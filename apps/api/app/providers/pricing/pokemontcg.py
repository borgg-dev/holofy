"""Client for the open pokémontcg.io API — the multi-market price source.

Unlike TCGdex (Cardmarket/EUR only), pokémontcg.io carries *both* the US market (TCGplayer, USD)
and the EU market (Cardmarket, EUR) for a card in one response, fresh-dated. That lets Holofy show
a real US-market price when the user views in USD — instead of FX-converting the EUR — which is the
honesty gap the client-side currency toggle otherwise has.

Its card ids line up with TCGdex's for most of the catalog, but not all, so this resolves a card by
its id first and falls back to a name + collector-number search — the combination that lifts native
coverage past ~85% (the residual misses are Pokémon-Pocket cards, a digital game that doesn't trade
on either market, so "no price" is the honest answer there).

No key required for modest volume; a free ``POKEMONTCG_API_KEY`` raises the rate limit and is sent
when configured. In production this sits behind the same Redis/Postgres price cache as TCGdex — the
hot path reads cached observations, not this API on every scan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx


class PokemonTcgError(Exception):
    """Base for pokémontcg.io faults."""


class PokemonTcgPriceUnavailable(PokemonTcgError):
    """The card was found but carries no usable price on either market."""


# TCGplayer groups prices by finish; we lead with the foil finishes a collector actually holds for
# the holo cards Holofy recognizes, then fall back to normal, then whatever exists.
_TCGPLAYER_FINISH_PRIORITY = (
    "holofoil",
    "reverseHolofoil",
    "1stEditionHolofoil",
    "unlimitedHolofoil",
    "normal",
    "1stEditionNormal",
)


@dataclass(frozen=True, slots=True)
class PokemonTcgPrice:
    """A card's reading across both markets, with freshness."""

    card_id: str
    card_name: str
    eur_trend: Decimal | None
    eur_avg30: Decimal | None
    eur_low: Decimal | None
    usd_market: Decimal | None
    updated: datetime
    tcgplayer_url: str | None

    @property
    def has_any_price(self) -> bool:
        return self.eur_trend is not None or self.eur_low is not None or self.usd_market is not None


def _dec(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return d if d > 0 else None


def _parse_updated(*values: str | None) -> datetime:
    """pokémontcg.io stamps freshness as ``YYYY/MM/DD``; take the newest present, else 'now' so a
    missing stamp doesn't read as ancient."""
    best: datetime | None = None
    for v in values:
        if not v:
            continue
        try:
            d = datetime.strptime(v, "%Y/%m/%d").replace(tzinfo=UTC)
        except ValueError:
            continue
        if best is None or d > best:
            best = d
    return best or datetime.now(UTC)


def _usd_market(tcgplayer: dict) -> Decimal | None:
    prices = tcgplayer.get("prices") or {}
    if not prices:
        return None
    ordered = [f for f in _TCGPLAYER_FINISH_PRIORITY if f in prices] + [
        f for f in prices if f not in _TCGPLAYER_FINISH_PRIORITY
    ]
    for finish in ordered:
        block = prices[finish] or {}
        for key in ("market", "mid", "high"):
            d = _dec(block.get(key))
            if d is not None:
                return d
    return None


def _extract(card: dict) -> PokemonTcgPrice:
    cm = (card.get("cardmarket") or {}).get("prices") or {}
    tp = card.get("tcgplayer") or {}
    return PokemonTcgPrice(
        card_id=card.get("id", ""),
        card_name=card.get("name", ""),
        eur_trend=_dec(cm.get("trendPrice")),
        eur_avg30=_dec(cm.get("avg30")),
        eur_low=_dec(cm.get("lowPrice")) or _dec(cm.get("lowPriceExPlus")),
        usd_market=_usd_market(tp),
        updated=_parse_updated((card.get("cardmarket") or {}).get("updatedAt"), tp.get("updatedAt")),
        tcgplayer_url=tp.get("url"),
    )


class PokemonTcgClient:
    def __init__(
        self,
        *,
        api_root: str = "https://api.pokemontcg.io/v2",
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._root = api_root.rstrip("/")
        # An injected client (tests use httpx.MockTransport); otherwise build our own.
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds, headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(
        self, canonical_id: str, *, name: str | None = None, collector_number: str | None = None
    ) -> PokemonTcgPrice:
        """Resolve a card by id, then by name+number; return its multi-market price.

        Raises ``PokemonTcgPriceUnavailable`` when the card can't be matched or carries no price on
        either market — the caller treats that as a long-tail "no comp", not an error.
        """
        card = await self._get_by_id(canonical_id)
        if card is None and name:
            card = await self._search(name, collector_number)
        if card is None:
            raise PokemonTcgPriceUnavailable(f"no pokemontcg.io match for {canonical_id}")
        price = _extract(card)
        if not price.has_any_price:
            raise PokemonTcgPriceUnavailable(f"no market price for {canonical_id}")
        return price

    async def _get_by_id(self, canonical_id: str) -> dict | None:
        try:
            resp = await self._client.get(f"{self._root}/cards/{canonical_id}")
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        return resp.json().get("data") or None

    async def _search(self, name: str, collector_number: str | None) -> dict | None:
        # Numerator only — pokémontcg.io's ``number`` is the bare printed number ("58"), not "58/102".
        numerator = "".join(c for c in (collector_number or "").split("/")[0] if c.isdigit())
        safe_name = name.replace('"', "").strip()
        query = f'name:"{safe_name}"' + (f" number:{numerator}" if numerator else "")
        try:
            resp = await self._client.get(
                f"{self._root}/cards", params={"q": query, "pageSize": 10}
            )
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json().get("data") or []
        # Prefer an exact printed-number match; otherwise the first priced hit.
        for card in data:
            if numerator and str(card.get("number", "")).lstrip("0") == numerator.lstrip("0"):
                if _extract(card).has_any_price:
                    return card
        for card in data:
            if _extract(card).has_any_price:
                return card
        return None
