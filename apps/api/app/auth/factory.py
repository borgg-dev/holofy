"""Auth provider selection by configuration — the single place a backend is chosen.

Mirrors the provider factory pattern: call sites depend on the ``AuthProvider`` Protocol,
so swapping ``HOLOFY_AUTH_PROVIDER`` from the dev token to a real issuer is a config change,
not a code change at the endpoints.
"""

from __future__ import annotations

from app.auth.base import AuthProvider
from app.auth.dev_token import DevTokenAuthProvider
from app.config import AuthBackend, Settings


def build_auth_provider(settings: Settings) -> AuthProvider:
    match settings.auth_provider:
        case AuthBackend.DEV_TOKEN:
            return DevTokenAuthProvider(secret=settings.auth_dev_secret)
