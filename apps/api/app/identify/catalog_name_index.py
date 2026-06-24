"""Accent-insensitive recall over a locale's catalog — the safety net for diacritic-blind OCR.

TCGdex's ``name=`` search is a *contains* match but accent-**sensitive**: the OCR reliably reads
a French/German card's letters yet drops the diacritics, so "Salameche" never matches the catalog
name "Salamèche" and the scan resolves to *zero* candidates. There is no server-side
accent-insensitive operator (``like:`` returns nothing), so we recover it locally: pull the locale's
full card-brief list once, de-accent every name, and match the de-accented OCR read against it.

The full list is ~20k tiny briefs (~2 MB) per locale — too heavy for the scan hot path, so it is
fetched once, cached in-process with a long TTL, and warmed at startup. It only does work when the
direct (accent-sensitive) search comes back empty, which is exactly the accented-name case.
"""

from __future__ import annotations

import asyncio
import logging
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.identify.collector_number import parse_collector_number
from app.providers.pricing.tcgdex import TcgdexClient

logger = logging.getLogger("holofy.recognition")

# The brief list is effectively static (the catalog changes on set releases, not minute to
# minute); a day-long TTL keeps it fresh enough while making the fetch a once-per-day event.
_DEFAULT_TTL_SECONDS = 24 * 60 * 60


def deaccent(text: str) -> str:
    """Fold a name to accent-free, case-insensitive tokens: "Salamèche" → "salameche".

    NFKD decomposition splits an accented letter into its base plus a combining mark (é → e +
    ◌́, ç → c + ◌̧); dropping the combining marks leaves the bare ASCII letters the OCR actually
    produces. Casefold makes the compare case-insensitive to match TCGdex's own search.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def _tokens(name: str) -> frozenset[str]:
    return frozenset(deaccent(name).split())


def _name_corroborates(read_tokens: frozenset[str], card_tokens: frozenset[str]) -> bool:
    """Token-subset either direction — the same loose rule the resolver uses, on de-accented
    tokens. The OCR may drop a suffix the print set smaller ("ex", "V") or read only the core
    name, so one side's words being a subset of the other's still corroborates."""
    if not read_tokens or not card_tokens:
        return False
    return read_tokens <= card_tokens or card_tokens <= read_tokens


@dataclass(frozen=True, slots=True)
class _Brief:
    card_id: str
    numerator: int | None
    tokens: frozenset[str]


@dataclass
class _LocaleCache:
    briefs: list[_Brief]
    fetched_at: float


class CatalogNameIndex:
    """De-accented name → card-id recall, cached per locale.

    ``lookup`` returns the ids of every brief whose de-accented name corroborates the read, so the
    catalog index can resolve them to full printings. A failed or empty fetch yields no matches —
    the caller simply gets today's behaviour (an honest empty result), never an error.
    """

    def __init__(
        self,
        client: TcgdexClient,
        *,
        locales: Sequence[str] = ("en",),
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._locales = tuple(locales) or ("en",)
        self._ttl = ttl_seconds
        self._caches: dict[str, _LocaleCache] = {}
        # One lock per locale so a concurrent burst of scans triggers a single bulk fetch, and a
        # fetch for one locale never blocks another.
        self._locks: dict[str, asyncio.Lock] = {loc: asyncio.Lock() for loc in self._locales}

    async def warm(self) -> None:
        """Prefetch every configured locale so the first real scan never pays the bulk fetch.

        Best-effort: a locale that fails to load is simply left cold and lazily retried on demand.
        Meant to run as a fire-and-forget background task at startup.
        """
        await asyncio.gather(
            *(self._ensure(locale) for locale in self._locales), return_exceptions=True
        )

    async def lookup(self, name: str, locale: str, *, numerator: int | None = None) -> list[str]:
        """Card ids whose de-accented name corroborates ``name`` (optionally pinned to a
        collector numerator). Empty when the locale isn't cached and can't be fetched."""
        cache = await self._ensure(locale)
        if cache is None:
            return []
        read_tokens = _tokens(name)
        if not read_tokens:
            return []
        hits = [b for b in cache.briefs if _name_corroborates(read_tokens, b.tokens)]
        if numerator is not None:
            pinned = [b for b in hits if b.numerator == numerator]
            # Keep the numerator pin only when it leaves something — else fall back to the
            # name-only hits, mirroring the direct-search recall-over-precision stance.
            hits = pinned or hits
        return [b.card_id for b in hits]

    async def _ensure(self, locale: str) -> _LocaleCache | None:
        cached = self._caches.get(locale)
        if cached is not None and (time.monotonic() - cached.fetched_at) < self._ttl:
            return cached
        lock = self._locks.setdefault(locale, asyncio.Lock())
        async with lock:
            # Re-check under the lock: another coroutine may have filled it while we waited.
            cached = self._caches.get(locale)
            if cached is not None and (time.monotonic() - cached.fetched_at) < self._ttl:
                return cached
            try:
                raw = await self._client.list_all_cards(locale=locale)
            except Exception as exc:  # noqa: BLE001 — best-effort; any failure leaves the cache cold
                logger.warning("catalog.name_index fetch_failed locale=%s — %s", locale, exc)
                return None
            briefs = [_to_brief(item) for item in raw]
            cache = _LocaleCache(
                briefs=[b for b in briefs if b is not None], fetched_at=time.monotonic()
            )
            self._caches[locale] = cache
            logger.info("catalog.name_index loaded locale=%s briefs=%d", locale, len(cache.briefs))
            return cache


def _to_brief(item: dict) -> _Brief | None:
    card_id = item.get("id")
    name = item.get("name")
    if not card_id or not name:
        return None
    number = parse_collector_number(str(item.get("localId", "")))
    return _Brief(
        card_id=card_id,
        numerator=number.numerator if number else None,
        tokens=_tokens(name),
    )
