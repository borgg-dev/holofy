"""The dev/beta email backend: log the message, don't deliver it.

For local and the closed beta there's no mail transport — a reset/verify link is read from the
server logs (or, in tests, from ``last_message``). It implements the same ``EmailSender`` seam a
real SMTP/API transport will, so wiring delivery later is a configuration change, not a code one.
The link itself is logged at INFO so an operator can complete a flow during the beta; the body is
otherwise treated as sensitive (a live, single-use credential) and never persisted.
"""

from __future__ import annotations

import logging

from app.email.base import EmailMessage, EmailSender

logger = logging.getLogger("holofy.email")


class LoggingEmailSender(EmailSender):
    def __init__(self) -> None:
        # Tests assert against the last message rather than scraping logs.
        self.last_message: EmailMessage | None = None

    async def send(self, message: EmailMessage) -> None:
        self.last_message = message
        logger.info("email.send to=%s subject=%s\n%s", message.to, message.subject, message.body)
