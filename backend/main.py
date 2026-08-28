"""FastAPI entrypoint for the Armour live voice-integrity platform."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

try:
    from .schemas import (
        CallerResult,
        CommunityReportRequest,
        CommunityReportResponse,
        ContactRequest,
        ContactResponse,
        HealthResponse,
        HelplineResponse,
        IntentResult,
        PanicRequest,
        PanicResponse,
        PaginatedSessionsResponse,
        RiskPayload,
        ScoreBreakdown,
        ScriptResult,
        SessionHistoryResponse,
        SessionStartRequest,
        SessionStartResponse,
        SessionSummary,
        Verdict,
    )
    from .services.alerts import AlertService
    from .services.behavior import BehaviorScoringService
    from .services.context import CallerContextService
    from .services.fusion import FusionService
    from .services.intent import IntentAnalysisService
    from .services.script_scanner import ScriptScannerService
    from .services.voice import VoiceAuthenticityService
    from .storage import DatabaseRepository, create_supabase_client
except ImportError:  # Supports `uvicorn main:app` from the backend directory.
    from schemas import (
        CallerResult,
        CommunityReportRequest,
        CommunityReportResponse,
        ContactRequest,
        ContactResponse,
        HealthResponse,
        HelplineResponse,
        IntentResult,
        PanicRequest,
        PanicResponse,
        PaginatedSessionsResponse,
        RiskPayload,
        ScoreBreakdown,
        ScriptResult,
        SessionHistoryResponse,
        SessionStartRequest,
        SessionStartResponse,
        SessionSummary,
        Verdict,
    )
    from services.alerts import AlertService
    from services.behavior import BehaviorScoringService
    from services.context import CallerContextService
    from services.fusion import FusionService, reason_key_to_display_string
    from services.intent import IntentAnalysisService
    from services.script_scanner import ScriptScannerService
    from services.voice import VoiceAuthenticityService
    from storage import DatabaseRepository, create_supabase_client

try:
    from .services.fusion import reason_key_to_display_string
except ImportError:  # pragma: no cover - top-level import already handled above
    pass

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavyweight models and integrations exactly once per process."""

    app.state.repository = DatabaseRepository(
        client=create_supabase_client(),
        helplines_path=ROOT / "data" / "helplines.json",
    )
    app.state.voice_service = VoiceAuthenticityService()
    app.state.intent_service = IntentAnalysisService()
    app.state.script_service = ScriptScannerService(ROOT / "data" / "script_patterns.yaml")
    app.state.behavior_service = BehaviorScoringService(ROOT / "data" / "behavior_bootstrap.csv")
    app.state.fusion_service = FusionService()
    app.state.context_service = CallerContextService(app.state.repository)
    app.state.alert_service = AlertService()
    app.state.caller_cache: dict[str, CallerResult] = {}
    app.state.session_states: dict[str, dict[str, Any]] = {}
    app.state.panic_attempts: dict[str, float] = {}
    app.state.services_ready = True
    LOGGER.info("Armour backend services initialized")
    try:
        yield
    finally:
        app.state.services_ready = False
        app.state.session_states.clear()


app = FastAPI(
    title="the app — Voice Integrity API",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

raw_origins = os.getenv("ALLOW_ORIGINS", "*").strip()
allow_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
if not allow_origins:
    allow_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _session_summary(row: dict[str, Any]) -> SessionSummary:
    """Validate a persistence row before returning it to a client."""

    return SessionSummary(
        id=str(row["id"]),
        created_at=row.get("created_at", datetime.now(timezone.utc).isoformat()),
        verdict=row.get("verdict"),
        final_score=row.get("final_score"),
        language=str(row.get("language", "auto")),
        alert_sent=bool(row.get("alert_sent", False)),
        is_practice=bool(row.get("is_practice", False)),
    )


def _neutral_caller() -> CallerResult:
    return CallerResult(caller_score=0.0)


def _safe_score(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _event_to_payload(event: dict[str, Any], session_language: str) -> RiskPayload:
    """Reconstruct the public payload from score-only persisted evidence."""

    voice_score = _safe_score(event.get("voice_score"))
    script_score = _safe_score(event.get("script_score"))
    intent_score = _safe_score(event.get("intent_score"))
    behavior_score = _safe_score(event.get("behavior_score"))
    final_score = _safe_score(event.get("final_score"))
    raw_verdict = str(event.get("verdict", "SAFE"))
    verdict: Verdict = raw_verdict if raw_verdict in {"SAFE", "SUSPICIOUS", "CRITICAL"} else "SAFE"  # type: ignore[assignment]
    pattern_ids = [str(item) for item in event.get("matched_patterns", [])]
    reasons = [reason_key_to_display_string(pattern_id) for pattern_id in pattern_ids[:5]]
    if not reasons:
        reasons = ["No strong scam indicators were detected in this call segment."]
    return RiskPayload(
        voice_score=voice_score,
        script_score=script_score,
        intent_score=intent_score,
        caller_score=0.0,
        behavior_score=behavior_score,
        final_score=final_score,
        verdict=verdict,
        reasons=reasons[:5],
        matched_patterns=pattern_ids,
        transcript_snippet=str(event.get("transcript_snippet", ""))[:280],
        detected_language=str(event.get("detected_language", session_language)),
        breakdown=ScoreBreakdown(
            voice=voice_score,
            intent=intent_score,
            caller=0.0,
            behavior=behavior_score,
        ),
    )


def _risk_payload_from_fused(
    fused: Any,
    script_score: float,
    transcript_snippet: str,
    detected_language: str,
) -> RiskPayload:
    """Convert a fusion result into the stable WebSocket contract."""

    return RiskPayload(
        voice_score=fused.breakdown.voice,
        script_score=_safe_score(script_score),
        intent_score=fused.breakdown.intent,
        caller_score=fused.breakdown.caller,
        behavior_score=fused.breakdown.behavior,
        final_score=fused.final_score,
        verdict=fused.verdict,
        reasons=fused.reasons,
        matched_patterns=fused.matched_patterns,
        transcript_snippet=transcript_snippet[:280],
        detected_language=detected_language,
        breakdown=fused.breakdown,
    )


def _schedule_background(coroutine: Any) -> None:
    """Start fire-and-forget persistence while consuming task exceptions."""

    task = asyncio.create_task(coroutine)

    def log_failure(completed: asyncio.Task[Any]) -> None:
        try:
            completed.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Background persistence task failed: %s", exc)

    task.add_done_callback(log_failure)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Expose basic readiness without leaking credentials."""

    repository = getattr(app.state, "repository", None)
    return HealthResponse(
        status="ok" if getattr(app.state, "services_ready", False) else "starting",
        supabase_configured=bool(repository and repository.supabase_configured),
        services_ready=bool(getattr(app.state, "services_ready", False)),
    )


@app.post("/session/start", response_model=SessionStartResponse)
@limiter.limit("20/hour")
async def start_session(request: Request, payload: SessionStartRequest) -> SessionStartResponse:
    """Create a session and cache caller reputation without storing its number."""

    repository: DatabaseRepository = app.state.repository
    row = await repository.create_session(payload.language, payload.is_practice)
    session_id = str(row["id"])
    caller_result = _neutral_caller()
    if payload.caller_phone:
        caller_result = await app.state.context_service.lookup_caller(payload.caller_phone)
    app.state.caller_cache[session_id] = caller_result
    return SessionStartResponse(session_id=session_id, language=payload.language)


@app.get("/session/{session_id}/history", response_model=SessionHistoryResponse)
async def session_history(session_id: str) -> SessionHistoryResponse:
    """Return session metadata plus chronological reconstructed risk events."""

    repository: DatabaseRepository = app.state.repository
    session = await repository.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    events = await repository.get_call_events(session_id)
    return SessionHistoryResponse(
        session=_session_summary(session),
        events=[_event_to_payload(event, str(session.get("language", "auto"))) for event in events],
    )


@app.get("/sessions/all", response_model=PaginatedSessionsResponse)
async def all_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedSessionsResponse:
    """List sessions in newest-first order with bounded pagination."""

    rows = await app.state.repository.list_sessions(limit, offset)
    return PaginatedSessionsResponse(
        items=[_session_summary(row) for row in rows],
        limit=limit,
        offset=offset,
        has_more=len(rows) == limit,
    )


@app.post("/community-report", response_model=CommunityReportResponse)
@limiter.limit("3/hour")
async def community_report(
    request: Request,
    payload: CommunityReportRequest,
) -> CommunityReportResponse:
    """Accept a report and persist only the caller's SHA-256 hash."""

    if await app.state.repository.get_session(payload.session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await app.state.context_service.submit_community_report(
        payload.phone_number,
        payload.category,
        payload.note,
        payload.session_id,
    )
    return CommunityReportResponse(success=True, message="Report submitted. Thank you.")


@app.post("/panic", response_model=PanicResponse)
@limiter.limit("1/10minutes")
async def panic(
    request: Request,
    payload: PanicRequest,
    x_device_id: str | None = Header(default=None),
) -> PanicResponse:
    """Notify up to five saved contacts, once per session cooldown."""

    now = time.monotonic()
    last_attempt = app.state.panic_attempts.get(payload.session_id)
    if last_attempt is not None and now - last_attempt < 600:
        raise HTTPException(status_code=429, detail="Panic already triggered for this session")
    session = await app.state.repository.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    owner_id = (payload.user_session_owner_id or x_device_id or "").strip()
    if not owner_id:
        raise HTTPException(status_code=400, detail="An emergency contact owner id is required")
    app.state.panic_attempts[payload.session_id] = now
    contacts = await app.state.repository.list_contacts(owner_id)
    verdict = str(session.get("verdict") or "SUSPICIOUS")
    score = _safe_score(session.get("final_score"))
    results = await asyncio.gather(
        *[
            app.state.alert_service.send_alert(
                str(contact.get("phone", "")),
                payload.session_id,
                verdict,
                score,
                payload.owner_name,
            )
            for contact in contacts
        ],
        return_exceptions=True,
    )
    notified_count = sum(result is True for result in results)
    if contacts:
        await app.state.repository.update_session(payload.session_id, {"alert_sent": notified_count > 0})
    return PanicResponse(notified_count=notified_count, success=notified_count > 0)


@app.post("/contacts", response_model=ContactResponse)
async def create_contact(payload: ContactRequest) -> ContactResponse:
    """Create an emergency contact, enforcing the backend five-contact limit."""

    try:
        row = await app.state.repository.create_contact(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ContactResponse.model_validate(row)


@app.get("/contacts", response_model=list[ContactResponse])
async def get_contacts(user_session_owner_id: str = Query(min_length=1, max_length=200)) -> list[ContactResponse]:
    """List contacts belonging to a device owner."""

    rows = await app.state.repository.list_contacts(user_session_owner_id)
    return [ContactResponse.model_validate(row) for row in rows]


@app.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str) -> dict[str, bool]:
    """Delete one emergency contact."""

    deleted = await app.state.repository.delete_contact(contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"success": True}


@app.get("/helplines", response_model=list[HelplineResponse])
async def get_helplines(category: str | None = Query(default=None, max_length=80)) -> list[HelplineResponse]:
    """Read editable Supabase helplines, falling back to checked-in JSON."""

    rows = await app.state.repository.list_helplines(category)
    return [HelplineResponse.model_validate(row) for row in rows]


@app.websocket("/ws/call/{session_id}")
async def call_websocket(websocket: WebSocket, session_id: str) -> None:
    """Process two-second binary audio chunks through the live risk pipeline."""

    await websocket.accept()
    repository: DatabaseRepository = app.state.repository
    session = await repository.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    requested_language = str(session.get("language", "auto"))
    caller_result = app.state.caller_cache.get(session_id, _neutral_caller())
    session_state: dict[str, Any] = {
        "chunks_processed": 0,
        "score_history": [],
        "transcript_history": [],
        "caller_result": caller_result,
        "behavior_score": 0.0,
        "session_id": session_id,
        "language": requested_language,
        "started_at": datetime.now(timezone.utc),
    }
    app.state.session_states[session_id] = session_state
    last_payload: RiskPayload | None = None

    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            voice_result, transcript_result = await asyncio.gather(
                app.state.voice_service.analyze(audio_chunk),
                app.state.intent_service.transcribe(audio_chunk, requested_language),
            )
            transcript = transcript_result.transcript.strip()
            if transcript:
                script_result = app.state.script_service.scan(transcript)
                intent_result = await app.state.intent_service.classify(
                    transcript,
                    list(session_state["transcript_history"]),
                    transcript_result.detected_language,
                )
            else:
                script_result = ScriptResult(script_score=0.0)
                intent_result = IntentResult(intent_score=0.0)

            # When Groq is unavailable, the offline scanner is the sole intent signal.
            if intent_result.fallback:
                intent_result.intent_score = script_result.script_score
            intent_result.script_score = script_result.script_score
            intent_result.detected_patterns = list(
                dict.fromkeys(script_result.matched_patterns + intent_result.detected_patterns)
            )
            snippet = transcript[-280:]
            if snippet:
                session_state["transcript_history"].append(snippet)
                session_state["transcript_history"] = session_state["transcript_history"][-10:]
            session_state["chunks_processed"] += 1
            behavior_result = await asyncio.to_thread(
                app.state.behavior_service.score,
                session_state,
            )
            session_state["behavior_score"] = behavior_result.behavior_score
            fused = app.state.fusion_service.fuse(
                voice_result,
                intent_result,
                caller_result,
                behavior_result,
            )
            fused = fused.model_copy(
                update={
                    "matched_patterns": intent_result.detected_patterns,
                    "transcript_snippet": snippet,
                    "detected_language": transcript_result.detected_language,
                }
            )
            session_state["score_history"].append(fused.final_score)
            session_state["score_history"] = session_state["score_history"][-50:]
            last_payload = _risk_payload_from_fused(
                fused,
                script_result.script_score,
                snippet,
                transcript_result.detected_language,
            )
            _schedule_background(
                app.state.context_service.log_call_event(
                    session_id,
                    {
                        "voice_score": last_payload.voice_score,
                        "script_score": last_payload.script_score,
                        "intent_score": last_payload.intent_score,
                        "behavior_score": last_payload.behavior_score,
                        "final_score": last_payload.final_score,
                        "verdict": last_payload.verdict,
                        "transcript_snippet": last_payload.transcript_snippet,
                        "matched_patterns": last_payload.matched_patterns,
                    },
                )
            )
            await repository.update_session(
                session_id,
                {"verdict": last_payload.verdict, "final_score": last_payload.final_score},
            )
            await websocket.send_json(last_payload.model_dump(mode="json"))
    except WebSocketDisconnect:
        LOGGER.info("Call WebSocket disconnected for session %s", session_id)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Call WebSocket failed for session %s: %s", session_id, exc)
        try:
            await websocket.close(code=1011, reason="Call processing error")
        except Exception:  # noqa: BLE001
            pass
    finally:
        if last_payload is not None:
            await repository.update_session(
                session_id,
                {"verdict": last_payload.verdict, "final_score": last_payload.final_score},
            )
        app.state.session_states.pop(session_id, None)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return validation-like errors as readable API responses."""

    return JSONResponse(status_code=400, content={"detail": str(exc)})
