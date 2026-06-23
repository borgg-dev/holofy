"""Map a pre-grade's estimated grade to a card condition, and a condition to a price factor.

The product model we agreed: a *scan* doesn't claim a condition (it identifies the card and shows
the market guide price); the user's *pre-grade* — a deliberate, multi-angle look — is what assesses
the card's state. This turns the pre-grade's 1–10 grade band into a collector condition, and a
condition into a multiplier on the near-mint guide price, so a graded card can show "your copy"
value alongside the baseline.

Both tables are honest approximations, not gospel:
- The grade→condition bands follow the usual PSA-grade ↔ TCG-condition correspondence.
- The multipliers follow standard secondary-market condition discounts (the guide price is a
  near-mint reference; lower conditions trade at a fraction). They're a transparent estimate the
  UI labels as such — a real per-condition feed (TCGplayer's NM/LP/MP/HP/DM) can replace them later
  without changing callers.
"""

from __future__ import annotations

from decimal import Decimal

from app.db.models.enums import CardCondition

# Central grade (rounded) → condition. A card is only as good as its band's middle estimate.
_GRADE_TO_CONDITION: dict[int, CardCondition] = {
    10: CardCondition.MINT,
    9: CardCondition.NEAR_MINT,
    8: CardCondition.NEAR_MINT,
    7: CardCondition.EXCELLENT,
    6: CardCondition.EXCELLENT,
    5: CardCondition.GOOD,
    4: CardCondition.GOOD,
    3: CardCondition.LIGHT_PLAYED,
    2: CardCondition.PLAYED,
    1: CardCondition.POOR,
}

# Condition → fraction of the near-mint guide price. NM/Mint anchor at 1.0 (the guide already
# references near-mint); each step down applies the standard market discount. NOT_ASSESSED shows the
# guide unchanged (no claim about the copy).
_CONDITION_MULTIPLIER: dict[CardCondition, Decimal] = {
    CardCondition.MINT: Decimal("1.00"),
    CardCondition.NEAR_MINT: Decimal("1.00"),
    CardCondition.EXCELLENT: Decimal("0.85"),
    CardCondition.GOOD: Decimal("0.70"),
    CardCondition.LIGHT_PLAYED: Decimal("0.55"),
    CardCondition.PLAYED: Decimal("0.40"),
    CardCondition.POOR: Decimal("0.25"),
    CardCondition.NOT_ASSESSED: Decimal("1.00"),
}


def grade_to_condition(likely_low: int, likely_high: int) -> CardCondition:
    """The condition a pre-grade band implies, from its central (rounded) grade."""
    central = round((likely_low + likely_high) / 2)
    central = max(1, min(10, central))
    return _GRADE_TO_CONDITION[central]


def condition_multiplier(condition: CardCondition) -> Decimal:
    """Fraction of the near-mint guide price a card in this condition is estimated to trade at.
    Unknown/scan-outcome conditions (resolved/needs_confirmation/unrecognized) fall back to 1.0."""
    return _CONDITION_MULTIPLIER.get(condition, Decimal("1.00"))


def adjust_value(value_eur: Decimal | None, condition: CardCondition) -> Decimal | None:
    """The guide value scaled to a condition (2dp). ``None`` value stays ``None`` (no comp)."""
    if value_eur is None:
        return None
    return (value_eur * condition_multiplier(condition)).quantize(Decimal("0.01"))
