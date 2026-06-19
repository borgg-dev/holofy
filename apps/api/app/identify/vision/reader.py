"""The real visual stage: a capture's stills → a ``CardRead`` the resolver can rank.

Composes the owned detection/crop with the OCR engine, then parses the located text into the
two cues identity turns on: the collector number (the precise pin) and the card name (the
weaker corroborating cue). Position matters — the name sits in the card's top band and the
number in a bottom corner — so token geometry, not guesswork, decides which is which.

Honest quality: the read's quality is the detection quality scaled by how confidently the
*relevant* tokens were recognized. A clean crop whose number OCR'd at 0.4 is a low-quality
read, and the resolver caps its confidence accordingly — exactly the behaviour that sends a
shaky read to a confirm rather than a wrong commit.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from app.identify.catalog import CardRead
from app.identify.collector_number import parse_collector_number
from app.identify.vision.detect import detect_card_crop
from app.identify.vision.ocr import OcrEngine, OcrToken

# The name occupies roughly the top third of a card; tokens whose centre sits above this
# fraction of the crop height are name candidates.
_NAME_BAND = 0.33


class VisionCardReader:
    def __init__(self, engine: OcrEngine) -> None:
        self._engine = engine

    async def read(self, images: Sequence[bytes]) -> CardRead:
        if not images:
            return CardRead(quality=0.0)

        crop = detect_card_crop(images[0])
        # OCR is blocking CPU work — keep it off the event loop.
        tokens = await asyncio.to_thread(self._engine.read_text, crop.image)
        if not tokens:
            return CardRead(quality=round(crop.quality * 0.2, 4))

        height = crop.image.shape[0]
        number, number_conf = self._best_number(tokens)
        name = self._name(tokens, height)

        # Quality leans on the number's read confidence (the load-bearing cue); with no number
        # found, fall back to the mean token confidence, discounted.
        if number is not None:
            ocr_conf = number_conf
        else:
            ocr_conf = 0.5 * (sum(t.confidence for t in tokens) / len(tokens))
        return CardRead(
            collector_number=number,
            name=name,
            quality=round(float(crop.quality) * float(ocr_conf), 4),
        )

    @staticmethod
    def _best_number(tokens: Sequence[OcrToken]) -> tuple[str | None, float]:
        # Prefer a full "n/total" over a bare numerator, then higher OCR confidence.
        best: tuple[tuple[bool, float], str] | None = None
        for token in tokens:
            parsed = parse_collector_number(token.text)
            if parsed is None or parsed.numerator is None:
                continue
            rank = (parsed.denominator is not None, token.confidence)
            if best is None or rank > best[0]:
                best = (rank, token.text)
        return (best[1], best[0][1]) if best is not None else (None, 0.0)

    @staticmethod
    def _name(tokens: Sequence[OcrToken], height: int) -> str | None:
        cutoff = height * _NAME_BAND
        named = [t for t in tokens if _looks_like_name(t.text) and t.cy <= cutoff]
        if not named:
            named = [t for t in tokens if _looks_like_name(t.text)]
        if not named:
            return None
        named.sort(key=lambda t: (t.cy, t.cx))
        return " ".join(t.text for t in named)


def _looks_like_name(text: str) -> bool:
    stripped = text.strip()
    letters = sum(ch.isalpha() for ch in stripped)
    # A name token is mostly letters and more than an abbreviation — excludes the number,
    # HP, stray symbols, and energy-cost glyphs the OCR may pick up.
    return len(stripped) >= 3 and letters >= max(3, len(stripped) - 1)
