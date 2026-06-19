"""In-house condition analysis — the corners/edges/surface reads we used to buy.

A humble, honest v1 (charter §3.1: a pre-screen, not a guarantee). It measures *defects*
from the pixels rather than learning a grade: a pristine card's edges and corners are clean,
uniform lines, while wear (whitening, fraying, nicks) and surface damage (scratches, print
lines) introduce local roughness. We quantify that roughness in the four edge bands, the four
corners, and the interior, map it to a 1–10 sub-score, and — crucially — report *modest*
confidence, because a from-pixels heuristic without a trained defect model is genuinely less
certain than a clean centering measurement. The pre-grade composition then widens the range
accordingly, so we never imply false precision. The consented data loop is what turns this v1
into a trained grader over time (the moat); until then it is honest, not authoritative.

Pure numpy/Pillow, on the detected card crop — no OpenCV in our own code.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.identify.vision.detect import detect_card_crop
from app.schemas.grading import GradingAxis

# Roughness (mean absolute deviation, in 0–255 luminance) that we treat as "fully worn" for
# an axis. Calibrated to be forgiving — a clean card reads near zero; this is the point a
# defect saturates the penalty. The data loop recalibrates these against real graded cards.
_ROUGHNESS_SATURATION = 40.0
# A defect drags the score from a 10 down to this floor when fully saturated.
_SCORE_FLOOR = 2.0
# v1 reads are inherently uncertain; confidence scales with capture quality but is capped well
# below 1 so the composition keeps an honest spread.
_CONF_BASE = 0.35
_CONF_QUALITY_GAIN = 0.45
_CONF_CAP = 0.85


@dataclass(frozen=True, slots=True)
class AxisRead:
    score: float
    confidence: float


def assess_condition(image_bytes: bytes) -> dict[GradingAxis, AxisRead]:
    """Read corners/edges/surface condition from a capture's bytes (centering is separate)."""
    crop = detect_card_crop(image_bytes)
    gray = crop.image.mean(axis=2) if crop.image.ndim == 3 else crop.image.astype(float)
    height, width = gray.shape[0], gray.shape[1]
    border = max(4, min(height, width) // 20)
    corner = max(6, min(height, width) // 12)

    edge_defect = _mean_roughness(
        [gray[:border, :], gray[-border:, :], gray[:, :border], gray[:, -border:]]
    )
    corner_defect = _mean_roughness(
        [
            gray[:corner, :corner],
            gray[:corner, -corner:],
            gray[-corner:, :corner],
            gray[-corner:, -corner:],
        ]
    )
    interior = gray[border:-border, border:-border] if height > 2 * border and width > 2 * border else gray
    surface_defect = _roughness(interior)

    confidence = _confidence(crop.quality)
    return {
        GradingAxis.CORNERS: AxisRead(_score(corner_defect), confidence),
        GradingAxis.EDGES: AxisRead(_score(edge_defect), confidence),
        GradingAxis.SURFACE: AxisRead(_score(surface_defect), confidence),
    }


def _roughness(region: np.ndarray) -> float:
    """Robust local roughness: mean absolute deviation from the region's median luminance.

    Zero for a uniform (clean) region; rises with the speckle/streaking that wear and surface
    damage introduce. Median-centred so a colour shift alone doesn't read as a defect.
    """
    if region.size == 0:
        return 0.0
    return float(np.mean(np.abs(region - np.median(region))))


def _mean_roughness(regions: list[np.ndarray]) -> float:
    values = [_roughness(r) for r in regions if r.size]
    return float(sum(values) / len(values)) if values else 0.0


def _score(defect: float) -> float:
    saturation = min(1.0, defect / _ROUGHNESS_SATURATION)
    return round(10.0 - (10.0 - _SCORE_FLOOR) * saturation, 2)


def _confidence(quality: float) -> float:
    return round(min(_CONF_CAP, _CONF_BASE + _CONF_QUALITY_GAIN * float(quality)), 3)
