"""Stateless, expiring session tokens — the real bearer a login issues.

A session token is ``base64url(payload).base64url(hmac_sha256(payload))`` where the payload is
a tiny JSON ``{"sub", "iat", "exp"}``. It is HMAC-signed under the auth secret, so it cannot
be forged or tampered with, and it carries its own expiry, so a leaked token stops working on
its own. This is the production bearer the dev token (``app.auth.dev_token``) stood in for:
issued only after a password check, scoped to one user's stable subject, and verified behind
the same ``AuthProvider`` seam — endpoints never learn how the bearer was minted.

Stateless by design (no server-side session table): a logout is client-side token disposal,
and the short-ish TTL bounds a stolen token. A server-side revocation list drops in behind the
same provider if per-session revocation is ever needed.
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256

from app.auth.base import AuthenticatedUser
from app.core.errors import InvalidCredentialError

PROVIDER_NAME = "session"
_SEPARATOR = "."


def issue_session_token(subject: str, *, secret: str, ttl_seconds: int) -> str:
    """Mint a signed, expiring token for ``subject`` (the user's stable auth subject)."""
    now = int(time.time())
    payload = {"sub": subject, "iat": now, "exp": now + int(ttl_seconds)}
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}{_SEPARATOR}{_sign(payload_b64, secret)}"


class SessionTokenAuthProvider:
    """Verifies a session token's signature and expiry, returning its subject."""

    def __init__(self, *, secret: str) -> None:
        self._secret = secret

    def authenticate(self, credential: str) -> AuthenticatedUser:
        payload_b64, _, signature = credential.partition(_SEPARATOR)
        if not payload_b64 or not signature:
            raise InvalidCredentialError("Malformed session token.")
        expected = _sign(payload_b64, self._secret)
        # Constant-time compare so a forged token can't be teased out by timing.
        if not hmac.compare_digest(signature, expected):
            raise InvalidCredentialError("Session token signature does not verify.")
        try:
            payload = json.loads(_unb64(payload_b64))
            subject = str(payload["sub"])
            exp = int(payload["exp"])
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidCredentialError("Session token payload is unreadable.") from exc
        if exp < int(time.time()):
            raise InvalidCredentialError("Session token has expired.")
        return AuthenticatedUser(provider=PROVIDER_NAME, subject=subject)


def _sign(payload_b64: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload_b64.encode(), sha256).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
