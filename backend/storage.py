"""Persistence adapter with Supabase and a safe local-development fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from dotenv import load_dotenv

LOGGER = logging.getLogger(__name__)


@dataclass
class InMemoryStore:
    """Process-local store used when Supabase is unavailable.

    The fallback intentionally mirrors only the non-audio data model. It is
    useful for a local demo and is not a replacement for durable production
    persistence.
    """

    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    reputations: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: list[dict[str, Any]] = field(default_factory=list)
    contacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    helplines: list[dict[str, Any]] = field(default_factory=list)


class DatabaseRepository:
    """Small async adapter around the synchronous supabase-py client."""

    def __init__(
        self,
        client: Any | None = None,
        fallback_store: InMemoryStore | None = None,
        helplines_path: Path | None = None,
    ) -> None:
        self.client = client
        self.memory = fallback_store or InMemoryStore()
        self.helplines_path = helplines_path or (
            Path(__file__).resolve().parent / "data" / "helplines.json"
        )
        self._load_fallback_helplines()

    @property
    def supabase_configured(self) -> bool:
        """Whether the adapter has a live Supabase client configured."""

        return self.client is not None

    @staticmethod
    def _response_rows(response: Any) -> list[dict[str, Any]]:
        data = getattr(response, "data", None)
        if isinstance(data, list):
            return [dict(row) for row in data if isinstance(row, Mapping)]
        if isinstance(data, Mapping):
            return [dict(data)]
        return []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _execute(self, operation: Callable[[], Any]) -> Any:
        """Run blocking Supabase I/O away from the event loop."""

        return await asyncio.to_thread(operation)

    def _load_fallback_helplines(self) -> None:
        if self.memory.helplines or not self.helplines_path.exists():
            return
        try:
            with self.helplines_path.open("r", encoding="utf-8") as handle:
                rows = json.load(handle)
            if isinstance(rows, list):
                self.memory.helplines = [dict(row) for row in rows if isinstance(row, Mapping)]
        except (OSError, ValueError) as exc:
            LOGGER.warning("Could not load fallback helplines: %s", exc)

    async def create_session(self, language: str, is_practice: bool = False) -> dict[str, Any]:
        """Create a session row without accepting or storing raw caller audio."""

        payload = {"language": language, "is_practice": is_practice}
        row: dict[str, Any] | None = None
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("sessions").insert(payload).execute()
                )
                rows = self._response_rows(response)
                row = rows[0] if rows else None
            except Exception as exc:  # noqa: BLE001 - persistence must not kill monitoring
                LOGGER.warning("Supabase session insert failed; using local fallback: %s", exc)
        if row is None:
            row = {
                "id": str(uuid.uuid4()),
                "created_at": self._now(),
                "verdict": None,
                "final_score": None,
                "language": language,
                "alert_sent": False,
                "is_practice": is_practice,
            }
        row.setdefault("language", language)
        row.setdefault("is_practice", is_practice)
        row.setdefault("created_at", self._now())
        row.setdefault("alert_sent", False)
        self.memory.sessions[str(row["id"])] = dict(row)
        return dict(row)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a session by UUID-like identifier."""

        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("sessions")
                    .select("*")
                    .eq("id", session_id)
                    .limit(1)
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    row = rows[0]
                    self.memory.sessions[session_id] = dict(row)
                    return dict(row)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase session lookup failed: %s", exc)
        row = self.memory.sessions.get(session_id)
        return dict(row) if row else None

    async def update_session(self, session_id: str, updates: Mapping[str, Any]) -> dict[str, Any] | None:
        """Update only known session fields and mirror them locally."""

        allowed = {"verdict", "final_score", "alert_sent", "language", "is_practice"}
        clean_updates = {key: value for key, value in updates.items() if key in allowed}
        if not clean_updates:
            return await self.get_session(session_id)
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("sessions")
                    .update(clean_updates)
                    .eq("id", session_id)
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    self.memory.sessions[session_id] = dict(rows[0])
                    return dict(rows[0])
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase session update failed: %s", exc)
        if session_id not in self.memory.sessions:
            return None
        self.memory.sessions[session_id].update(clean_updates)
        return dict(self.memory.sessions[session_id])

    async def list_sessions(self, limit: int, offset: int) -> list[dict[str, Any]]:
        """Return newest sessions first."""

        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("sessions")
                    .select("id,created_at,verdict,final_score,language,alert_sent,is_practice")
                    .order("created_at", desc=True)
                    .range(offset, offset + limit - 1)
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    for row in rows:
                        self.memory.sessions[str(row["id"])] = dict(row)
                    return rows
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase session listing failed: %s", exc)
        rows = sorted(
            self.memory.sessions.values(),
            key=lambda row: str(row.get("created_at", "")),
            reverse=True,
        )
        return [dict(row) for row in rows[offset : offset + limit]]

    async def insert_call_event(self, event: Mapping[str, Any]) -> dict[str, Any] | None:
        """Insert a score-only call event; raw audio is never accepted here."""

        clean_event = dict(event)
        clean_event["transcript_snippet"] = str(clean_event.get("transcript_snippet", ""))[:280]
        clean_event["matched_patterns"] = list(clean_event.get("matched_patterns", []))
        inserted: dict[str, Any] | None = None
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("call_events").insert(clean_event).execute()
                )
                rows = self._response_rows(response)
                inserted = rows[0] if rows else None
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase call event insert failed: %s", exc)
        if inserted is None:
            inserted = {
                "id": str(uuid.uuid4()),
                "timestamp": self._now(),
                **clean_event,
            }
        self.memory.events.append(dict(inserted))
        return dict(inserted)

    async def get_call_events(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch events in chronological order."""

        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("call_events")
                    .select("*")
                    .eq("session_id", session_id)
                    .order("timestamp", desc=False)
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    return rows
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase event lookup failed: %s", exc)
        return [dict(row) for row in self.memory.events if row.get("session_id") == session_id]

    async def get_reputation(self, phone_number_hash: str) -> dict[str, Any] | None:
        """Read reputation using only a SHA-256 phone key."""

        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("caller_reputation")
                    .select("*")
                    .eq("phone_number_hash", phone_number_hash)
                    .limit(1)
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    self.memory.reputations[phone_number_hash] = dict(rows[0])
                    return dict(rows[0])
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase caller lookup failed: %s", exc)
        row = self.memory.reputations.get(phone_number_hash)
        return dict(row) if row else None

    async def upsert_reputation(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Upsert a reputation row keyed by hash."""

        clean_row = dict(row)
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("caller_reputation")
                    .upsert(clean_row, on_conflict="phone_number_hash")
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    clean_row = rows[0]
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase reputation upsert failed: %s", exc)
        self.memory.reputations[str(clean_row["phone_number_hash"])] = dict(clean_row)
        return dict(clean_row)

    async def insert_community_report(self, row: Mapping[str, Any]) -> dict[str, Any] | None:
        """Insert a community report after its reputation row exists."""

        clean_row = dict(row)
        inserted: dict[str, Any] | None = None
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("community_reports").insert(clean_row).execute()
                )
                rows = self._response_rows(response)
                inserted = rows[0] if rows else None
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase community report insert failed: %s", exc)
        if inserted is None:
            inserted = {"id": str(uuid.uuid4()), "created_at": self._now(), **clean_row}
        self.memory.reports.append(dict(inserted))
        return dict(inserted)

    async def list_reports_for_hash(self, phone_number_hash: str) -> list[dict[str, Any]]:
        """Return community reports for one hashed caller number."""

        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("community_reports")
                    .select("id,phone_number_hash,category,created_at")
                    .eq("phone_number_hash", phone_number_hash)
                    .order("created_at", desc=False)
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    return rows
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase community report lookup failed: %s", exc)
        return [
            dict(row)
            for row in self.memory.reports
            if row.get("phone_number_hash") == phone_number_hash
        ]

    async def list_contacts(self, owner_id: str) -> list[dict[str, Any]]:
        """List contacts for one device/session owner."""

        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("emergency_contacts")
                    .select("*")
                    .eq("user_session_owner_id", owner_id)
                    .order("name")
                    .execute()
                )
                rows = self._response_rows(response)
                if rows:
                    for row in rows:
                        self.memory.contacts[str(row["id"])] = dict(row)
                    return rows
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase contact listing failed: %s", exc)
        return [
            dict(row)
            for row in self.memory.contacts.values()
            if row.get("user_session_owner_id") == owner_id
        ]

    async def create_contact(self, contact: Mapping[str, Any]) -> dict[str, Any]:
        """Create a contact and enforce the five-contact application limit."""

        owner_id = str(contact["user_session_owner_id"])
        existing = await self.list_contacts(owner_id)
        if len(existing) >= 5:
            raise ValueError("A maximum of five emergency contacts is allowed")
        clean_contact = dict(contact)
        row: dict[str, Any] | None = None
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("emergency_contacts").insert(clean_contact).execute()
                )
                rows = self._response_rows(response)
                row = rows[0] if rows else None
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase contact insert failed: %s", exc)
        if row is None:
            row = {"id": str(uuid.uuid4()), **clean_contact}
        self.memory.contacts[str(row["id"])] = dict(row)
        return dict(row)

    async def delete_contact(self, contact_id: str) -> bool:
        """Delete one contact by identifier."""

        deleted = False
        if self.client is not None:
            try:
                response = await self._execute(
                    lambda: self.client.table("emergency_contacts")
                    .delete()
                    .eq("id", contact_id)
                    .execute()
                )
                deleted = bool(self._response_rows(response))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase contact deletion failed: %s", exc)
        deleted = self.memory.contacts.pop(contact_id, None) is not None or deleted
        return deleted

    async def list_helplines(self, category: str | None = None) -> list[dict[str, Any]]:
        """Read Supabase helplines and fall back to checked-in JSON when empty."""

        if self.client is not None:
            try:
                query = self.client.table("helplines").select("*")
                if category:
                    query = query.eq("category", category)
                response = await self._execute(lambda: query.order("name").execute())
                rows = self._response_rows(response)
                if rows:
                    return rows
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Supabase helpline lookup failed; using JSON fallback: %s", exc)
        rows = self.memory.helplines
        if category:
            rows = [row for row in rows if row.get("category") == category]
        return [dict(row) for row in rows]


def create_supabase_client() -> Any | None:
    """Create a client when both environment credentials are present.

    Missing credentials are a supported local-development mode. The caller
    still receives a fully functioning repository backed by ``InMemoryStore``.
    """

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        LOGGER.warning("SUPABASE_URL/SUPABASE_KEY missing; using local persistence fallback")
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Could not initialize Supabase client; using local fallback: %s", exc)
        return None
