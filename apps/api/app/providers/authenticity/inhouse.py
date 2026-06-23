"""In-house authenticity provider — the four visual reads from the real capture bytes.

Behind the same ``AuthenticityProvider`` seam the mock and a future CV ensemble use, so the
authenticity service is unchanged: it still composes these visual signals with the
deterministic catalog-existence cross-check into a risk *band*, never a verdict. Like the
in-house recognizer and grader, it resolves the capture's bytes from the object store itself
(the Protocol passes a reference, not pixels) and runs the owned visual analysis on them.
"""

from __future__ import annotations

from app.authenticity.artwork_reference import assess_artwork_match
from app.authenticity.visual import assess_visual_signals
from app.grading.capture_store import CaptureNotFoundError, CaptureStore
from app.identify.embedding_index import EmbeddingImageIndex
from app.providers.base import AuthenticityCapture
from app.schemas.authenticity import AuthenticitySignal


class InHouseAuthenticityProvider:
    def __init__(
        self,
        store: CaptureStore,
        *,
        embedding_index: EmbeddingImageIndex | None = None,
        model_path: str | None = None,
    ) -> None:
        self._store = store
        # The recognizer's embedding index + model power the artwork-reference reassurance signal —
        # when both are deployed and the capture names a card we hold a reference for.
        self._embedding_index = embedding_index
        self._model_path = model_path

    async def analyze(self, capture: AuthenticityCapture) -> list[AuthenticitySignal]:
        try:
            image = await self._store.load(capture.capture_ref)
        except CaptureNotFoundError:
            # No bytes to read — every visual signal is unreadable. The endpoint already
            # guards a missing ref with a typed 404, so this is a defensive empty read.
            return assess_visual_signals(b"", image_count=capture.image_count)
        signals = assess_visual_signals(image, image_count=capture.image_count)
        artwork = self._artwork_signal(capture, image)
        return [*signals, artwork] if artwork is not None else signals

    def _artwork_signal(self, capture: AuthenticityCapture, image: bytes) -> AuthenticitySignal | None:
        """The embedding artwork-reference reassurance signal, when we can compute it."""
        canonical_id = getattr(capture, "canonical_id", None)
        if not (self._embedding_index and self._model_path and canonical_id):
            return None
        reference = self._embedding_index.reference(canonical_id)
        return assess_artwork_match(image, reference, model_path=self._model_path)
