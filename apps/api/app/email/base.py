"""The email seam — how Holofy sends a transactional message (reset link, verify link).

A Protocol so the rest of the app depends on "send this email", never on SMTP/SES/Postmark. The
dev/beta backend logs the message (and remembers the last one, for tests) instead of delivering it;
a real transport drops in behind the same seam by configuration, exactly like the pricing/recognition
providers. Messages are plain, link-bearing transactional mails — no marketing, no tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None:
        """Deliver one transactional email. Must not raise for a normal send; a transport fault is
        the implementation's concern (logged/retried there), never surfaced to the auth flow, so a
        flaky mailer can't 500 a password-reset request."""
        ...
