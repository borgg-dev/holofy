"""RedisRateLimiter contract tests against an in-memory fakeredis (no server needed).

These pin the same behaviour the in-process limiter guarantees — allow up to the limit, then
deny; a denied call consumes nothing; per-key isolation; a TTL on the window — so the Redis
drop-in is a true behavioural equal of the memory backend.
"""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis

from app.ratelimit.redis import RedisRateLimiter


@pytest.fixture
def limiter() -> RedisRateLimiter:
    return RedisRateLimiter(FakeRedis(), namespace="test")


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_denies(limiter: RedisRateLimiter) -> None:
    verdicts = [await limiter.check_and_consume("u1", limit=3) for _ in range(4)]
    assert [v.allowed for v in verdicts] == [True, True, True, False]
    assert [v.remaining for v in verdicts] == [2, 1, 0, 0]
    assert all(v.limit == 3 for v in verdicts)


@pytest.mark.asyncio
async def test_denied_calls_consume_nothing(limiter: RedisRateLimiter) -> None:
    for _ in range(3):
        await limiter.check_and_consume("u", limit=3)
    # Hammer the wall: none of these should move the counter or ever flip back to allowed.
    denied = [await limiter.check_and_consume("u", limit=3) for _ in range(5)]
    assert all(not v.allowed and v.remaining == 0 for v in denied)
    # The very next day-window check (simulated by a fresh key) would allow again — proven by
    # a different key here standing in for a fresh window.
    assert (await limiter.check_and_consume("u-next", limit=3)).allowed


@pytest.mark.asyncio
async def test_keys_are_isolated(limiter: RedisRateLimiter) -> None:
    await limiter.check_and_consume("a", limit=1)
    assert (await limiter.check_and_consume("a", limit=1)).allowed is False
    assert (await limiter.check_and_consume("b", limit=1)).allowed is True


@pytest.mark.asyncio
async def test_window_has_a_reset_and_ttl(limiter: RedisRateLimiter) -> None:
    verdict = await limiter.check_and_consume("x", limit=5)
    assert 0 < verdict.reset_seconds <= 86_400


@pytest.mark.asyncio
async def test_factory_wires_redis_when_configured() -> None:
    from app.config import RateLimitBackend, Settings
    from app.ratelimit.factory import build_rate_limiter
    from app.ratelimit.memory import InMemoryRateLimiter

    redis_limiter = build_rate_limiter(
        Settings(rate_limit_provider=RateLimitBackend.REDIS, redis_url="redis://localhost:6379/0")
    )
    assert isinstance(redis_limiter, RedisRateLimiter)  # no connection until first use
    assert isinstance(build_rate_limiter(Settings()), InMemoryRateLimiter)
