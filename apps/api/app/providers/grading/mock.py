"""Deterministic mock grader for the three bought PSA sub-scores.

Stands in for Ximilar ``/v2/grade`` until the real provider lands behind the same
``GradingProvider`` Protocol. It maps a capture to fixed corners/edges/surface sub-scores
keyed on ``capture_ref`` so the whole pre-grade flow — and its tests — are reproducible
with no model and no network.

The fixtures are chosen to exercise the composition's branches honestly:

- ``mock-gem`` — a clean, high-confidence capture: high sub-scores, the case that pushes
  the probability range up.
- ``mock-poor-surface`` — a real-world failure: a confidently-read *poor* surface (a deep
  scratch) that must drag the range down without dragging confidence down — a low score is
  not a low-confidence read.
- ``mock-low-confidence`` (the default for unknown refs) — a capture the model could barely
  read: middling scores with low confidence, so the composite must *widen the range and
  down-weight its own confidence* rather than emit false precision.
"""

from __future__ import annotations

from app.providers.base import GradingCapture
from app.schemas.grading import GradingAxis, SubScore

# capture_ref → (corners, edges, surface) as (score, confidence) on the PSA 1–10 scale.
_Score = tuple[float, float]
_FIXTURES: dict[str, tuple[_Score, _Score, _Score]] = {
    "mock-gem": ((9.5, 0.94), (9.0, 0.92), (9.5, 0.95)),
    "mock-poor-surface": ((8.5, 0.90), (8.0, 0.88), (4.0, 0.91)),
    "mock-low-confidence": ((7.0, 0.35), (7.0, 0.30), (6.5, 0.33)),
}

# Unknown captures get the low-confidence case, so a caller hits the harder path — the one
# that must widen the range and refuse on poor capture — unless they opt into an easy one.
_DEFAULT_CAPTURE = "mock-low-confidence"


class MockGradingProvider:
    """Returns fixed corners/edges/surface ``SubScore``s keyed on ``capture.capture_ref``."""

    async def grade(self, capture: GradingCapture) -> list[SubScore]:
        corners, edges, surface = _FIXTURES.get(capture.capture_ref) or _FIXTURES[_DEFAULT_CAPTURE]
        return [
            SubScore(axis=GradingAxis.CORNERS, score=corners[0], confidence=corners[1]),
            SubScore(axis=GradingAxis.EDGES, score=edges[0], confidence=edges[1]),
            SubScore(axis=GradingAxis.SURFACE, score=surface[0], confidence=surface[1]),
        ]
