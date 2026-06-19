"""The in-house recognition provider's orchestration: capture ref → read → resolve, behind
the standard RecognitionProvider seam. The visual read is a deterministic fake here (the OCR
engine is the one pluggable piece); this proves the owned pipeline wires together and that an
unresolvable capture recognizes nothing rather than erroring.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from app.identify.catalog import CardRead, InMemoryCatalogIndex
from app.identify.provider import InHouseRecognitionProvider
from app.identify.resolver import CardResolver
from app.storage.memory import InMemoryCaptureStorage


@dataclass(frozen=True, slots=True)
class _Bundle:
    """Satisfies the CaptureBundle Protocol the recognizer scores against."""

    bundle_id: str
    image_count: int = 1


class _FixedReader:
    """Returns a preset CardRead for whatever bytes it's handed (stands in for the OCR stage)."""

    def __init__(self, read: CardRead) -> None:
        self._read = read
        self.seen: list[int] = []

    async def read(self, images: Sequence[bytes]) -> CardRead:
        self.seen.append(len(images))
        return self._read


def _provider(reader: _FixedReader, store: InMemoryCaptureStorage) -> InHouseRecognitionProvider:
    return InHouseRecognitionProvider(store=store, reader=reader, resolver=CardResolver(InMemoryCatalogIndex()))


@pytest.mark.asyncio
async def test_recognizes_a_stored_capture_end_to_end() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([b"front-still"])
    reader = _FixedReader(CardRead(collector_number="8/120", name="Tidecaller Leviath", quality=0.96))

    result = await _provider(reader, store).recognize(_Bundle(bundle_id=ref))

    assert result.candidates[0].identity.canonical_id == "origins-8"
    # The provider loaded the stored still and handed it to the reader.
    assert reader.seen == [1]


@pytest.mark.asyncio
async def test_unresolvable_capture_recognizes_nothing() -> None:
    store = InMemoryCaptureStorage()
    reader = _FixedReader(CardRead(collector_number="8/120", quality=0.96))

    result = await _provider(reader, store).recognize(_Bundle(bundle_id="never-uploaded"))

    assert result.candidates == []
