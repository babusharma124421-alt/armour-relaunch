"""Typed request, response, and service contracts for the backend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Verdict = Literal["SAFE", "SUSPICIOUS", "CRITICAL"]
ReportCategory = Literal["impersonation", "financial_fraud", "harassment", "other"]


class VoiceResult(BaseModel):
    """Result returned by the audio authenticity model."""

    synthetic_probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    model_used: str


class TranscriptResult(BaseModel):
    """Transcript and language metadata for one audio chunk."""

    transcript: str = Field(default="", max_length=5000)
    detected_language: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ScriptResult(BaseModel):
    """Offline regex scanner output."""

    script_score: float = Field(ge=0.0, le=100.0)
    matched_patterns: list[str] = Field(default_factory=list)
    matched_categories: list[str] = Field(default_factory=list)


class IntentResult(BaseModel):
    """LLM intent output plus the offline score blended into it."""

    intent_score: float = Field(default=0.0, ge=0.0, le=100.0)
    script_score: float = Field(default=0.0, ge=0.0, le=100.0)
    detected_patterns: list[str] = Field(default_factory=list)
    reasoning: str = ""
    primary_threat_type: Literal[
        "authority_impersonation",
        "financial_fraud",
        "urgency_pressure",
        "secrecy_coercion",
        "remote_access",
        "unknown",
    ] = "unknown"
    fallback: bool = False

    @property
    def llm_intent_score(self) -> float:
        """Expose the LLM score using the pipeline's domain vocabulary."""

        return self.intent_score


class CallerResult(BaseModel):
    """Reputation lookup for a hashed caller number."""

    caller_score: float = Field(ge=0.0, le=100.0)
    report_count: int = Field(default=0, ge=0)
    community_report_count: int = Field(default=0, ge=0)
    avg_reported_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    is_known_scammer: bool = False


class BehaviorResult(BaseModel):
    """Rolling behavioral model output."""

    behavior_score: float = Field(ge=0.0, le=100.0)
    top_features: list[str] = Field(default_factory=list, max_length=3)


class ScoreBreakdown(BaseModel):
    """The four normalized components used by the fusion engine."""

    voice: float = Field(ge=0.0, le=100.0)
    intent: float = Field(ge=0.0, le=100.0)
    caller: float = Field(ge=0.0, le=100.0)
    behavior: float = Field(ge=0.0, le=100.0)


class FusedResult(BaseModel):
    """Final user-facing risk decision."""

    final_score: float = Field(ge=0.0, le=100.0)
    verdict: Verdict
    breakdown: ScoreBreakdown
    reasons: list[str] = Field(default_factory=list, max_length=5)
    matched_patterns: list[str] = Field(default_factory=list)
    transcript_snippet: str = Field(default="", max_length=280)
    detected_language: str = "unknown"


class SessionStartRequest(BaseModel):
    """Payload used to create a monitored call session."""

    model_config = ConfigDict(extra="ignore")

    language: str = Field(default="auto", min_length=2, max_length=20)
    caller_phone: str | None = Field(default=None, max_length=32)
    is_practice: bool = False

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return value.strip().lower() or "auto"

    @field_validator("caller_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SessionStartResponse(BaseModel):
    """Session identifier returned to the client."""

    session_id: str
    language: str


class RiskPayload(BaseModel):
    """WebSocket and history event payload."""

    model_config = ConfigDict(extra="ignore")

    voice_score: float = Field(ge=0.0, le=100.0)
    script_score: float = Field(ge=0.0, le=100.0)
    intent_score: float = Field(ge=0.0, le=100.0)
    caller_score: float = Field(ge=0.0, le=100.0)
    behavior_score: float = Field(ge=0.0, le=100.0)
    final_score: float = Field(ge=0.0, le=100.0)
    verdict: Verdict
    reasons: list[str] = Field(default_factory=list, max_length=5)
    matched_patterns: list[str] = Field(default_factory=list)
    transcript_snippet: str = Field(default="", max_length=280)
    detected_language: str = "unknown"
    breakdown: ScoreBreakdown


class CommunityReportRequest(BaseModel):
    """Community report payload; the phone is hashed before persistence."""

    model_config = ConfigDict(extra="ignore")

    phone_number: str = Field(min_length=7, max_length=32)
    category: ReportCategory
    note: str | None = Field(default=None, max_length=1000)
    session_id: str

    @field_validator("phone_number")
    @classmethod
    def normalize_report_phone(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("phone_number cannot be empty")
        return cleaned


class PanicRequest(BaseModel):
    """Manual alert request."""

    session_id: str
    user_session_owner_id: str | None = Field(default=None, max_length=200)
    owner_name: str = Field(default="User", max_length=100)


class ContactRequest(BaseModel):
    """Emergency contact create payload."""

    user_session_owner_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=32)
    relationship: str | None = Field(default=None, max_length=80)

    @field_validator("user_session_owner_id", "name", "phone", "relationship")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        allowed = set("0123456789+ -()")
        if any(character not in allowed for character in value) or sum(
            character.isdigit() for character in value
        ) < 7:
            raise ValueError("phone must contain at least seven digits")
        return value


class ContactResponse(ContactRequest):
    """Persisted emergency contact."""

    id: str


class SessionSummary(BaseModel):
    """Compact session row for history."""

    id: str
    created_at: datetime | str
    verdict: Verdict | None = None
    final_score: float | None = Field(default=None, ge=0.0, le=100.0)
    language: str
    alert_sent: bool = False
    is_practice: bool = False


class SessionHistoryResponse(BaseModel):
    """Session metadata and reconstructed risk events."""

    session: SessionSummary
    events: list[RiskPayload]


class PaginatedSessionsResponse(BaseModel):
    """Paginated history response."""

    items: list[SessionSummary]
    limit: int
    offset: int
    has_more: bool


class CommunityReportResponse(BaseModel):
    """Acknowledgement returned after a report is accepted."""

    success: bool
    message: str


class PanicResponse(BaseModel):
    """Summary of attempted emergency notifications."""

    notified_count: int = Field(ge=0)
    success: bool


class HelplineResponse(BaseModel):
    """Editable helpline directory row."""

    id: str | None = None
    name: str
    number: str
    category: str
    description: str | None = None
    available_hours: str | None = None
    locale: str = "all"


class HealthResponse(BaseModel):
    """Small operational health response."""

    status: str
    supabase_configured: bool
    services_ready: bool


class DatabaseRow(BaseModel):
    """Typed escape hatch for rows returned by external persistence."""

    model_config = ConfigDict(extra="allow")

    values: dict[str, Any] = Field(default_factory=dict)
