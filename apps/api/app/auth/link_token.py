"""Signed, expiring, single-purpose links — the password-reset and email-verify tokens.

Same construction as the session bearer (``base64url(payload).hmac``) but for one-shot links: the
payload is ``{sub, purpose, iat, exp, fp}``. Two guards make these safe to email:

- **purpose** — a reset token can't be replayed as a verify token (or vice-versa); the verifier
  demands the exact purpose it expects.
- **fingerprint (fp)** — binds the token to a piece of mutable server state so it becomes single-use
  without a server-side token table. For a reset we fingerprint the *current* password hash: the
  moment the password changes (the reset succeeds, or the user changes it another way) every
  outstanding reset link stops verifying. For verify we fingerprint the email being confirmed.

HMAC-signed under the auth secret, so the link can't be forged or its claims tampered with, and it
expires on its own. No secret material is in the payload — only an opaque fingerprint we recompute.
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256

from app.core.errors import InvalidCredentialError

_SEPARATOR = "."


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), sha256).digest())


def fingerprint(*parts: str) -> str:
    """An opaque, stable digest of server state a token is bound to (e.g. the password hash). Hashed
    so the token never carries the raw value."""
    return _b64(sha256("\x1f".join(parts).encode("utf-8")).digest())[:16]


def issue_link_token(
    subject: str, *, purpose: str, secret: str, ttl_seconds: int, fp: str = ""
) -> str:
    now = int(time.time())
    payload = {"sub": subject, "purpose": purpose, "iat": now, "exp": now + int(ttl_seconds), "fp": fp}
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}{_SEPARATOR}{_sign(payload_b64, secret)}"


def verify_link_token(token: str, *, purpose: str, secret: str) -> tuple[str, str]:
    """Verify a token's signature, purpose and expiry; return ``(subject, fingerprint)``.

    The *fingerprint* is returned rather than checked here because the caller needs the subject to
    load the account before it can recompute what the fingerprint should be (it's derived from
    mutable server state like the password hash). The caller then compares it with
    ``check_fingerprint`` — a constant-time match. A bad signature / wrong purpose / expired token
    raises ``InvalidCredentialError``.
    """
    payload_b64, _, signature = token.partition(_SEPARATOR)
    if not payload_b64 or not signature:
        raise InvalidCredentialError("Malformed link token.")
    if not hmac.compare_digest(signature, _sign(payload_b64, secret)):
        raise InvalidCredentialError("Link token signature does not verify.")
    try:
        payload = json.loads(_unb64(payload_b64))
        subject = str(payload["sub"])
        token_purpose = str(payload["purpose"])
        exp = int(payload["exp"])
        token_fp = str(payload.get("fp", ""))
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidCredentialError("Link token payload is unreadable.") from exc
    if token_purpose != purpose:
        raise InvalidCredentialError("Link token is for a different purpose.")
    if exp < int(time.time()):
        raise InvalidCredentialError("Link token has expired.")
    return subject, token_fp


def check_fingerprint(token_fp: str, expected: str) -> bool:
    """Constant-time fingerprint compare, so a guessed value can't be teased out by timing."""
    return hmac.compare_digest(token_fp, expected)
