"""The in-house recognition provider — our owned alternative to a bought recognizer.

Composes the three owned stages behind the standard ``RecognitionProvider`` seam: resolve
the capture reference to its stored stills, read identity cues from them (``CardReader``),
and rank catalog candidates (``CardResolver``). The scan service calls this exactly as it
calls the mock or any bought provider — it never learns recognition was done in-house.

An unresolvable capture reference is an empty result (the honest "couldn't read a card"
branch), not an error: a scan of a missing/expired upload simply recognizes nothing.
"""

from __future__ import annotations

from app.grading.capture_store import CaptureStore
from app.identify.reader import CardReader
from app.identify.resolver import CardResolver
from app.providers.base import CaptureBundle
from app.schemas.cards import RecognitionResult
from app.storage.base import CaptureNotFoundError


class InHouseRecognitionProvider:
    def __init__(self, store: CaptureStore, reader: CardReader, resolver: CardResolver) -> None:
        self._store = store
        self._reader = reader
        self._resolver = resolver

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        try:
            image = await self._store.load(bundle.bundle_id)
        except CaptureNotFoundError:
            return RecognitionResult(candidates=[])
        read = await self._reader.read([image])
        return await self._resolver.resolve(read)
