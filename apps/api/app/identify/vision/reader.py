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

import logging

import numpy as np
from PIL import Image
from io import BytesIO

from app.identify.catalog import CardRead
from app.identify.collector_number import search_collector_number
from app.identify.vision.ocr import OcrEngine, OcrToken
from app.identify.vision.rectify import rectify_card

logger = logging.getLogger("holofy.recognition")

# The name occupies roughly the top third of a card, but a loose detection crop can leave
# the card lower in the frame, so we read name candidates from the top ~45% rather than a
# tight third — a confidently-read name is the rescue cue when the tiny collector number
# doesn't OCR, so we must not lose it to an overtight band.
_NAME_BAND = 0.45

# The collector number prints in the card's bottom strip; a bare numerator above this fraction
# of the card height is some other stat (attack damage, HP, year), not the collector number.
_NUMBER_BAND = 0.78


class VisionCardReader:
    def __init__(self, engine: OcrEngine) -> None:
        self._engine = engine

    async def read(self, images: Sequence[bytes]) -> CardRead:
        if not images:
            return CardRead(quality=0.0)
        # Localize and flatten the card once; OCR reads the upright rectified crop (slanted text
        # is what wrecked number/name reads). The same crop is hashed by the visual matcher
        # upstream, so the provider rectifies once and hands the image to read_image — this path
        # stays for callers that only have bytes.
        rect = rectify_card(images[0])
        return await self.read_image(rect.image, rect.quality, fallback_bytes=images[0])

    async def read_image(
        self, image: np.ndarray, quality: float, *, fallback_bytes: bytes | None = None
    ) -> CardRead:
        """Parse identity cues from an already-rectified card image (RGB ndarray).

        The provider rectifies the capture once and shares the crop between the visual matcher
        and this reader, so OCR and the artwork hash see the exact same upright card.
        """
        # OCR is blocking CPU work — keep it off the event loop.
        tokens = await asyncio.to_thread(self._engine.read_text, image)
        height = image.shape[0]
        number, number_conf = self._best_number(tokens, height)
        name, name_conf = self._name(tokens, height)
        if name is None and number is None and fallback_bytes is not None:
            # The rectified crop yielded nothing legible — try the full frame so a tight or
            # mis-localized crop can't silently blind the reader.
            full = await asyncio.to_thread(self._read_full_frame, fallback_bytes)
            if full is not None:
                tokens, height = full
                number, number_conf = self._best_number(tokens, height)
                name, name_conf = self._name(tokens, height)

        if not tokens:
            logger.info("recognition.read no_tokens detect_q=%.3f", quality)
            return CardRead(quality=round(quality * 0.2, 4))

        # Quality reflects how confidently the *identity* cues were read. The collector number
        # is the load-bearing cue when present, but a confidently-read name is a real signal in
        # its own right (it rescues the common case of a readable card whose tiny number didn't
        # OCR), so name-only reads keep the name's confidence rather than being discounted into
        # the reject band. Only a read with neither cue is treated as weak.
        if number is not None:
            ocr_conf = number_conf
        elif name is not None:
            ocr_conf = name_conf
        else:
            ocr_conf = 0.4 * (sum(t.confidence for t in tokens) / len(tokens))
        read_quality = round(float(quality) * float(ocr_conf), 4)
        logger.info(
            "recognition.read name=%r number=%r name_conf=%.2f num_conf=%.2f detect_q=%.3f quality=%.3f ntokens=%d",
            name, number, name_conf, number_conf, quality, read_quality, len(tokens),
        )
        return CardRead(
            collector_number=number,
            name=name,
            quality=read_quality,
        )

    def _read_full_frame(self, image_bytes: bytes) -> tuple[list[OcrToken], int] | None:
        try:
            arr = np.asarray(Image.open(BytesIO(image_bytes)).convert("RGB"))
        except Exception:
            return None
        return self._engine.read_text(arr), int(arr.shape[0])

    @staticmethod
    def _best_number(tokens: Sequence[OcrToken], height: int = 0) -> tuple[str | None, float]:
        # The collector number is either an unambiguous "n/total" (accepted wherever it reads)
        # or a bare numerator printed in the card's bottom strip. A *bare* numerator anywhere
        # else is some other stat — attack damage, HP, the year, an "LV." — so we accept one
        # only from the bottom band, never mid-card. This stops the recognizer mis-pinning to a
        # wrong printing off a damage number when the real corner number didn't OCR.
        bottom_cutoff = height * _NUMBER_BAND if height else 0.0
        best: tuple[tuple[bool, float], str] | None = None
        for token in tokens:
            parsed = search_collector_number(token.text)
            if parsed is None or parsed.numerator is None:
                continue
            has_total = parsed.denominator is not None
            if not has_total and height and token.cy < bottom_cutoff:
                continue  # a bare number above the bottom strip isn't the collector number
            rank = (has_total, token.confidence)
            # Store the cleaned "n/total", not the raw OCR token, so the resolver matches on the
            # canonical number rather than the noisy line it was embedded in.
            if best is None or rank > best[0]:
                best = (rank, parsed.raw)
        return (best[1], best[0][1]) if best is not None else (None, 0.0)

    @staticmethod
    def _name(tokens: Sequence[OcrToken], height: int) -> tuple[str | None, float]:
        cutoff = height * _NAME_BAND
        named = [t for t in tokens if _looks_like_name(t.text) and t.cy <= cutoff]
        if not named:
            named = [t for t in tokens if _looks_like_name(t.text)]
        if not named:
            return None, 0.0
        # The card name is set in the largest font in the top band. Take the single most
        # prominent token — tallest box, tie-broken by length then OCR confidence — as the
        # search term, rather than concatenating the band: joining pulled in the "Basic Pokémon"
        # type label and stray OCR noise, corrupting the query. TCGdex name search is a fuzzy
        # contains-match, so the card's core name token ("Charizard") still recalls its suffixed
        # printings ("Charizard ex"); the collector number does the precise pinning downstream.
        best = max(named, key=lambda t: (t.height, len(t.text.strip()), t.confidence))
        return best.text.strip(), float(best.confidence)


# Top-line type labels that sit where the name does but are never the creature name. A real
# Pokémon name never contains "pokémon", "basic", or a stage marker, so a token carrying one is
# the type label ("Basic Pokémon", "Stage 1 Pokémon"), not the name — drop it from candidates.
_LABEL_MARKERS = ("pokemon", "pokémon", "basic", "stage")


def _looks_like_name(text: str) -> bool:
    stripped = text.strip()
    lowered = stripped.lower()
    if any(marker in lowered for marker in _LABEL_MARKERS):
        return False
    letters = sum(ch.isalpha() for ch in stripped)
    # A name token is mostly letters and more than an abbreviation — excludes the number,
    # HP, stray symbols, and energy-cost glyphs the OCR may pick up.
    return len(stripped) >= 3 and letters >= max(3, len(stripped) - 1)
