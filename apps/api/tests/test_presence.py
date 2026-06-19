"""The Pokémon-card presence guard. Proves it accepts a cleanly-framed card and rejects a
non-card frame from real pixels, and that the recognizer skips the OCR pass when no card is
present (the cost the guard exists to save).
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.identify.catalog import CardRead, InMemoryCatalogIndex
from app.identify.presence import HeuristicCardPresence
from app.identify.provider import InHouseRecognitionProvider
from app.identify.resolver import CardResolver
from app.storage.memory import InMemoryCaptureStorage


def _card_png() -> bytes:
    # A card-shaped bright region filling a dark frame.
    arr = np.full((520, 380, 3), 12, dtype=np.uint8)
    arr[30:490, 30:350] = 150
    buffer = BytesIO()
    Image.fromarray(arr).save(buffer, format="PNG")
    return buffer.getvalue()


def _empty_png() -> bytes:
    # A near-uniform dark frame — a hand-in-the-dark / table / no-card miss.
    buffer = BytesIO()
    Image.new("RGB", (380, 520), (14, 14, 18)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_presence_accepts_a_framed_card() -> None:
    presence = HeuristicCardPresence().assess(_card_png())
    assert presence.present
    assert presence.confidence >= 0.45


def test_presence_rejects_a_non_card_frame() -> None:
    assert not HeuristicCardPresence().assess(_empty_png()).present


def test_presence_rejects_undecodable_bytes() -> None:
    assert not HeuristicCardPresence().assess(b"not-an-image").present


class _SpyReader:
    def __init__(self) -> None:
        self.calls = 0

    async def read(self, images):  # noqa: ANN001
        self.calls += 1
        return CardRead(collector_number="8/120", name="Tidecaller Leviath", quality=0.95)


@pytest.mark.asyncio
async def test_recognizer_skips_ocr_when_no_card_present() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([_empty_png()])
    reader = _SpyReader()
    provider = InHouseRecognitionProvider(
        store=store,
        reader=reader,
        resolver=CardResolver(InMemoryCatalogIndex()),
        presence=HeuristicCardPresence(),
    )

    result = await provider.recognize(_bundle(ref))

    assert result.candidates == []
    # The guard short-circuited before the (expensive) OCR read.
    assert reader.calls == 0


@pytest.mark.asyncio
async def test_recognizer_reads_when_a_card_is_present() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([_card_png()])
    reader = _SpyReader()
    provider = InHouseRecognitionProvider(
        store=store,
        reader=reader,
        resolver=CardResolver(InMemoryCatalogIndex()),
        presence=HeuristicCardPresence(),
    )

    result = await provider.recognize(_bundle(ref))

    assert reader.calls == 1
    assert result.candidates[0].identity.canonical_id == "origins-8"


from dataclasses import dataclass


@dataclass
class _Bundle:
    bundle_id: str
    image_count: int = 1


def _bundle(ref: str) -> _Bundle:
    return _Bundle(bundle_id=ref)
