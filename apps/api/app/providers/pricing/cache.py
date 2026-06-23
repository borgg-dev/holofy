"""A TTL read-through cache in front of any ``PricingProvider``.

Pricing runs on the hot path — every Vault view values every held card — and the real sources
(pokémontcg.io, TCGdex) are rate-limited network calls. Without a cache, a 20-card Vault would fire
dozens of upstream requests per view, both slow and quick to trip a keyless rate limit. This wraps
the real provider so each card is fetched at most once per TTL and served from memory after; a
typical view then makes zero upstream calls.

It caches *misses* too — a long-tail or Pokémon-Pocket card that no market carries would otherwise
re-hit the upstream on every single view forever. The miss is remembered (for a shorter window, so
a newly-listed card still gets picked up) and re-raised, so the caller's honest "no price yet" path
is unchanged.

In-process by design: prod runs a single API instance, so a shared store buys nothing here and the
cache simply warms after a restart. The price *history* (value-over-time) is a separate concern,
persisted to ``PriceObservation`` by the snapshot job — this is only the request cache.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.errors import CardNotFoundError, PriceUnavailableError
from app.providers.base import PricingProvider
from app.schemas.cards import PriceQuote

# A miss is cached far shorter than a hit: a card with no comp today may get listed tomorrow, and we
# don't want to blind ourselves to it for the full hit TTL — but we still avoid re-hitting upstream
# on every view in the meantime.
_MISS_TTL_FRACTION = 0.25


@dataclass(frozen=True, slots=True)
class _Entry:
    quote: PriceQuote | None  # None == a cached miss (no price for this card)
    expires_at: float


class CachedPricingProvider:
    """Wrap a ``PricingProvider`` with an in-memory TTL cache (hits and misses)."""

    def __init__(
        self, inner: PricingProvider, *, ttl_seconds: float = 43200.0, max_entries: int = 60000
    ) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._miss_ttl = ttl_seconds * _MISS_TTL_FRACTION
        self._max_entries = max_entries
        self._cache: dict[str, _Entry] = {}

    async def price(
        self, canonical_id: str, *, name: str | None = None, collector_number: str | None = None
    ) -> PriceQuote:
        now = time.monotonic()
        entry = self._cache.get(canonical_id)
        if entry is not None and entry.expires_at > now:
            if entry.quote is None:
                raise PriceUnavailableError(
                    "No market pricing for this card.", details={"canonical_id": canonical_id}
                )
            return entry.quote

        try:
            quote = await self._inner.price(canonical_id, name=name, collector_number=collector_number)
        except (PriceUnavailableError, CardNotFoundError):
            # Remember the miss (shorter TTL) so an unpriceable card stops hammering upstream.
            self._store(canonical_id, _Entry(quote=None, expires_at=now + self._miss_ttl))
            raise
        self._store(canonical_id, _Entry(quote=quote, expires_at=now + self._ttl))
        return quote

    def _store(self, key: str, entry: _Entry) -> None:
        if len(self._cache) >= self._max_entries and key not in self._cache:
            # Cheap bound: drop already-expired entries; if none, clear (a cold rewarm is fine and
            # far simpler than an LRU for a catalog that fits comfortably under the cap anyway).
            now = time.monotonic()
            self._cache = {k: e for k, e in self._cache.items() if e.expires_at > now}
            if len(self._cache) >= self._max_entries:
                self._cache.clear()
        self._cache[key] = entry

    async def aclose(self) -> None:
        closer = getattr(self._inner, "aclose", None)
        if closer is not None:
            await closer()
