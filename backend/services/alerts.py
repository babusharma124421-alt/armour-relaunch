"""SMS alert providers selected through environment configuration."""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

try:
    from twilio.rest import Client as TwilioClient
except ImportError:  # pragma: no cover - requirements install supplies this package
    TwilioClient = None  # type: ignore[assignment,misc]

LOGGER = logging.getLogger(__name__)


class AlertProvider(ABC):
    """Provider interface for emergency SMS delivery."""

    @abstractmethod
    async def send(self, contact_phone: str, message: str) -> bool:
        """Send one message and report whether the provider accepted it."""


class TwilioAlertProvider(AlertProvider):
    """Twilio implementation using the synchronous SDK off the event loop."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self.from_number = from_number
        self.client: Any | None = None
        if account_sid and auth_token and from_number and TwilioClient is not None:
            try:
                self.client = TwilioClient(account_sid, auth_token)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Twilio client initialization failed: %s", exc)

    async def send(self, contact_phone: str, message: str) -> bool:
        """Create a Twilio message and return true only after SDK success."""

        if self.client is None:
            LOGGER.warning("Twilio credentials are not configured; SMS was not sent")
            return False

        def create_message() -> Any:
            return self.client.messages.create(
                to=contact_phone,
                from_=self.from_number,
                body=message,
            )

        try:
            await asyncio.to_thread(create_message)
            return True
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Twilio SMS delivery failed: %s", exc)
            return False


class Fast2SMSAlertProvider(AlertProvider):
    """Fast2SMS HTTP API implementation."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.endpoint = "https://www.fast2sms.com/dev/bulkV2"

    async def send(self, contact_phone: str, message: str) -> bool:
        """Send a transactional-style quick message through Fast2SMS."""

        if not self.api_key:
            LOGGER.warning("FAST2SMS_API_KEY is not configured; SMS was not sent")
            return False
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        payload = {
            "route": "q",
            "message": message,
            "language": "english",
            "numbers": contact_phone,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
            return response.status_code == 200
        except httpx.HTTPError as exc:
            LOGGER.warning("Fast2SMS request failed: %s", exc)
            return False


class AlertService:
    """Choose Twilio or Fast2SMS once at application startup."""

    def __init__(self, provider_name: str | None = None) -> None:
        provider = (provider_name or os.getenv("SMS_PROVIDER", "twilio")).strip().lower()
        if provider == "twilio":
            self.provider: AlertProvider = TwilioAlertProvider(
                os.getenv("TWILIO_ACCOUNT_SID", ""),
                os.getenv("TWILIO_AUTH_TOKEN", ""),
                os.getenv("TWILIO_FROM_NUMBER", ""),
            )
        elif provider == "fast2sms":
            self.provider = Fast2SMSAlertProvider(os.getenv("FAST2SMS_API_KEY", ""))
        else:
            raise ValueError("SMS_PROVIDER must be either 'twilio' or 'fast2sms'")
        self.provider_name = provider

    async def send_alert(
        self,
        contact_phone: str,
        session_id: str,
        verdict: str,
        score: float,
        owner_name: str = "User",
    ) -> bool:
        """Send a privacy-conscious, enforced sub-160-character alert."""

        message = (
            f"[the app Alert] {owner_name}'s device has detected a {verdict} risk call "
            f"(score: {score:.0f}/100). Session: {session_id[:8]}. "
            "This is an automated safety alert."
        )
        if len(message) >= 160:
            message = message[:156] + "..."
        return await self.provider.send(contact_phone, message)
