"""Request/response contract for password accounts — register, login, and the session token.

Email is normalized (trimmed + lowercased) at the boundary so the login handle and the token
subject are stable, and validated with a deliberately simple shape check (no ``email-validator``
dependency): we only need "looks like an address", not RFC-perfect parsing. The password floor
is 8 characters — enough to be a real credential without dictating a policy the client can't
explain. The response never echoes the hash or any internal id beyond the opaque user id.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Pragmatic "looks like an email" check: one @, a dotted domain, no whitespace. Not RFC 5322 —
# the goal is to reject obvious junk at the edge, not to be the authority on address syntax.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _EmailMixin(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class RegisterRequest(_EmailMixin):
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(_EmailMixin):
    # No min_length on login (an old/short password must still be *checkable*); the value is
    # only ever compared against the stored hash, never stored.
    password: str = Field(min_length=1, max_length=200)


class AuthUser(BaseModel):
    """The account identity the client holds onto — opaque id + the login email."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str


class AuthTokenResponse(BaseModel):
    """A successful register/login: the bearer to send, when it expires, and who it's for."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the token expires
    user: AuthUser
