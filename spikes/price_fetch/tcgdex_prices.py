"""Spike A — proof that a no-auth € price path exists via the TCGdex catalog API.

This is a throwaway spike, not production code. It exercises the one question that
gates the whole pricing service: can we read a Cardmarket EUR price for a specific
card, including its freshness, without holding a Cardmarket/TCGPlayer key? The real
service (see ADR 0001) will cache nightly into Postgres rather than hit this on the
hot path.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import httpx

API_ROOT: Final = "https://api.tcgdex.net/v2"
_REQUEST_TIMEOUT: Final = httpx.Timeout(10.0, connect=5.0)


class PriceUnavailable(Exception):
    """Card resolved but carries no Cardmarket pricing (long-tail / unlisted card)."""


class CardNotFound(Exception):
    """No catalog entry for the requested (set, localId)."""


@dataclass(frozen=True, slots=True)
class CardmarketPrice:
    card_id: str
    card_name: str
    trend_eur: Decimal | None
    avg30_eur: Decimal | None
    low_eur: Decimal | None
    updated: datetime
    product_id: int | None
    locale: str

    @property
    def staleness(self) -> str:
        age = datetime.now(timezone.utc) - self.updated
        hours = age.total_seconds() / 3600
        if hours < 36:
            return f"{hours:.0f}h old"
        return f"{age.days}d old"

    @property
    def display_value(self) -> Decimal | None:
        """What the UI leads with: Cardmarket's smoothed ``trend`` (the guide price a
        German collector sees on the listing page), falling back to the 30-day average
        when trend is absent. The raw ``avg7`` is deliberately not used — it whipsaws on
        thin volume for high-value singles.
        """
        return self.trend_eur if self.trend_eur is not None else self.avg30_eur


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    # JSON gives floats; round-trip through str so we don't inherit binary-float noise
    # on a value we display as currency.
    return Decimal(str(value))


def fetch_cardmarket_price(
    card_id: str,
    *,
    locale: str = "en",
    client: httpx.Client | None = None,
) -> CardmarketPrice:
    """Resolve a TCGdex card id (e.g. ``base1-4``) to its Cardmarket EUR pricing.

    Raises ``CardNotFound`` for an unknown id and ``PriceUnavailable`` when the card
    exists but TCGdex holds no Cardmarket entry for it.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=_REQUEST_TIMEOUT)
    try:
        response = client.get(f"{API_ROOT}/{locale}/cards/{card_id}")
        if response.status_code == 404:
            raise CardNotFound(card_id)
        response.raise_for_status()
        card = response.json()
    finally:
        if owns_client:
            client.close()

    cardmarket = (card.get("pricing") or {}).get("cardmarket")
    if not cardmarket:
        raise PriceUnavailable(card_id)

    return CardmarketPrice(
        card_id=card["id"],
        card_name=card["name"],
        trend_eur=_to_decimal(cardmarket.get("trend")),
        avg30_eur=_to_decimal(cardmarket.get("avg30")),
        low_eur=_to_decimal(cardmarket.get("low")),
        updated=_parse_timestamp(cardmarket["updated"]),
        product_id=cardmarket.get("idProduct"),
        locale=locale,
    )


def _parse_timestamp(raw: str) -> datetime:
    # TCGdex emits RFC 3339 with a trailing 'Z'; fromisoformat handles it from 3.11+
    # but we normalise defensively so the spike runs on any interpreter ≥3.11.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _render(price: CardmarketPrice) -> str:
    value = price.display_value
    headline = f"€{value:,.2f}" if value is not None else "—"
    basis = "trend" if price.trend_eur is not None else "30-day avg"
    cm_url = (
        f"https://www.cardmarket.com/en/Pokemon/Products/Singles?idProduct={price.product_id}"
        if price.product_id
        else "n/a"
    )
    return "\n".join(
        [
            f"{price.card_name}  ({price.card_id})",
            f"  Cardmarket value : {headline}  [{basis}]",
            f"  30-day average   : "
            + (f"€{price.avg30_eur:,.2f}" if price.avg30_eur is not None else "—"),
            f"  lowest available : "
            + (f"€{price.low_eur:,.2f}" if price.low_eur is not None else "—"),
            f"  provenance       : Cardmarket EUR, via TCGdex catalog ({price.locale})",
            f"  freshness        : updated {price.updated.isoformat()} ({price.staleness})",
            f"  source listing   : {cm_url}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a card's Cardmarket EUR price via TCGdex (no API key).",
    )
    parser.add_argument(
        "card_id",
        nargs="?",
        default="base1-4",
        help="TCGdex card id, e.g. base1-4 (Base Set Charizard 4/102)",
    )
    parser.add_argument("--locale", default="en")
    args = parser.parse_args(argv)

    try:
        price = fetch_cardmarket_price(args.card_id, locale=args.locale)
    except CardNotFound as exc:
        print(f"No catalog entry for '{exc}'.", file=sys.stderr)
        return 2
    except PriceUnavailable as exc:
        print(f"'{exc}' has no Cardmarket pricing (long-tail or unlisted).", file=sys.stderr)
        return 3
    except httpx.HTTPError as exc:
        print(f"Upstream fetch failed: {exc}", file=sys.stderr)
        return 1

    print(_render(price))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
