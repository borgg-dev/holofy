"""Visual-first recognition provider — artwork match primary, text catalog as fallback.

The composed owned recognizer the review prescribed: localize and flatten the card once, hash
its artwork, and identify it by nearest catalog art; the OCR read corroborates and breaks
reprint ties. When the artwork index has no confident hit for a capture — the card isn't in the
built index yet, or the crop was too poor to match — it defers to the existing OCR-against-TCGdex
provider so coverage never regresses below today's behaviour. As the index grows toward the full
catalog, the fallback fires less and less.

It satisfies the same ``RecognitionProvider`` seam as the mock and the text provider, so the scan
service is unchanged. An empty/undeployed index makes this a transparent pass-through to the
fallback, so shipping the index is a data step, not a risky code switch.
"""

from __future__ import annotations

import logging

from app.grading.capture_store import CaptureStore
from app.identify.image_index import ImageMatchIndex
from app.identify.vision.phash import phash
from app.identify.vision.reader import VisionCardReader
from app.identify.vision.rectify import rectify_card
from app.identify.visual_resolver import VisualCardResolver
from app.providers.base import CaptureBundle, RecognitionProvider
from app.schemas.cards import RecognitionResult
from app.storage.base import CaptureNotFoundError

logger = logging.getLogger("holofy.recognition")


class VisualRecognitionProvider:
    def __init__(
        self,
        store: CaptureStore,
        reader: VisionCardReader,
        image_index: ImageMatchIndex,
        visual_resolver: VisualCardResolver,
        fallback: RecognitionProvider,
        *,
        max_match_distance: int = 14,
    ) -> None:
        self._store = store
        self._reader = reader
        self._index = image_index
        self._resolver = visual_resolver
        self._fallback = fallback
        # Above this Hamming distance the nearest catalog art is not a real match (the card is
        # outside the built index) — defer to the text/catalog path rather than assert a wrong,
        # far artwork hit. Calibrated from the observed gap: true matches ≤ ~8, distinct art ≥ ~14.
        self._max_match_distance = max_match_distance

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        if len(self._index) == 0:
            # Nothing fingerprinted — transparent pass-through to the text recognizer.
            return await self._fallback.recognize(bundle)
        try:
            image = await self._store.load(bundle.bundle_id)
        except CaptureNotFoundError:
            logger.info("recognition.recognize capture_not_found bundle=%s", bundle.bundle_id)
            return RecognitionResult(candidates=[])

        rect = rectify_card(image)
        image_hash = phash(rect.image)
        matches = self._index.query(image_hash, k=8)
        if not matches or matches[0].distance > self._max_match_distance:
            logger.info(
                "recognition.recognize visual_miss bundle=%s nearest=%s → text fallback",
                bundle.bundle_id,
                matches[0].distance if matches else None,
            )
            return await self._fallback.recognize(bundle)

        read = await self._reader.read_image(rect.image, rect.quality, fallback_bytes=image)
        result = self._resolver.resolve(matches, read, rect.quality)
        logger.info(
            "recognition.recognize visual bundle=%s found_quad=%s q=%.3f nearest=%d top=%.3f cand=%d",
            bundle.bundle_id,
            rect.found_quad,
            rect.quality,
            matches[0].distance,
            result.candidates[0].confidence if result.candidates else 0.0,
            len(result.candidates),
        )
        return result
