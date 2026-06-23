"""The pricing read-through cache: serve hits and misses from memory, refetch after TTL.

The inner provider counts its calls so we can assert the cache actually shields the upstream — the
whole point on the Vault hot path. A miss is cached too (a long-tail card must not re-hit upstream
every view) but for a shorter window, and the caller's PriceUnavailableError is preserved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.errors import PriceUnavailableError
from app.providers.pricing.cache import CachedPricingProvider
from app.schemas.cards import PriceQuote


class _CountingProvider:
    def __init__(self, *, missing: set[str] | None = None) -> None:
        self.calls = 0
        self._missing = missing or set()

    async def price(self, canonical_id, *, name=None, collector_number=None):  # noqa: ANN001
        self.calls += 1
        if canonical_id in self._missing:
            raise PriceUnavailableError("no price", details={"canonical_id": canonical_id})
        return PriceQuote(
            canonical_id=canonical_id, value=Decimal("10.00"), basis="trend",
            source="test", as_of=datetime.now(UTC), age_hours=1.0,
        )


@pytest.mark.asyncio
async def test_hit_is_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachedPricingProvider(inner, ttl_seconds=1000)

    a = await cache.price("base1-4")
    b = await cache.price("base1-4")

    assert a.value == b.value
    assert inner.calls == 1  # second read came from the cache


@pytest.mark.asyncio
async def test_distinct_cards_each_fetch_once() -> None:
    inner = _CountingProvider()
    cache = CachedPricingProvider(inner, ttl_seconds=1000)

    for cid in ["a", "b", "a", "b", "a"]:
        await cache.price(cid)

    assert inner.calls == 2


@pytest.mark.asyncio
async def test_miss_is_cached_and_reraised() -> None:
    inner = _CountingProvider(missing={"ghost"})
    cache = CachedPricingProvider(inner, ttl_seconds=1000)

    for _ in range(3):
        with pytest.raises(PriceUnavailableError):
            await cache.price("ghost")

    assert inner.calls == 1  # the unpriceable card hit upstream once, then served the cached miss


@pytest.mark.asyncio
async def test_expired_entry_refetches() -> None:
    inner = _CountingProvider()
    cache = CachedPricingProvider(inner, ttl_seconds=0)  # everything immediately stale

    await cache.price("base1-4")
    await cache.price("base1-4")

    assert inner.calls == 2
