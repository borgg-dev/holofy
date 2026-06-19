"""In-house grading provider — our owned corners/edges/surface reads.

Behind the same ``GradingProvider`` seam the mock and a bought grader use, so the pre-grade
service is unchanged: it still composes these three with the in-house centering measurement
into an honest range. Like the in-house recognizer, it resolves the capture's bytes from the
object store itself (the Protocol passes a reference, not pixels) and runs the classical-CV
condition analysis on them.
"""

from __future__ import annotations

from app.grading.capture_store import CaptureStore
from app.grading.condition import assess_condition
from app.providers.base import GradingCapture
from app.schemas.grading import GradingAxis, SubScore


class InHouseGradingProvider:
    def __init__(self, store: CaptureStore) -> None:
        self._store = store

    async def grade(self, capture: GradingCapture) -> list[SubScore]:
        image = await self._store.load(capture.capture_ref)
        reads = assess_condition(image)
        return [
            SubScore(axis=axis, score=reads[axis].score, confidence=reads[axis].confidence)
            for axis in (GradingAxis.CORNERS, GradingAxis.EDGES, GradingAxis.SURFACE)
        ]
