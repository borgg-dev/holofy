"""The in-house recognition provider — our owned alternative to a bought recognizer.

Composes the three owned stages behind the standard ``RecognitionProvider`` seam: resolve
the capture reference to its stored stills, read identity cues from them (``CardReader``),
and rank catalog candidates (``CardResolver``). The scan service calls this exactly as it
calls the mock or any bought provider — it never learns recognition was done in-house.

An unresolvable capture reference is an empty result (the honest "couldn't read a card"
branch), not an error: a scan of a missing/expired upload simply recognizes nothing.
"""

from __future__ import annotations

import logging

from app.grading.capture_store import CaptureStore
from app.identify.presence import CardPresenceProvider
from app.identify.reader import CardReader
from app.identify.resolver import CardResolver
from app.providers.base import CaptureBundle
from app.schemas.cards import RecognitionResult
from app.storage.base import CaptureNotFoundError

logger = logging.getLogger("holofy.recognition")


class InHouseRecognitionProvider:
    def __init__(
        self,
        store: CaptureStore,
        reader: CardReader,
        resolver: CardResolver,
        presence: CardPresenceProvider,
    ) -> None:
        self._store = store
        self._reader = reader
        self._resolver = resolver
        self._presence = presence

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        try:
            image = await self._store.load(bundle.bundle_id)
        except CaptureNotFoundError:
            logger.info("recognition.recognize capture_not_found bundle=%s", bundle.bundle_id)
            return RecognitionResult(candidates=[])
        # The presence heuristic (a brightness/aspect score) is recorded as a signal but is no
        # longer a hard gate: on real phone photos it mis-scored cleanly-readable cards and
        # silently skipped OCR. The OCR read + catalog match is the real decision — a frame with
        # no card simply yields no name and resolves to no candidates, which is the honest gate.
        presence = self._presence.assess(image)
        read = await self._reader.read([image])
        result = await self._resolver.resolve(read)
        logger.info(
            "recognition.recognize bundle=%s presence=%.3f candidates=%d top=%.3f",
            bundle.bundle_id,
            presence.confidence,
            len(result.candidates),
            result.candidates[0].confidence if result.candidates else 0.0,
        )
        return result
