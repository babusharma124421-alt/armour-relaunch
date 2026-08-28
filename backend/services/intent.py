"""Groq Whisper transcription and multilingual intent analysis."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:  # pragma: no cover - requirements install supplies this package
    Groq = None  # type: ignore[assignment,misc]

try:
    from ..schemas import IntentResult, TranscriptResult
except ImportError:  # Supports `uvicorn main:app` from backend directory.
    from schemas import IntentResult, TranscriptResult

LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert fraud detection system specializing in
voice-based social engineering and impersonation scams. You analyze telephone
call transcripts in English, Hindi (Devanagari and Latin-transliterated), and
Hinglish (code-switched). Do NOT assume scam phrases appear only in English —
check for equivalent phrases in all three language forms.

Analyze the transcript and conversation history. Score scam intent from 0 to
100. Return ONLY valid JSON:
{
  "intent_score": <0-100>,
  "detected_patterns": ["pattern1", "pattern2"],
  "reasoning": "<brief explanation max 2 sentences>",
  "primary_threat_type": "<authority_impersonation | financial_fraud | urgency_pressure | secrecy_coercion | remote_access | unknown>"
}

Score based on these signals (check in Hindi/Hinglish too, not only English):
- Authority impersonation (police/CBI/RBI/bank/govt/court/customs/narcotics — any official body)
- Urgency or threat language (arrest, FIR, warrant, "you are in trouble", "immediately", deadlines)
- Secrecy requests ("don't tell anyone", "stay on line", "don't disconnect", "keep confidential")
- Financial or data requests (OTP, PIN, account number, money transfer, UPI, AnyDesk install)
- False accusations linking the target to crimes
- Coerced video/audio surveillance ("digital arrest")

Keep reasoning general to any impersonation-based social engineering — not
hardcoded to any single scam type."""


class IntentAnalysisService:
    """Use Groq once per service instance and degrade to scanner-only mode."""

    def __init__(self, api_key: str | None = None, model: str = "llama-3.1-8b-instant") -> None:
        load_dotenv()
        self.api_key = (api_key if api_key is not None else os.getenv("GROQ_API_KEY", "")).strip()
        self.model = model
        self.client: Any | None = None
        if self.api_key and Groq is not None:
            try:
                self.client = Groq(api_key=self.api_key)
                LOGGER.info("Groq intent service initialized with model %s", self.model)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Groq client initialization failed: %s", exc)
        else:
            LOGGER.warning("GROQ_API_KEY missing; using scanner-only intent fallback")

    @property
    def groq_available(self) -> bool:
        """Whether remote transcription/classification calls can be made."""

        return self.client is not None

    @staticmethod
    def _demo_text(audio_chunk: bytes) -> str | None:
        """Read a text marker used by the offline demo without writing audio."""

        marker = b"DEMO_TEXT:"
        position = audio_chunk.find(marker)
        if position < 0:
            return None
        text = audio_chunk[position + len(marker) :].split(b"\x00", 1)[0]
        try:
            return text.decode("utf-8", errors="ignore").strip()
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _detect_language(text: str, requested: str = "auto") -> str:
        if requested not in {"", "auto"}:
            normalized = requested.lower()
            if normalized.startswith("hi"):
                return "hi"
            if normalized.startswith("en"):
                return "en"
        if re.search(r"[\u0900-\u097f]", text):
            return "hi"
        hinglish_markers = {
            "aap",
            "hai",
            "hain",
            "sir",
            "madam",
            "paisa",
            "paise",
            "karo",
            "mat",
            "account",
            "batao",
        }
        tokens = {token.lower() for token in re.findall(r"[A-Za-z]+", text)}
        if tokens.intersection(hinglish_markers):
            return "hinglish"
        return "en" if text else "unknown"

    async def transcribe(self, audio_chunk: bytes, language: str = "auto") -> TranscriptResult:
        """Transcribe an in-memory chunk with Groq Whisper."""

        demo_text = self._demo_text(audio_chunk)
        if demo_text is not None:
            if len(demo_text) < 3:
                return TranscriptResult(transcript="", detected_language="unknown", confidence=0.0)
            return TranscriptResult(
                transcript=demo_text,
                detected_language=self._detect_language(demo_text, language),
                confidence=1.0,
            )

        if self.client is None:
            return TranscriptResult(transcript="", detected_language="unknown", confidence=0.0)

        def request_transcription() -> Any:
            buffer = io.BytesIO(bytes(audio_chunk))
            buffer.seek(0)
            return self.client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=("chunk.wav", buffer, "audio/wav"),
                response_format="verbose_json",
                language=None if language == "auto" else language,
            )

        try:
            response = await asyncio.to_thread(request_transcription)
            transcript = str(getattr(response, "text", "") or "").strip()
            if len(transcript) < 3:
                return TranscriptResult(transcript="", detected_language="unknown", confidence=0.0)
            detected = str(getattr(response, "language", "") or "").lower().strip()
            detected_language = self._detect_language(transcript, detected or language)
            segments = getattr(response, "segments", None)
            confidence = 0.85
            if isinstance(segments, list) and segments:
                confidence_values = [
                    float(segment.get("avg_logprob", -0.5))
                    for segment in segments
                    if isinstance(segment, dict) and "avg_logprob" in segment
                ]
                if confidence_values:
                    confidence = max(0.0, min(1.0, sum(confidence_values) / len(confidence_values) / 2.0 + 1.0))
            return TranscriptResult(
                transcript=transcript,
                detected_language=detected_language,
                confidence=confidence,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Groq Whisper unavailable for chunk: %s", exc)
            return TranscriptResult(transcript="", detected_language="unknown", confidence=0.0)

    @staticmethod
    def _parse_json_response(raw_response: str) -> dict[str, Any]:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Groq response was not a JSON object")
        return parsed

    async def classify(
        self,
        transcript: str,
        history: list[str],
        detected_language: str,
    ) -> IntentResult:
        """Classify a transcript using a sliding conversation window."""

        if not transcript or len(transcript.strip()) < 3:
            return IntentResult(intent_score=0.0, detected_patterns=[], reasoning="", fallback=False)
        if self.client is None:
            return IntentResult(
                intent_score=0.0,
                detected_patterns=[],
                reasoning="Groq unavailable; offline scanner signal used.",
                primary_threat_type="unknown",
                fallback=True,
            )

        joined_history = "\n".join(history[-10:])
        user_message = (
            f"Conversation history:\n{joined_history}\n\n"
            f"Latest transcript segment: {transcript}\n"
            f"Detected language: {detected_language}"
        )

        def request_classification() -> Any:
            return self.client.chat.completions.create(
                model=self.model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )

        try:
            completion = await asyncio.to_thread(request_classification)
            raw_response = str(completion.choices[0].message.content or "")
            payload = self._parse_json_response(raw_response)
            return IntentResult.model_validate(
                {
                    "intent_score": payload.get("intent_score", 0.0),
                    "detected_patterns": payload.get("detected_patterns", []),
                    "reasoning": str(payload.get("reasoning", ""))[:500],
                    "primary_threat_type": payload.get("primary_threat_type", "unknown"),
                    "fallback": False,
                }
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Groq intent response could not be parsed or fetched: %s", exc)
            if "raw_response" in locals():
                LOGGER.warning("Raw Groq intent response: %s", raw_response)
            return IntentResult(
                intent_score=0.0,
                detected_patterns=[],
                reasoning="Parse error",
                primary_threat_type="unknown",
                fallback=True,
            )
