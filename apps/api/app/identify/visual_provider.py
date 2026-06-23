"""Visual-first recognition provider — artwork embedding primary, hash then text as fallback.

The composed owned recognizer the review prescribed, now learned-embedding-first: localize and
flatten the card once, embed its picture, and identify it by nearest catalog embedding; the OCR
read corroborates and breaks same-art reprint ties. Three tiers degrade gracefully:

1. **Embedding** (primary) — when the ONNX model + embedding index are deployed. Robust to real
   capture conditions; this is the path that clears the quality bar.
2. **Perceptual hash** — when only the hash index is present (model undeployed). The prior
   behaviour, kept so a partial deploy never regresses below today.
3. **Text/OCR-against-TCGdex** — when no artwork index has a confident hit, or none is built.

It satisfies the same ``RecognitionProvider`` seam as the mock and text providers, so the scan
service is unchanged. An empty/undeployed index makes this a transparent pass-through, so shipping
the model+index is a data step, not a risky code switch.
"""

from __future__ import annotations

import logging

import numpy as np

from app.grading.capture_store import CaptureStore
from app.identify.embedding_index import EmbeddingImageIndex
from app.identify.image_index import ImageMatchIndex
from app.identify.vision.embed import EmbeddingModelUnavailable, embed
from app.identify.vision.phash import phash
from app.identify.vision.reader import VisionCardReader
from app.identify.vision.rectify import rectify_card
from app.identify.visual_resolver import VisualCardResolver
from app.providers.base import CaptureBundle, RecognitionProvider
from app.schemas.cards import RecognitionResult
from app.storage.base import CaptureNotFoundError

logger = logging.getLogger("holofy.recognition")


def _merge_matches(embedding_matches: list, anchored: list) -> list:
    """Union the embedding nearest-neighbours with the OCR-anchored cards.

    The anchored cards are kept *unconditionally* — they're what the OCR collector-number identified,
    and they exist precisely because the raw embedding under-ranked them, so they must not be culled
    by cosine. We keep all anchored, then fill the rest of the slot budget with the highest-cosine
    embedding candidates. The resolver re-ranks with the OCR number/name boosts, so an anchored card
    can still win on a confident read even though its bare cosine sits below the wrong matches'."""
    result = list(anchored)
    seen = {m.identity.canonical_id for m in result}
    for match in sorted(embedding_matches, key=lambda m: m.cosine, reverse=True):
        if len(result) >= 8:
            break
        if match.identity.canonical_id not in seen:
            seen.add(match.identity.canonical_id)
            result.append(match)
    return result


class VisualRecognitionProvider:
    def __init__(
        self,
        store: CaptureStore,
        reader: VisionCardReader,
        image_index: ImageMatchIndex,
        visual_resolver: VisualCardResolver,
        fallback: RecognitionProvider,
        *,
        embedding_index: EmbeddingImageIndex | None = None,
        model_path: str | None = None,
        min_similarity: float = 0.68,
        max_match_distance: int = 84,
    ) -> None:
        self._store = store
        self._reader = reader
        self._index = image_index
        self._embedding_index = embedding_index
        self._model_path = model_path
        self._resolver = visual_resolver
        self._fallback = fallback
        # Below this cosine the nearest catalog embedding is not a real match (the card is outside
        # the built index) — defer to the hash/text path rather than assert a wrong, far hit.
        # Calibrated against real captures after the index build.
        self._min_similarity = min_similarity
        # The pHash equivalent of the abstain gate, used on the hash-fallback path.
        self._max_match_distance = max_match_distance

    @property
    def _embedding_ready(self) -> bool:
        return bool(self._model_path) and self._embedding_index is not None and len(self._embedding_index) > 0

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        if not self._embedding_ready and len(self._index) == 0:
            # Nothing fingerprinted — transparent pass-through to the text recognizer.
            return await self._fallback.recognize(bundle)
        try:
            image = await self._store.load(bundle.bundle_id)
        except CaptureNotFoundError:
            logger.info("recognition.recognize capture_not_found bundle=%s", bundle.bundle_id)
            return RecognitionResult(candidates=[])

        rect = rectify_card(image)
        if self._embedding_ready:
            result = await self._recognize_embedding(bundle, rect, image)
            if result is not None:
                return result
            # Embedding abstained (or model unavailable at runtime) — fall through to the hash path
            # if one is deployed, else the text recognizer.
            if len(self._index) == 0:
                return await self._fallback.recognize(bundle)
        return await self._recognize_hash(bundle, rect, image)

    async def _recognize_embedding(self, bundle, rect, image) -> RecognitionResult | None:
        """Embedding path. Returns a result, or None to abstain to the next tier."""
        try:
            oriented_image, matches = self._best_orientation_embed(rect.image)
            # OCR reads the rectifier's *upright* crop, not the embedding's best-match orientation:
            # a wrong card can score highest upside-down, and OCR on an inverted crop reads nothing,
            # throwing away the strongest identity signal. The rectifier already orients upright.
            read = await self._reader.read_image(rect.image, rect.quality, fallback_bytes=image)
            # OCR-anchored candidates: when OCR reads a collector number, pull the catalog cards that
            # actually carry it (scored by the upright embedding) into the candidate set — so a card
            # the OCR clearly identifies isn't lost when the raw nearest-neighbours mis-ranked it.
            if read.collector_number:
                upright = embed(rect.image, model_path=self._model_path)
                anchored = self._embedding_index.match_read(
                    upright, name=read.name, collector_number=read.collector_number
                )
                matches = _merge_matches(matches, anchored)
        except EmbeddingModelUnavailable as exc:
            logger.warning("recognition.recognize embedding_unavailable bundle=%s — %s", bundle.bundle_id, exc)
            return None
        best_cos = max((m.cosine for m in matches), default=None)
        if best_cos is None or best_cos < self._min_similarity:
            logger.info(
                "recognition.recognize embedding_miss bundle=%s nearest=%s → next tier",
                bundle.bundle_id,
                round(best_cos, 4) if best_cos is not None else None,
            )
            return None
        result = self._resolver.resolve(
            matches, read, rect.quality, preferred_language=getattr(bundle, "preferred_language", None)
        )
        logger.info(
            "recognition.recognize embedding bundle=%s found_quad=%s q=%.3f cos=%.4f ocr=%r top=%.3f cand=%d",
            bundle.bundle_id,
            rect.found_quad,
            rect.quality,
            best_cos,
            read.collector_number,
            result.candidates[0].confidence if result.candidates else 0.0,
            len(result.candidates),
        )
        return result

    async def _recognize_hash(self, bundle, rect, image) -> RecognitionResult:
        """Perceptual-hash path — the prior behaviour, the fallback when the model is undeployed."""
        if len(self._index) == 0:
            return await self._fallback.recognize(bundle)
        oriented_image, matches = self._best_orientation_hash(rect.image)
        if not matches or matches[0].distance > self._max_match_distance:
            logger.info(
                "recognition.recognize hash_miss bundle=%s nearest=%s → text fallback",
                bundle.bundle_id,
                matches[0].distance if matches else None,
            )
            return await self._fallback.recognize(bundle)
        read = await self._reader.read_image(oriented_image, rect.quality, fallback_bytes=image)
        result = self._resolver.resolve(
            matches, read, rect.quality, preferred_language=getattr(bundle, "preferred_language", None)
        )
        logger.info(
            "recognition.recognize hash bundle=%s found_quad=%s q=%.3f nearest=%d top=%.3f cand=%d",
            bundle.bundle_id,
            rect.found_quad,
            rect.quality,
            matches[0].distance,
            result.candidates[0].confidence if result.candidates else 0.0,
            len(result.candidates),
        )
        return result

    def _best_orientation_embed(self, image: "np.ndarray"):
        """Embed all four right-angle rotations; keep the one whose nearest catalog embedding is
        closest. The embedding (like a hash) is not rotation-invariant, and the rectifier's upright
        guess can be 90°/180° off; this aligns the crop to the upright catalog and feeds that same
        oriented crop to OCR."""
        best_image = image
        best_matches: list = []
        for k in range(4):
            candidate = image if k == 0 else np.rot90(image, k)
            vector = embed(candidate, model_path=self._model_path)
            matches = self._embedding_index.query(vector, k=8)
            if matches and (not best_matches or matches[0].cosine > best_matches[0].cosine):
                best_matches = matches
                best_image = candidate
        return best_image, best_matches

    def _best_orientation_hash(self, image: "np.ndarray") -> tuple["np.ndarray", list]:
        """Return the (image, matches) for whichever 90° rotation matches the hash index best."""
        best_image = image
        best_matches: list = []
        for k in range(4):
            candidate = image if k == 0 else np.rot90(image, k)
            matches = self._index.query(phash(candidate), k=8)
            if matches and (not best_matches or matches[0].distance < best_matches[0].distance):
                best_matches = matches
                best_image = candidate
        return best_image, best_matches
