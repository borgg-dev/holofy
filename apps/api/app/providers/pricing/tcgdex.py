"""Shared TCGdex Cardmarket pricing client — the production home for the helper that
Phase-0 spikes A and B each carried their own copy of.

TCGdex is the open catalog API (no key) that surfaces Cardmarket EUR price points per
card. It is *not* called on the hot path in production: the architecture (§4) syncs the
catalog nightly into Postgres and serves prices from a Redis cache. This client is the
thing that populates that cache and the fallback for cold lookups; it speaks to the same
endpoint the spikes proved out.

The HTTP layer is injectable (``client=``) so tests drive it with ``httpx.MockTransport``
and the live API is never touched in CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import httpx

_DEFAULT_API_ROOT: Final = "https://api.tcgdex.net/v2"


class TcgdexError(Exception):
    """Base for failures originating in the TCGdex client."""


class CardNotFound(TcgdexError):
    """No catalog entry for the requested card id."""


class PriceUnavailable(TcgdexError):
    """Card resolved but carries no Cardmarket pricing (long-tail / unlisted card)."""


@dataclass(frozen=True, slots=True)
class CardmarketPrice:
    """A point-in-time Cardmarket EUR reading for one card, with its freshness.

    The freshness fields are load-bearing, not cosmetic: TCGdex refreshes Cardmarket data
    daily, so the UI shows the update timestamp and treats stale prices accordingly.
    """

    card_id: str
    card_name: str
    trend_eur: Decimal | None
    avg30_eur: Decimal | None
    low_eur: Decimal | None
    updated: datetime
    product_id: int | None
    locale: str

    @property
    def display_value(self) -> Decimal | None:
        """What the UI leads with: Cardmarket's smoothed ``trend`` (the guide price a
        German collector sees on the listing page), falling back to the 30-day average
        when trend is absent. The raw ``avg7`` is deliberately not used — it whipsaws on
        thin volume for high-value singles.
        """
        return self.trend_eur if self.trend_eur is not None else self.avg30_eur

    @property
    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.updated).total_seconds() / 3600

    @property
    def listing_url(self) -> str | None:
        if self.product_id is None:
            return None
        return (
            "https://www.cardmarket.com/en/Pokemon/Products/Singles"
            f"?idProduct={self.product_id}"
        )


def to_decimal(value: object) -> Decimal | None:
    """Coerce a JSON number to ``Decimal`` for currency use.

    JSON gives floats; round-trip through ``str`` so we don't inherit binary-float noise
    on a value we display as money.
    """
    if value is None:
        return None
    return Decimal(str(value))


def _parse_timestamp(raw: str) -> datetime:
    # TCGdex emits RFC 3339 with a trailing 'Z'; normalise to an aware datetime.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _price_from_card(card: dict, *, locale: str) -> CardmarketPrice:
    cardmarket = (card.get("pricing") or {}).get("cardmarket")
    if not cardmarket:
        raise PriceUnavailable(card.get("id", "?"))
    return CardmarketPrice(
        card_id=card["id"],
        card_name=card["name"],
        trend_eur=to_decimal(cardmarket.get("trend")),
        avg30_eur=to_decimal(cardmarket.get("avg30")),
        low_eur=to_decimal(cardmarket.get("low")),
        updated=_parse_timestamp(cardmarket["updated"]),
        product_id=cardmarket.get("idProduct"),
        locale=locale,
    )


class TcgdexClient:
    """Thin, typed wrapper over the TCGdex card endpoint.

    Construct once and reuse — it owns an ``httpx.AsyncClient`` for connection pooling and
    must be closed via ``aclose()`` (or used as an async context manager). Pass ``client=``
    to inject a transport in tests.
    """

    def __init__(
        self,
        *,
        api_root: str = _DEFAULT_API_ROOT,
        locale: str = "en",
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_root = api_root.rstrip("/")
        self._locale = locale
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=5.0)
        )

    async def __aenter__(self) -> "TcgdexClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_cardmarket_price(
        self, card_id: str, *, locale: str | None = None
    ) -> CardmarketPrice:
        """Resolve a TCGdex card id (e.g. ``origins-12``) to its Cardmarket EUR pricing.

        Raises ``CardNotFound`` for an unknown id and ``PriceUnavailable`` when the card
        exists but TCGdex holds no Cardmarket entry for it. Both are domain conditions, not
        transport faults; ``httpx.HTTPError`` propagates for the latter.
        """
        locale = locale or self._locale
        response = await self._client.get(f"{self._api_root}/{locale}/cards/{card_id}")
        if response.status_code == 404:
            raise CardNotFound(card_id)
        response.raise_for_status()
        return _price_from_card(response.json(), locale=locale)
