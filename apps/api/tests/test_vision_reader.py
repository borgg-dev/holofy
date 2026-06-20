"""The real visual stage. Two layers:

- Parsing/geometry (fast, deterministic): a fake OCR engine feeds located tokens, and we
  assert the reader pulls the collector number from the bottom token, the name from the top
  band, and caps quality by OCR confidence.
- A genuine end-to-end read (the `ocr` marker): render a synthetic card to PNG, run the real
  RapidOCR engine + detection + resolver, and assert it identifies the card from pixels — no
  fixtures, no network. Skipped automatically if onnxruntime/RapidOCR isn't installed.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.identify.catalog import InMemoryCatalogIndex
from app.identify.resolver import CardResolver
from app.identify.vision.ocr import OcrToken
from app.identify.vision.reader import VisionCardReader


class _FakeEngine:
    def __init__(self, tokens: list[OcrToken]) -> None:
        self._tokens = tokens

    def read_text(self, image: np.ndarray) -> list[OcrToken]:  # noqa: ARG002
        return self._tokens


def _png(width: int = 360, height: int = 500, color: int = 235) -> bytes:
    # A bright card filling a dark frame — what detection expects from the guided scan.
    image = Image.new("RGB", (width + 40, height + 40), (12, 12, 16))
    ImageDraw.Draw(image).rectangle((20, 20, 20 + width, 20 + height), fill=(color, color, color))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_reader_parses_number_from_bottom_and_name_from_top() -> None:
    tokens = [
        # The "Basic Pokémon" type label sits where the name does but must be dropped, even at
        # higher OCR confidence, so it never becomes the search term.
        OcrToken(text="BasicPokemon", confidence=0.99, cx=120, cy=28, height=14),
        # The name is the most prominent token — the tallest box.
        OcrToken(text="Tidecaller Leviath", confidence=0.97, cx=180, cy=50, height=30),
        OcrToken(text="58 HP", confidence=0.80, cx=300, cy=44, height=14),  # not a name/number
        OcrToken(text="8/120", confidence=0.95, cx=60, cy=470, height=12),
    ]
    read = await VisionCardReader(_FakeEngine(tokens)).read([_png()])

    assert read.collector_number == "8/120"
    assert read.name == "Tidecaller Leviath"
    assert 0.0 < read.quality <= 1.0


@pytest.mark.asyncio
async def test_reader_with_no_tokens_is_low_quality() -> None:
    read = await VisionCardReader(_FakeEngine([])).read([_png()])
    assert read.collector_number is None
    assert read.quality < 0.3


@pytest.mark.asyncio
async def test_reader_handles_an_empty_capture() -> None:
    read = await VisionCardReader(_FakeEngine([])).read([])
    assert read.quality == 0.0


def _rendered_card(name: str, number: str) -> bytes:
    """A synthetic but genuine card image: name in the top band, number in a bottom corner."""
    width, height = 420, 580
    image = Image.new("RGB", (width, height), (15, 15, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, width - 30, height - 30), fill=(238, 238, 238))
    font_name = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    font_num = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
    draw.text((55, 55), name, fill=(10, 10, 10), font=font_name)
    draw.text((55, height - 90), number, fill=(10, 10, 10), font=font_num)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.ocr
@pytest.mark.asyncio
async def test_genuine_pixels_to_identity_end_to_end() -> None:
    pytest.importorskip("rapidocr_onnxruntime")
    from app.identify.vision.ocr import RapidOcrEngine

    reader = VisionCardReader(RapidOcrEngine())
    read = await reader.read([_rendered_card("Tidecaller Leviath", "8/120")])

    # The engine genuinely read the pixels into the identity cues.
    assert read.collector_number == "8/120"
    assert "tidecaller" in (read.name or "").lower()

    # And those cues resolve to the right catalog card — pixels in, identity out, no fixtures.
    result = await CardResolver(InMemoryCatalogIndex()).resolve(read)
    assert result.candidates[0].identity.canonical_id == "origins-8"
