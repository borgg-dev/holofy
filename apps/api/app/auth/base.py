"""The authentication Protocol the API depends on.

An ``AuthProvider`` turns a raw bearer credential into the ``(auth_provider, auth_subject)``
identity pair the persistence layer keys a ``User`` on. It deliberately does *not* touch the
database: resolving (and lazily provisioning) the ``User`` is the dependency's job, so the
same provider works whether identity comes from a dev token, Clerk, or a future in-house
issuer. Verification failures raise the API's auth errors so they render in the one envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AuthenticatedUser:
    """The identity a credential resolves to, before it is mapped to a ``User`` row.

    ``provider`` / ``subject`` are exactly the columns ``User.auth_provider`` /
    ``User.auth_subject`` are uniquely paired on, so the dependency can find-or-create the
    user deterministically.
    """

    provider: str
    subject: str
    # When the credential was issued (epoch seconds, sub-second precision), if it carries that — the
    # session bearer does. ``get_current_user`` compares it to ``User.sessions_valid_from`` to honour
    # a revocation. ``None`` for credentials without an issue time (the dev token), which are simply
    # not epoch-revocable.
    issued_at: float | None = None


@runtime_checkable
class AuthProvider(Protocol):
    def authenticate(self, credential: str) -> AuthenticatedUser:
        """Verify a bearer credential and return its identity.

        Raises ``InvalidCredentialError`` if the credential is present but unusable; the
        caller is responsible for the missing-credential (``NotAuthenticatedError``) case.
        """
        ...
