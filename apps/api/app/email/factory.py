"""Select the email transport by configuration — one place, like the other provider factories."""

from __future__ import annotations

from app.config import EmailBackend, Settings
from app.email.base import EmailSender
from app.email.logging_sender import LoggingEmailSender


def build_email_sender(settings: Settings) -> EmailSender:
    match settings.email_provider:
        case EmailBackend.LOGGING:
            return LoggingEmailSender()
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported email backend: {unknown}")
