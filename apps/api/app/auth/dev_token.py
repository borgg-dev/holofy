"""HMAC-signed dev tokens — real auth without an identity provider yet.

A dev token is ``<subject>.<signature>`` where the signature is an HMAC-SHA256 of the
subject under the configured secret. It is *not* "always admin": each token names a distinct
subject, so two tokens scope to two different users, and a forged or tampered token fails
verification. This is enough to build and test genuinely user-scoped endpoints; it is
replaced wholesale by Clerk/Supabase token verification behind the same ``AuthProvider``.
"""

from __future__ import annotations

import hmac
from hashlib import sha256

from app.auth.base import AuthenticatedUser
from app.core.errors import InvalidCredentialError

PROVIDER_NAME = "dev_token"
_SEPARATOR = "."


def _sign(subject: str, secret: str) -> str:
    return hmac.new(secret.encode(), subject.encode(), sha256).hexdigest()


def mint_dev_token(subject: str, *, secret: str) -> str:
    """Issue a token for a subject — the seam a dev/test harness uses in place of a login."""
    return f"{subject}{_SEPARATOR}{_sign(subject, secret)}"


class DevTokenAuthProvider:
    def __init__(self, *, secret: str) -> None:
        self._secret = secret

    def authenticate(self, credential: str) -> AuthenticatedUser:
        subject, _, signature = credential.partition(_SEPARATOR)
        if not subject or not signature:
            raise InvalidCredentialError("Malformed dev token.")
        expected = _sign(subject, self._secret)
        # Constant-time compare so a forged token can't be teased out by timing.
        if not hmac.compare_digest(signature, expected):
            raise InvalidCredentialError("Dev token signature does not verify.")
        return AuthenticatedUser(provider=PROVIDER_NAME, subject=subject)
