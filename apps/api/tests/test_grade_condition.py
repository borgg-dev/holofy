"""Grade→condition mapping and condition→price scaling — the pre-grade pricing logic.

Pure and deterministic. Pins the product rules we agreed: a pre-grade band implies a condition; a
condition discounts the near-mint guide into a "your copy" estimate; near-mint and not-assessed
leave the guide unchanged so a freshly-scanned card is never silently marked down or up.
"""

from __future__ import annotations

from decimal import Decimal

from app.db.models.enums import CardCondition
from app.grading.grade_condition import adjust_value, condition_multiplier, grade_to_condition


def test_grade_band_maps_to_condition() -> None:
    assert grade_to_condition(10, 10) is CardCondition.MINT
    assert grade_to_condition(9, 9) is CardCondition.NEAR_MINT
    assert grade_to_condition(8, 9) is CardCondition.NEAR_MINT  # central 8.5 → 9 → NM
    assert grade_to_condition(7, 7) is CardCondition.EXCELLENT
    assert grade_to_condition(5, 5) is CardCondition.GOOD
    assert grade_to_condition(3, 3) is CardCondition.LIGHT_PLAYED
    assert grade_to_condition(1, 2) is CardCondition.PLAYED  # central 1.5 → 2 → played
    assert grade_to_condition(1, 1) is CardCondition.POOR


def test_near_mint_and_unassessed_do_not_change_the_guide() -> None:
    for cond in (CardCondition.NEAR_MINT, CardCondition.MINT, CardCondition.NOT_ASSESSED):
        assert condition_multiplier(cond) == Decimal("1.00")
        assert adjust_value(Decimal("42.00"), cond) == Decimal("42.00")


def test_worn_condition_discounts_the_guide() -> None:
    base = Decimal("100.00")
    assert adjust_value(base, CardCondition.EXCELLENT) == Decimal("85.00")
    assert adjust_value(base, CardCondition.LIGHT_PLAYED) == Decimal("55.00")
    assert adjust_value(base, CardCondition.POOR) == Decimal("25.00")
    # Discounts strictly decrease as condition worsens.
    order = [CardCondition.NEAR_MINT, CardCondition.EXCELLENT, CardCondition.GOOD,
             CardCondition.LIGHT_PLAYED, CardCondition.PLAYED, CardCondition.POOR]
    vals = [adjust_value(base, c) for c in order]
    assert vals == sorted(vals, reverse=True) and len(set(vals)) == len(vals)


def test_no_price_stays_none() -> None:
    assert adjust_value(None, CardCondition.GOOD) is None
