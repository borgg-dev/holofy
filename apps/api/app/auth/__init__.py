"""Authentication seam.

Every user-scoped path resolves the caller through an ``AuthProvider``: a bearer token in,
a persisted ``User`` out. The Protocol is the swap point — the dev-token backend here maps
a signed token to a seeded user so the API is genuinely user-scoped with no OAuth yet, and
a real Clerk/Supabase verifier drops in behind the same interface later (ADR 0004).
"""

from __future__ import annotations

from app.auth.base import AuthProvider, AuthenticatedUser
from app.auth.dev_token import DevTokenAuthProvider, mint_dev_token
from app.auth.factory import build_auth_provider

__all__ = [
    "AuthProvider",
    "AuthenticatedUser",
    "DevTokenAuthProvider",
    "build_auth_provider",
    "mint_dev_token",
]
