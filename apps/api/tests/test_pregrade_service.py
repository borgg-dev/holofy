"""Coverage for the pre-grade composition: range math, confidence downgrade, refuse paths.

Centering is measured in-house from a synthetic capture (so the band/confidence are real),
the bought sub-scores come from a stub grader so each branch is pinned exactly. The hard
honest-framing rules (charter §3.1) are the assertions: never a single grade, a poorly-read
capture widens the range and lowers confidence rather than guessing, and an ungradeable
capture refuses with a retake reason instead of a confident wrong answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.schemas.grading import GradingAxis, PregradeStatus, SubScore
from app.services.pregrade import PregradeService
from tests.grading_synthetic import make_card

_MIN_CENTERING_CONFIDENCE = 0.4


@dataclass
class _Capture:
    capture_ref: str = "capture-x"
    image_count: int = 1


class _StubGrader:
    """Returns fixed corners/edges/surface sub-scores, independent of the capture."""

    def __init__(self, *scores: tuple[GradingAxis, float, float]) -> None:
        self._sub_scores = [
            SubScore(axis=axis, score=score, confidence=conf) for axis, score, conf in scores
        ]

    async def grade(self, _capture) -> list[SubScore]:  # noqa: ANN001
        return list(self._sub_scores)


def _png(field: np.ndarray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(field.astype(np.uint8), mode="L").save(buffer, format="PNG")
    return buffer.getvalue()


def _bought(corners: float, edges: float, surface: float, conf: float) -> _StubGrader:
    return _StubGrader(
        (GradingAxis.CORNERS, corners, conf),
        (GradingAxis.EDGES, edges, conf),
        (GradingAxis.SURFACE, surface, conf),
    )


def _service(grader: _StubGrader) -> PregradeService:
    return PregradeService(grading=grader, min_centering_confidence=_MIN_CENTERING_CONFIDENCE)


@pytest.mark.asyncio
async def test_clean_card_high_scores_yield_a_confident_high_range() -> None:
    image = _png(make_card(borders=(40, 40, 40, 40)).image)  # pristine centering
    grader = _bought(9.5, 9.0, 9.5, conf=0.93)

    result = await _service(grader).pregrade(_Capture(), image=image)

    assert result.status is PregradeStatus.ESTIMATED
    assert result.probability is not None
    assert result.confidence is not None and result.confidence > 0.85
    # High but honest: a band over the 1–10 scale, never a single grade. The clean capture
    # keeps the band tight.
    band = result.probability
    assert band.likely_high >= band.likely_low
    assert band.likely_high - band.likely_low <= 2
    assert band.likely_high >= 9


@pytest.mark.asyncio
async def test_the_output_is_never_a_single_grade() -> None:
    image = _png(make_card(borders=(40, 40, 40, 40)).image)
    result = await _service(_bought(9.0, 9.0, 9.0, conf=0.9)).pregrade(_Capture(), image=image)

    assert result.status is PregradeStatus.ESTIMATED
    dumped = result.probability.model_dump()
    # The honesty contract: there is no field that holds "the grade".
    assert "grade" not in dumped
    assert {"likely_low", "likely_high", "at_least", "p_at_least"} <= set(dumped)
    assert "pre-screen" in result.disclaimer.lower() or "not an official grade" in result.disclaimer.lower()


@pytest.mark.asyncio
async def test_worst_axis_gates_the_range_a_poor_surface_drags_it_down() -> None:
    # Centering and corners/edges are gem, but surface is poor — the worst axis must cap the
    # estimate, the way a grader gates on the weakest sub-grade.
    image = _png(make_card(borders=(40, 40, 40, 40)).image)
    poor = await _service(_bought(9.5, 9.0, 4.0, conf=0.9)).pregrade(_Capture(), image=image)
    clean = await _service(_bought(9.5, 9.0, 9.5, conf=0.9)).pregrade(_Capture(), image=image)

    assert poor.probability.likely_high < clean.probability.likely_high
    assert poor.probability.likely_high <= 7  # a 4-surface card can't read as a 9


@pytest.mark.asyncio
async def test_low_bought_confidence_widens_the_range_and_lowers_confidence() -> None:
    # Same scores, but the bought read is barely confident: the range must widen (honest
    # uncertainty) and the overall confidence must drop — no false precision.
    image = _png(make_card(borders=(40, 40, 40, 40)).image)
    confident = await _service(_bought(8.0, 8.0, 8.0, conf=0.9)).pregrade(_Capture(), image=image)
    unsure = await _service(_bought(8.0, 8.0, 8.0, conf=0.2)).pregrade(_Capture(), image=image)

    confident_band = confident.probability.likely_high - confident.probability.likely_low
    unsure_band = unsure.probability.likely_high - unsure.probability.likely_low
    assert unsure_band > confident_band
    assert unsure.confidence < confident.confidence


@pytest.mark.asyncio
async def test_overall_confidence_is_gated_by_the_least_certain_axis() -> None:
    # Centering is read cleanly (high confidence) but the bought surface read is poor: the
    # composite confidence must follow the weakest axis, not the strongest.
    image = _png(make_card(borders=(40, 40, 40, 40)).image)
    grader = _StubGrader(
        (GradingAxis.CORNERS, 9.0, 0.9),
        (GradingAxis.EDGES, 9.0, 0.9),
        (GradingAxis.SURFACE, 9.0, 0.25),
    )
    result = await _service(grader).pregrade(_Capture(), image=image)
    assert result.confidence is not None and result.confidence <= 0.25 + 1e-9


@pytest.mark.asyncio
async def test_four_sub_scores_including_in_house_centering() -> None:
    image = _png(make_card(borders=(48, 32, 45, 45)).image)
    result = await _service(_bought(9.0, 9.0, 9.0, conf=0.9)).pregrade(_Capture(), image=image)

    axes = {s.axis for s in result.sub_scores}
    assert axes == {
        GradingAxis.CENTERING,
        GradingAxis.CORNERS,
        GradingAxis.EDGES,
        GradingAxis.SURFACE,
    }


@pytest.mark.asyncio
async def test_full_bleed_capture_refuses_with_a_retake_reason() -> None:
    # A uniform face has no measurable border — the service must refuse, not invent a ratio.
    field = np.full((400, 300), 30.0)
    field[24:376, 24:276] = 200.0
    result = await _service(_bought(9.0, 9.0, 9.0, conf=0.9)).pregrade(_Capture(), image=_png(field))

    assert result.status is PregradeStatus.RETAKE
    assert result.probability is None
    assert result.confidence is None
    assert result.reasons and "full-bleed" in result.reasons[0].lower()


@pytest.mark.asyncio
async def test_low_centering_confidence_refuses_rather_than_guessing() -> None:
    # A washed-out, low-contrast border reads with low confidence — below the floor the
    # service refuses rather than emitting a confident wrong range.
    image = _png(make_card(borders=(40, 40, 40, 40), card_value=140.0, art_value=120.0).image)
    result = await _service(_bought(9.0, 9.0, 9.0, conf=0.9)).pregrade(_Capture(), image=image)

    assert result.status is PregradeStatus.RETAKE
    assert result.reasons and "confiden" in result.reasons[0].lower()


@pytest.mark.asyncio
async def test_undecodable_capture_refuses() -> None:
    result = await _service(_bought(9.0, 9.0, 9.0, conf=0.9)).pregrade(_Capture(), image=b"garbage")
    assert result.status is PregradeStatus.RETAKE
