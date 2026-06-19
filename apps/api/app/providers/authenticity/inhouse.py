"""In-house authenticity provider — the four visual reads from the real capture bytes.

Behind the same ``AuthenticityProvider`` seam the mock and a future CV ensemble use, so the
authenticity service is unchanged: it still composes these visual signals with the
deterministic catalog-existence cross-check into a risk *band*, never a verdict. Like the
in-house recognizer and grader, it resolves the capture's bytes from the object store itself
(the Protocol passes a reference, not pixels) and runs the owned visual analysis on them.
"""

from __future__ import annotations

from app.authenticity.visual import assess_visual_signals
from app.grading.capture_store import CaptureNotFoundError, CaptureStore
from app.providers.base import AuthenticityCapture
from app.schemas.authenticity import AuthenticitySignal


class InHouseAuthenticityProvider:
    def __init__(self, store: CaptureStore) -> None:
        self._store = store

    async def analyze(self, capture: AuthenticityCapture) -> list[AuthenticitySignal]:
        try:
            image = await self._store.load(capture.capture_ref)
        except CaptureNotFoundError:
            # No bytes to read — every visual signal is unreadable. The endpoint already
            # guards a missing ref with a typed 404, so this is a defensive empty read.
            return assess_visual_signals(b"", image_count=capture.image_count)
        return assess_visual_signals(image, image_count=capture.image_count)
