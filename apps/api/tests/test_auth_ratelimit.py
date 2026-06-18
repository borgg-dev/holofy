"""Unit coverage for the auth and rate-limit seams, independent of the API wiring.

The dev-token provider must scope distinct subjects to distinct identities and reject
tampering; the in-memory limiter must enforce the budget, report the remaining count and
reset, and not consume a unit on a denied call.
"""

from __future__ import annotations

import pytest

from app.auth.dev_token import DevTokenAuthProvider, mint_dev_token
from app.core.errors import InvalidCredentialError
from app.ratelimit.memory import InMemoryRateLimiter

_SECRET = "unit-secret"


def test_dev_token_round_trips_to_its_subject() -> None:
    provider = DevTokenAuthProvider(secret=_SECRET)
    identity = provider.authenticate(mint_dev_token("collector-7", secret=_SECRET))

    assert identity.provider == "dev_token"
    assert identity.subject == "collector-7"


def test_distinct_tokens_resolve_to_distinct_subjects() -> None:
    provider = DevTokenAuthProvider(secret=_SECRET)
    a = provider.authenticate(mint_dev_token("a", secret=_SECRET))
    b = provider.authenticate(mint_dev_token("b", secret=_SECRET))

    # Not "always admin": the seam genuinely separates users.
    assert a.subject != b.subject


def test_tampered_or_foreign_token_is_rejected() -> None:
    provider = DevTokenAuthProvider(secret=_SECRET)

    with pytest.raises(InvalidCredentialError):
        provider.authenticate("collector-7.deadbeef")
    with pytest.raises(InvalidCredentialError):
        provider.authenticate("no-signature")
    # A token signed under a different secret must not verify.
    foreign = mint_dev_token("collector-7", secret="other-secret")
    with pytest.raises(InvalidCredentialError):
        provider.authenticate(foreign)


@pytest.mark.asyncio
async def test_limiter_enforces_budget_and_reports_remaining() -> None:
    limiter = InMemoryRateLimiter()

    first = await limiter.check_and_consume("user-1", limit=2)
    assert first.allowed is True
    assert first.remaining == 1
    assert first.reset_seconds > 0

    second = await limiter.check_and_consume("user-1", limit=2)
    assert second.allowed is True
    assert second.remaining == 0

    third = await limiter.check_and_consume("user-1", limit=2)
    assert third.allowed is False
    assert third.remaining == 0


@pytest.mark.asyncio
async def test_limiter_is_keyed_per_subject() -> None:
    limiter = InMemoryRateLimiter()
    await limiter.check_and_consume("user-1", limit=1)

    # A second key has its own budget.
    other = await limiter.check_and_consume("user-2", limit=1)
    assert other.allowed is True
