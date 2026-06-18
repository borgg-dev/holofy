"""Spike D — pixel-level centering measurement for pre-grading.

Centering is the cheapest and most *mathematically honest* pre-grade signal: it is a
direct geometric measurement, not a learned guess. Given a flat, deskewed scan of a
bordered card, we locate the outer card edge and the inner frame (the boundary of the
printed border), measure the four border widths, and express centering the way graders
and collectors do — ``L/R`` and ``T/B`` ratios — plus a quality band that maps toward
PSA-style centering tolerances.

This is decision support, never a grade. Every result carries a ``confidence`` and the
band is framed as an *estimate*; see ``docs/TECHNICAL_ARCHITECTURE.md`` §3.2 and the
charter's honest-framing rule. The output of this stage feeds the broader pre-grade
model (centering is one of four PSA sub-grades) rather than standing alone.

Pure numpy for the measurement; Pillow only to decode image files. No OpenCV — the
edge/border detection here is classic 1-D intensity-gradient profiling, which is both
adequate for a flat scan and transparent enough to audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

# A border whose two opposing widths differ by less than this fraction of the card is
# treated as visually centred — below it the ratio is dominated by measurement noise,
# not real off-centring.
_PERFECT_TOLERANCE: Final = 0.01

# Fraction of the outer card span ignored on each side when locating the inner frame, so
# the outer-edge gradient itself is never mistaken for the inner border.
_EDGE_GUARD_FRACTION: Final = 0.02

# Minimum mean-luma step (0–255) a border transition must show to count as a real frame
# rather than sensor noise on a uniform, full-bleed face. Tuned to clear typical capture
# noise (σ≈6) while still firing on the soft transitions of a low-contrast border.
_MIN_TRANSITION_LUMA: Final = 12.0

# Mean-luma step at which a border transition is treated as unambiguous; confidence
# saturates here, so a crisp border↔art edge reads as fully certain.
_CONFIDENT_TRANSITION_LUMA: Final = 60.0

Axis = NDArray[np.float64]


class CenteringError(Exception):
    """The image could not be measured (no card edge or no inner frame resolved)."""


class QualityBand(str, Enum):
    """Centering quality, framed against PSA-style centering tolerances for a raw card.

    Values are deliberately coarse bands, not numeric grades: the worst-axis off-centring
    is the gating factor a grader applies, so we report the band the *weaker* axis lands
    in. PSA's published front tolerances are ~55/45 for a 10 and ~60/40 for a 9; we mirror
    that shape without claiming to *be* a grade.
    """

    PRISTINE = "pristine"  # ≤ 55/45 both axes — gem-mint-eligible on centering alone
    EXCELLENT = "excellent"  # ≤ 60/40 — typically still a 9 on centering
    GOOD = "good"  # ≤ 65/35 — mid-grade territory
    OFF_CENTER = "off_center"  # ≤ 75/25 — visibly off, caps the grade
    SEVERE = "severe"  # worse than 75/25 — a hard ceiling on grade


@dataclass(frozen=True, slots=True)
class Ratio:
    """One axis of centering, e.g. left vs right, as the standard collector ``hi/lo``."""

    high: int
    low: int

    @property
    def offset(self) -> float:
        """How far from a perfect 50/50 split, in 0–1 (0 = centred, 0.5 = touching one side)."""
        return (self.high - self.low) / 200.0

    def __str__(self) -> str:
        return f"{self.high}/{self.low}"


@dataclass(frozen=True, slots=True)
class CenteringResult:
    """A centering *estimate* with provenance, never an absolute grade.

    ``confidence`` reflects how cleanly the borders were resolved (edge contrast and
    geometric plausibility), independent of how good the centering itself is — a sharply
    measured badly-centred card is a high-confidence "off-center", not a low one.
    """

    left_right: Ratio
    top_bottom: Ratio
    band: QualityBand
    confidence: float
    borders_px: tuple[int, int, int, int]  # left, right, top, bottom

    @property
    def worst_offset(self) -> float:
        return max(self.left_right.offset, self.top_bottom.offset)

    def report(self) -> str:
        l, r, t, b = self.borders_px
        return "\n".join(
            [
                "Centering estimate (pre-grade, not a grade)",
                f"  Left-Right : {self.left_right}   (borders {l}px / {r}px)",
                f"  Top-Bottom : {self.top_bottom}   (borders {t}px / {b}px)",
                f"  Quality    : {self.band.value}",
                f"  Confidence : {self.confidence:.0%}",
            ]
        )


def measure_centering(image: NDArray[np.floating] | NDArray[np.integer]) -> CenteringResult:
    """Measure centering from a flat, deskewed grayscale card image.

    ``image`` is a 2-D array (H×W); RGB input should be reduced to luminance by the caller
    or via :func:`load_grayscale`. The card is assumed to sit on a contrasting background
    and be roughly axis-aligned — this stage is a *measurement*, not a rectifier, and
    depends on the guided-capture flow (see FINDINGS.md) to supply aligned input.

    Raises :class:`CenteringError` if no card edge or no inner frame can be resolved.
    """
    if image.ndim != 2:
        raise CenteringError(f"expected a 2-D grayscale image, got shape {image.shape}")
    field = np.asarray(image, dtype=np.float64)
    if field.shape[0] < 16 or field.shape[1] < 16:
        raise CenteringError(f"image too small to measure: {field.shape}")

    top, bottom = _locate_card_edges(_row_profile(field))
    left, right = _locate_card_edges(_column_profile(field))

    card = field[top:bottom, left:right]
    height, width = card.shape

    border_top, border_bottom, conf_v = _locate_inner_border(_row_profile(card), height)
    border_left, border_right, conf_h = _locate_inner_border(_column_profile(card), width)

    left_right = _to_ratio(border_left, border_right)
    top_bottom = _to_ratio(border_top, border_bottom)
    band = _classify(left_right, top_bottom)
    confidence = round(min(conf_h, conf_v), 3)

    return CenteringResult(
        left_right=left_right,
        top_bottom=top_bottom,
        band=band,
        confidence=confidence,
        borders_px=(border_left, border_right, border_top, border_bottom),
    )


def load_grayscale(path: str | Path) -> NDArray[np.float64]:
    """Decode an image file to a 2-D luminance array via Pillow (BT.601 weights)."""
    from PIL import Image  # local import keeps the numpy core dependency-light

    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.float64)


def _row_profile(field: Axis) -> Axis:
    """Mean intensity per row — collapses the image to a vertical 1-D signal."""
    return field.mean(axis=1)


def _column_profile(field: Axis) -> Axis:
    """Mean intensity per column — collapses the image to a horizontal 1-D signal."""
    return field.mean(axis=0)


def _locate_card_edges(profile: Axis) -> tuple[int, int]:
    """Find the outer card boundary along one axis, returned as a half-open ``[start, end)``.

    The card edge is the largest intensity step against the background. ``np.diff`` peaks at
    the index *before* a transition, so the strongest rising step at ``r`` puts the first
    card pixel at ``r + 1`` and the strongest falling step at ``f`` puts the last card pixel
    at ``f`` — i.e. the interior is ``[r + 1, f + 1)``. If the card bleeds off-frame (steps
    collapse to one side) we use the full extent.
    """
    step = np.diff(profile)
    n = profile.size
    rising = int(np.argmax(step))
    falling = int(np.argmin(step))
    start, end = sorted((rising, falling))
    if end - start < n * 0.25:
        return 0, n
    return start + 1, end + 1


def _locate_inner_border(profile: Axis, span: int) -> tuple[int, int, float]:
    """Measure the two border widths on one axis of an already-cropped card.

    Scans inward from each edge for the first strong intensity transition (border → art)
    and returns ``(near_border_px, far_border_px, confidence)``. ``np.diff`` indexing is
    symmetric here: a step at ``s`` scanning forward means ``s + 1`` border pixels precede
    the art; the same logic mirrored gives the far border, so a centred card yields equal
    widths with no off-by-one bias.

    Confidence combines transition sharpness (how cleanly the border stands out) with
    border symmetry (a sane, balanced split), in [0, 1]. A washed-out or full-bleed card
    yields a weak transition and a correspondingly low confidence.
    """
    guard = max(1, int(span * _EDGE_GUARD_FRACTION))
    limit = span // 2  # neither border can plausibly cross the midline

    step = np.abs(np.diff(profile))

    near, near_luma = _border_from(step, guard, limit)
    far, far_luma = _border_from(step[::-1], guard, limit)

    weakest_luma = min(near_luma, far_luma)
    if weakest_luma < _MIN_TRANSITION_LUMA:
        raise CenteringError("no border transition above the noise floor (full-bleed face?)")

    confidence = _confidence(weakest_luma)
    return near, far, confidence


def _border_from(step: Axis, guard: int, limit: int) -> tuple[int, float]:
    """Border width from one edge: peak of the diff in ``[guard, limit)``, plus its magnitude.

    A peak at array index ``i`` means the border spans pixels ``0..i`` inclusive, i.e. a
    width of ``i + 1`` pixels. The returned magnitude is the raw mean-luma step, used both
    to reject full-bleed faces and to score confidence.
    """
    window = step[guard:limit]
    peak = int(np.argmax(window))
    return guard + peak + 1, float(window[peak])


def _confidence(weakest_luma: float) -> float:
    """Map the weaker border's mean-luma transition magnitude to a [0, 1] confidence.

    This rates *measurement quality*, not centering quality: a sharply-imaged but badly
    off-centre card is high-confidence, while a washed-out or low-contrast card reads low
    because its border transition is faint. The weaker of the two opposing transitions
    gates the score, since the axis is only as trustworthy as its softest edge. The
    saturation point is a typical strong border↔art contrast — past it, more contrast adds
    no certainty.
    """
    return max(0.0, min(1.0, weakest_luma / _CONFIDENT_TRANSITION_LUMA))


def _to_ratio(a: int, b: int) -> Ratio:
    """Express two opposing border widths as a ``hi/lo`` percentage split summing to 100."""
    total = a + b
    if total == 0:
        return Ratio(50, 50)
    share = a / total
    if abs(share - 0.5) < _PERFECT_TOLERANCE:
        return Ratio(50, 50)
    high = round(max(a, b) / total * 100)
    return Ratio(high, 100 - high)


def _classify(left_right: Ratio, top_bottom: Ratio) -> QualityBand:
    """Map the *worse* of the two axes to a centering band (the grader's gating axis)."""
    worst = max(left_right.high, top_bottom.high)
    if worst <= 55:
        return QualityBand.PRISTINE
    if worst <= 60:
        return QualityBand.EXCELLENT
    if worst <= 65:
        return QualityBand.GOOD
    if worst <= 75:
        return QualityBand.OFF_CENTER
    return QualityBand.SEVERE
