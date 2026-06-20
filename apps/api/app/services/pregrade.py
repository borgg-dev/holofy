"""Pre-grade orchestration: in-house centering + bought corners/edges/surface → a range.

This composes the one sub-score Holofy *measures* (centering, ``app.grading.centering``)
with the three it *buys* (corners/edges/surface, behind ``GradingProvider``) into an honest
grade **probability range** — never a single grade (charter §3.1). The honesty rules live
in the composition, not in copy:

1. Centering is mapped from its quality band to a 1–10 sub-score, carrying its own
   measurement confidence.
2. The overall grade is modelled the way a grader gates one: the *worst* sub-grade caps the
   card, so the central estimate is dominated by the minimum sub-score (a soft, confidence-
   weighted minimum), not the mean — a card is only as good as its weakest axis.
3. The estimate is a **distribution**: a central value plus a spread that *widens* as the
   sub-scores' confidence drops, so a poorly-read capture yields a wide, low-confidence
   range instead of false precision. From it we report a likely band and ``p_at_least``.
4. **Refuse over guess**: if centering can't be measured at all (full-bleed / washed-out)
   or is read below the confidence floor, we return ``RETAKE`` with reasons rather than a
   confident wrong range. The endpoint renders that as a typed 200, not a 500.

The service does not own persistence; the endpoint logs the result through the repository,
mirroring how the scan flow is wired.
"""

from __future__ import annotations

from app.grading.centering import (
    CenteringError,
    CenteringResult,
    QualityBand,
    measure_centering,
)
from app.providers.base import GradingCapture, GradingProvider
from app.schemas.grading import (
    GradeProbabilityRange,
    GradingAxis,
    PregradeResponse,
    PregradeStatus,
    SubScore,
)

# Each centering band maps to the 1–10 sub-score a grader would assign on centering alone.
# These mirror the band docstrings (PSA-style tolerances) — pristine centering is gem-mint
# eligible, severe centering is a hard ceiling.
_BAND_TO_SCORE: dict[QualityBand, float] = {
    QualityBand.PRISTINE: 10.0,
    QualityBand.EXCELLENT: 9.0,
    QualityBand.GOOD: 7.5,
    QualityBand.OFF_CENTER: 5.0,
    QualityBand.SEVERE: 2.5,
}

# The grade is gated by the worst axis, but the other axes still inform it: the central
# estimate is the worst sub-score pulled a fraction of the way toward the mean. 1.0 would be
# a hard minimum (too pessimistic — a single soft read tanks everything); 0.0 the mean (too
# optimistic — ignores that graders cap on the weakest). This blend matches how a worst-axis
# gate behaves in practice.
_WORST_AXIS_WEIGHT = 0.7

# Spread (in grade points, 1σ) of the predicted-grade distribution at the confidence
# extremes. A perfectly-read card still carries irreducible model error (~half a grade); a
# barely-read one is very uncertain. The actual spread interpolates between these on the
# composite confidence.
_SPREAD_AT_FULL_CONFIDENCE = 0.5
_SPREAD_AT_NO_CONFIDENCE = 3.0


class PregradeService:
    def __init__(
        self,
        *,
        grading: GradingProvider,
        min_centering_confidence: float,
    ) -> None:
        self._grading = grading
        self._min_centering_confidence = min_centering_confidence

    async def pregrade(
        self,
        capture: GradingCapture,
        *,
        image: bytes,
    ) -> PregradeResponse:
        """Estimate a grade range for a capture, or refuse if it can't be read honestly.

        ``image`` is the capture's decoded bytes (the endpoint resolves them from object
        storage). Centering is measured here; corners/edges/surface come from the grading
        provider. A capture too poor to centre-measure returns ``RETAKE`` — a clear signal,
        never a confident wrong range.
        """
        try:
            centering = measure_centering(image)
        except CenteringError as exc:
            return _retake([_centering_retake_reason(exc)])

        if centering.confidence < self._min_centering_confidence:
            return _retake(
                [
                    "Centering needs a clean, straight-on look at the border. Lay the card flat, "
                    "fill the frame, shoot square-on (not at an angle) in even light with no glare, "
                    "then try again.",
                    "Pre-grade is in beta and only estimates from a sharp, flat scan — if it can't "
                    "read the border clearly it asks for a retake rather than guess a grade.",
                ]
            )

        sub_scores = [_centering_sub_score(centering), *await self._grading.grade(capture)]
        probability, confidence = _compose(sub_scores)

        return PregradeResponse(
            status=PregradeStatus.ESTIMATED,
            probability=probability,
            sub_scores=sub_scores,
            confidence=confidence,
        )


def _centering_sub_score(centering: CenteringResult) -> SubScore:
    """Turn the in-house centering measurement into a comparable 1–10 sub-score."""
    return SubScore(
        axis=GradingAxis.CENTERING,
        score=_BAND_TO_SCORE[centering.band],
        confidence=centering.confidence,
    )


def _compose(sub_scores: list[SubScore]) -> tuple[GradeProbabilityRange, float]:
    """Combine the four sub-scores into a probability range and an overall confidence.

    The central estimate is a confidence-weighted blend of the worst sub-score (the grader's
    gate) and the mean. The distribution's spread widens as confidence drops, so the reported
    band and ``p_at_least`` carry honest uncertainty rather than false precision.
    """
    scores = [s.score for s in sub_scores]
    confidences = [s.confidence for s in sub_scores]

    worst = min(scores)
    mean = sum(scores) / len(scores)
    central = _WORST_AXIS_WEIGHT * worst + (1.0 - _WORST_AXIS_WEIGHT) * mean

    # The composite is gated by the *least* certain axis — the range is only as trustworthy
    # as the softest read feeding it.
    overall_confidence = min(confidences)
    spread = _spread_for(overall_confidence)

    # A ±1σ band, clamped to the 1–10 scale and to whole grades collectors reason in.
    likely_low = _clamp_grade(round(central - spread))
    likely_high = _clamp_grade(round(central + spread))

    # The decision number: P(true grade ≥ the rounded central estimate). A normal model on
    # (central, spread) puts ~50% mass at or above the central grade's lower edge; we report
    # P(≥ floor) where floor is the central grade rounded down, computed from the tail.
    at_least = _clamp_grade(int(central))
    p_at_least = round(_p_at_least(central, spread, at_least), 2)

    probability = GradeProbabilityRange(
        likely_low=likely_low,
        likely_high=likely_high,
        at_least=at_least,
        p_at_least=p_at_least,
    )
    return probability, round(overall_confidence, 3)


def _spread_for(confidence: float) -> float:
    """Interpolate the distribution's 1σ spread (grade points) from overall confidence."""
    confidence = max(0.0, min(1.0, confidence))
    return _SPREAD_AT_NO_CONFIDENCE + confidence * (
        _SPREAD_AT_FULL_CONFIDENCE - _SPREAD_AT_NO_CONFIDENCE
    )


def _p_at_least(central: float, spread: float, floor: int) -> float:
    """P(grade ≥ ``floor``) under a normal(central, spread) model of the true grade.

    Uses the standard-normal CDF via ``math.erf`` so there is no scipy dependency. A wider
    spread (lower confidence) pulls this toward 0.5 — we are honestly less sure — which is
    exactly the behaviour the honesty rule wants.
    """
    import math

    if spread <= 0:
        return 1.0 if central >= floor else 0.0
    z = (floor - central) / spread
    cdf_below = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return max(0.0, min(1.0, 1.0 - cdf_below))


def _clamp_grade(value: int) -> int:
    return max(1, min(10, value))


def _retake(reasons: list[str]) -> PregradeResponse:
    """A refuse-on-bad-capture response: no range, just why to re-capture."""
    return PregradeResponse(status=PregradeStatus.RETAKE, reasons=reasons)


def _centering_retake_reason(exc: CenteringError) -> str:
    """Map a centering failure to user-facing capture coaching."""
    detail = str(exc)
    if "full-bleed" in detail:
        return (
            "No measurable border was found — this looks like a full-bleed / full-art card, "
            "which has no centering frame to grade. Centering pre-grade isn't applicable here."
        )
    if "too small" in detail:
        return "The capture is too small or low-resolution to measure. Re-capture closer and in focus."
    return "The card edges couldn't be located. Re-capture the whole card, flat, on a contrasting background."
