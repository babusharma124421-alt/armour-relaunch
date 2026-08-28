"""Caller reputation and privacy-preserving call context service."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

try:
    from ..schemas import CallerResult
    from ..storage import DatabaseRepository
except ImportError:  # Supports imports when running from backend/.
    from schemas import CallerResult
    from storage import DatabaseRepository

LOGGER = logging.getLogger(__name__)

CATEGORY_RISK: dict[str, float] = {
    "impersonation": 0.85,
    "financial_fraud": 1.0,
    "harassment": 0.65,
    "other": 0.45,
}


class CallerContextService:
    """Keep caller context useful without retaining raw phone numbers."""

    def __init__(self, repository: DatabaseRepository) -> None:
        self.repository = repository

    @staticmethod
    def hash_phone(phone: str) -> str:
        """Return the unsalted SHA-256 digest of a normalized phone string."""

        normalized = phone.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _result_from_row(row: Mapping[str, Any] | None) -> CallerResult:
        if not row:
            return CallerResult(
                caller_score=0.0,
                report_count=0,
                community_report_count=0,
                avg_reported_risk=0.0,
                is_known_scammer=False,
            )
        report_count = max(0, int(row.get("report_count", 0) or 0))
        community_count = max(0, int(row.get("community_report_count", 0) or 0))
        avg_risk = max(0.0, min(1.0, float(row.get("avg_reported_risk", 0.0) or 0.0)))
        base = min(report_count / 10.0, 1.0) * 50.0
        community = min(community_count / 5.0, 1.0) * 30.0
        caller_score = min(100.0, base + community + avg_risk * 20.0)
        return CallerResult(
            caller_score=round(caller_score, 2),
            report_count=report_count,
            community_report_count=community_count,
            avg_reported_risk=round(avg_risk, 4),
            is_known_scammer=caller_score >= 50.0 or report_count >= 3,
        )

    async def lookup_caller(self, phone_number: str) -> CallerResult:
        """Look up a caller by hash and calculate the documented score."""

        phone_hash = self.hash_phone(phone_number)
        row = await self.repository.get_reputation(phone_hash)
        return self._result_from_row(row)

    async def log_call_event(self, session_id: str, event_data: Mapping[str, Any]) -> None:
        """Persist score metadata and a maximum 280-character transcript snippet."""

        event = {
            "session_id": session_id,
            "voice_score": float(event_data.get("voice_score", 0.0)),
            "script_score": float(event_data.get("script_score", 0.0)),
            "intent_score": float(event_data.get("intent_score", 0.0)),
            "behavior_score": float(event_data.get("behavior_score", 0.0)),
            "final_score": float(event_data.get("final_score", 0.0)),
            "verdict": str(event_data.get("verdict", "SUSPICIOUS")),
            "transcript_snippet": str(event_data.get("transcript_snippet", ""))[:280],
            "matched_patterns": list(event_data.get("matched_patterns", [])),
        }
        await self.repository.insert_call_event(event)

    async def submit_community_report(
        self,
        phone_number: str,
        category: str,
        note: str | None,
        session_id: str,
    ) -> CallerResult:
        """Upsert reputation, insert a report, and recalculate average risk."""

        phone_hash = self.hash_phone(phone_number)
        existing = await self.repository.get_reputation(phone_hash) or {}
        report_count = int(existing.get("report_count", 0) or 0) + 1
        community_count = int(existing.get("community_report_count", 0) or 0) + 1
        reputation = await self.repository.upsert_reputation(
            {
                "phone_number_hash": phone_hash,
                "report_count": report_count,
                "community_report_count": community_count,
                "avg_reported_risk": float(existing.get("avg_reported_risk", 0.0) or 0.0),
            }
        )
        await self.repository.insert_community_report(
            {
                "phone_number_hash": phone_hash,
                "reporter_session_id": session_id,
                "category": category,
                "note": note[:1000] if note else None,
            }
        )
        reports = await self.repository.list_reports_for_hash(phone_hash)
        risk_values = [CATEGORY_RISK.get(str(row.get("category")), CATEGORY_RISK["other"]) for row in reports]
        average_risk = sum(risk_values) / len(risk_values) if risk_values else CATEGORY_RISK.get(category, 0.45)
        reputation = await self.repository.upsert_reputation(
            {
                **reputation,
                "phone_number_hash": phone_hash,
                "report_count": report_count,
                "community_report_count": community_count,
                "avg_reported_risk": round(min(1.0, average_risk), 4),
            }
        )
        LOGGER.info("Stored privacy-preserving community report for caller hash %s", phone_hash[:12])
        return self._result_from_row(reputation)
