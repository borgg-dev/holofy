"""Spike B — proof that name/art alone cannot price a card, and that the
``(set, collector number, variant)`` tuple is the disambiguator.

The killer accuracy problem: many cards share an exact name and even the exact
artwork (Mitsuhiro Arita's Base Set Charizard was reprinted unchanged into Base Set 2
and Evolutions), yet their Cardmarket € prices differ by orders of magnitude. An
artwork/embedding match can land on the right *name* and still be ~2000× wrong on
*value*. The ground truth that resolves the variant is the printed set symbol plus the
bottom-corner collector number (e.g. "4/102") — exactly what an OCR/classify step
recovers from the card and what this tool keys on.

This is a throwaway spike, not production code. It hits the open TCGdex catalog API
(no key; same source proven in Spike A) to enumerate every printing that shares a name,
resolve each to its variant tuple + € price, and quantify the spread. The production
recognition service (ADR 0002) narrows candidates by artwork, then disambiguates against
this same catalog by collector number + set symbol, and surfaces the price delta to the
user when confidence is low.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

import httpx

API_ROOT: Final = "https://api.tcgdex.net/v2"
_REQUEST_TIMEOUT: Final = httpx.Timeout(10.0, connect=5.0)

# Cardmarket exposes a base trend and a parallel "-holo" trend in the same block. For a
# card whose base printing is the holo (most vintage rares), the "-holo" series tracks
# the *reverse*-holo variant; the disambiguation tuple has to distinguish them because
# the spread between them is itself material.
_VARIANT_PRIORITY: Final = (
    ("firstEdition", "1st Edition"),
    ("holo", "Holo"),
    ("reverse", "Reverse Holo"),
    ("normal", "Normal"),
    ("wPromo", "Promo"),
)


class CardNotFound(Exception):
    """No catalog entry matched the requested name."""


@dataclass(frozen=True, slots=True)
class Printing:
    """One physical printing of a named card, keyed by its disambiguation tuple."""

    card_id: str
    name: str
    set_name: str
    collector_number: str
    set_total: int | None
    variant: str
    trend_eur: Decimal | None
    product_id: int | None

    @property
    def set_code(self) -> str:
        """The collector-number string as it reads on the card ("4/102"), the literal
        OCR target. Falls back to the bare number for promos with no printed total.
        """
        return f"{self.collector_number}/{self.set_total}" if self.set_total else self.collector_number

    @property
    def tuple_label(self) -> str:
        return f"{self.set_name} {self.set_code} · {self.variant}"


@dataclass(frozen=True, slots=True)
class Spread:
    """The price stakes of getting the variant wrong for a given card name."""

    name: str
    printings: tuple[Printing, ...]

    @property
    def priced(self) -> tuple[Printing, ...]:
        return tuple(p for p in self.printings if p.trend_eur is not None)

    @property
    def cheapest(self) -> Printing | None:
        priced = self.priced
        return min(priced, key=lambda p: p.trend_eur) if priced else None  # type: ignore[arg-type, return-value]

    @property
    def dearest(self) -> Printing | None:
        priced = self.priced
        return max(priced, key=lambda p: p.trend_eur) if priced else None  # type: ignore[arg-type, return-value]

    @property
    def factor(self) -> Decimal | None:
        """The ×N a mis-disambiguation can cost: dearest / cheapest priced printing."""
        lo, hi = self.cheapest, self.dearest
        if lo is None or hi is None or lo.trend_eur == 0:
            return None
        return hi.trend_eur / lo.trend_eur  # type: ignore[union-attr]


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _resolve_variant(variants: dict[str, bool]) -> str:
    for key, label in _VARIANT_PRIORITY:
        if variants.get(key):
            return label
    return "Unknown"


def _printing_from_card(card: dict) -> Printing:
    card_set = card.get("set") or {}
    cardmarket = (card.get("pricing") or {}).get("cardmarket") or {}
    return Printing(
        card_id=card["id"],
        name=card["name"],
        set_name=card_set.get("name", "—"),
        collector_number=str(card.get("localId", "?")),
        set_total=(card_set.get("cardCount") or {}).get("official"),
        variant=_resolve_variant(card.get("variants") or {}),
        trend_eur=_to_decimal(cardmarket.get("trend")),
        product_id=cardmarket.get("idProduct"),
    )


def _iter_named_cards(
    name: str, *, locale: str, client: httpx.Client
) -> Iterator[dict]:
    """Yield the catalog stubs whose name matches ``name`` exactly.

    TCGdex's ``eq:`` filter excludes near-name decoys ("Dark Charizard", "Blaine's
    Charizard") that share artwork lineage but are genuinely different cards — those are
    a recognition concern, not a variant one.
    """
    response = client.get(
        f"{API_ROOT}/{locale}/cards", params={"name": f"eq:{name}"}
    )
    response.raise_for_status()
    yield from response.json()


def enumerate_printings(
    name: str,
    *,
    locale: str = "en",
    limit: int | None = None,
    client: httpx.Client | None = None,
) -> Spread:
    """Enumerate every distinct printing sharing ``name`` and resolve each to its
    ``(set, collector number, variant)`` tuple with its Cardmarket € trend price.

    Raises ``CardNotFound`` when no card carries that exact name. ``limit`` caps the
    per-card detail fetches (the list endpoint omits pricing, so each printing needs one
    follow-up call) — purely a speed knob for demos. It takes printings in catalog order,
    so a limited run *samples* the spread and may miss the dearest variant; the unbounded
    default is what proves the full price range.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=_REQUEST_TIMEOUT)
    try:
        stubs = list(_iter_named_cards(name, locale=locale, client=client))
        if not stubs:
            raise CardNotFound(name)
        printings = [
            _printing_from_card(_fetch_card(stub["id"], locale=locale, client=client))
            for stub in _capped(stubs, limit)
        ]
    finally:
        if owns_client:
            client.close()

    printings.sort(key=_sort_key, reverse=True)
    return Spread(name=name, printings=tuple(printings))


def _fetch_card(card_id: str, *, locale: str, client: httpx.Client) -> dict:
    response = client.get(f"{API_ROOT}/{locale}/cards/{card_id}")
    response.raise_for_status()
    return response.json()


def _capped(stubs: list[dict], limit: int | None) -> Iterable[dict]:
    return stubs if limit is None else stubs[:limit]


def _sort_key(printing: Printing) -> tuple[int, Decimal]:
    # Priced printings first, dearest at the top; unpriced sink to the bottom.
    return (1 if printing.trend_eur is not None else 0, printing.trend_eur or Decimal(0))


def _render(spread: Spread) -> str:
    rows = [
        f"Distinct printings named \"{spread.name}\" — same name, often the same artwork, "
        f"resolved by (set, collector №, variant):",
        "",
        f"  {'VARIANT TUPLE':<46} {'€ TREND':>10}   {'×vs floor':>9}",
        f"  {'-' * 46} {'-' * 10}   {'-' * 9}",
    ]
    floor = spread.cheapest
    for printing in spread.printings:
        if printing.trend_eur is None:
            price, factor = "no Cardmarket data", "—"
        else:
            price = f"€{printing.trend_eur:,.2f}"
            factor = (
                f"×{printing.trend_eur / floor.trend_eur:.0f}"
                if floor and floor.trend_eur
                else "—"
            )
        rows.append(f"  {printing.tuple_label:<46} {price:>10}   {factor:>9}")

    rows.append("")
    if spread.factor is not None and spread.dearest and spread.cheapest:
        rows.append(
            f"Price spread: €{spread.cheapest.trend_eur:,.2f} → "
            f"€{spread.dearest.trend_eur:,.2f}  =  ×{spread.factor:,.0f} swing on the "
            f"same name."
        )
        rows.append(
            "Artwork/name match alone cannot pick the right row. The collector number + "
            "set symbol can — that is the disambiguator."
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate the distinct printings sharing a card name and show the € price "
            "spread across (set, collector number, variant) — no API key."
        ),
    )
    parser.add_argument(
        "name",
        nargs="?",
        default="Charizard",
        help="Exact card name, e.g. Charizard",
    )
    parser.add_argument("--locale", default="en")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap printings inspected, in catalog order (a demo speed knob; may understate the spread).",
    )
    args = parser.parse_args(argv)

    try:
        spread = enumerate_printings(args.name, locale=args.locale, limit=args.limit)
    except CardNotFound as exc:
        print(f"No card named '{exc}' in the catalog.", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"Upstream fetch failed: {exc}", file=sys.stderr)
        return 1

    print(_render(spread))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
