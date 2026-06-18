"""Synthetic bordered-card generator for the centering tests.

Ported from Spike D (``spikes/centering/synthetic.py``). Real graded-card photos with
ground-truth border pixels are scarce and noisy; a synthetic card lets us assert the *math*
against an exact, known centering offset — draw an outer card on a contrasting background
and an inner art panel whose four border widths we choose, then check the measurement
recovers them. This validates the algorithm independently of a labelled dataset.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

_BACKGROUND: float = 30.0  # dark capture surface
_CARD: float = 235.0  # light card border (e.g. the yellow Base Set frame, in luma)
_ART: float = 90.0  # darker inner art panel


@dataclass(frozen=True, slots=True)
class SyntheticCard:
    """A generated card plus the border widths that produced it (the ground truth)."""

    image: NDArray[np.float64]
    border_left: int
    border_right: int
    border_top: int
    border_bottom: int

    @property
    def expected_lr(self) -> tuple[int, int]:
        return _ratio(self.border_left, self.border_right)

    @property
    def expected_tb(self) -> tuple[int, int]:
        return _ratio(self.border_top, self.border_bottom)


def make_card(
    *,
    size: tuple[int, int] = (700, 500),
    margin: int = 24,
    borders: tuple[int, int, int, int] = (40, 40, 40, 40),
    card_value: float = _CARD,
    art_value: float = _ART,
    noise: float = 0.0,
    seed: int | None = None,
) -> SyntheticCard:
    """Render a card on a background with an inner art panel at known border widths.

    ``borders`` is ``(left, right, top, bottom)`` in pixels, measured from the card edge to
    the art panel. ``margin`` is the background gutter around the card. ``noise`` adds
    Gaussian sensor noise so tests can probe robustness, not just the ideal case.
    """
    height, width = size
    field = np.full((height, width), _BACKGROUND, dtype=np.float64)

    card_top, card_bottom = margin, height - margin
    card_left, card_right = margin, width - margin
    field[card_top:card_bottom, card_left:card_right] = card_value

    b_left, b_right, b_top, b_bottom = borders
    art_top = card_top + b_top
    art_bottom = card_bottom - b_bottom
    art_left = card_left + b_left
    art_right = card_right - b_right
    if art_top >= art_bottom or art_left >= art_right:
        raise ValueError("borders leave no room for an inner art panel")
    field[art_top:art_bottom, art_left:art_right] = art_value

    if noise > 0:
        rng = np.random.default_rng(seed)
        field = np.clip(field + rng.normal(0.0, noise, field.shape), 0.0, 255.0)

    return SyntheticCard(
        image=field,
        border_left=b_left,
        border_right=b_right,
        border_top=b_top,
        border_bottom=b_bottom,
    )


def _ratio(a: int, b: int) -> tuple[int, int]:
    total = a + b
    if total == 0:
        return 50, 50
    if a == b:
        return 50, 50
    high = round(max(a, b) / total * 100)
    return high, 100 - high
