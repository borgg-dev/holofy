"""Card detection & crop — find the card in a capture and cut it out before reading.

The guided scan-frame puts a single card, brighter than its surface, roughly filling the
frame; this exploits exactly that. A relative-brightness threshold separates card from
ground, the foreground's bounding box is the crop, and a quality score falls out of how much
of the box is filled and whether its aspect ratio is card-like (~0.71, the 63×88mm ratio).
That quality is the honest ceiling the reader passes downstream — a sliver of glare or a
card lost in a busy background scores low, so a weak detection can't masquerade as a clean
read. Pure numpy/Pillow (no OpenCV in our own code), like the centering measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

# A standard trading card is 63×88mm → short/long ≈ 0.716. We score how close the detected
# region's aspect is to that, in either orientation.
_CARD_ASPECT = 0.716
# Below this share of bright pixels the frame is essentially empty — no card to read.
_MIN_FOREGROUND = 0.02


@dataclass(frozen=True, slots=True)
class CardCrop:
    image: np.ndarray  # RGB HxWx3 of the cropped card
    quality: float  # 0–1 confidence that this is a cleanly-framed card


def detect_card_crop(image_bytes: bytes) -> CardCrop:
    rgb = Image.open(BytesIO(image_bytes)).convert("RGB")
    arr = np.asarray(rgb)
    gray = np.asarray(rgb.convert("L"), dtype=np.float64)

    threshold = (float(gray.max()) + float(gray.min())) / 2.0
    foreground = gray > threshold
    if foreground.mean() < _MIN_FOREGROUND:
        # Nothing bright enough to be a card filling the frame.
        return CardCrop(image=arr, quality=0.05)

    rows = np.where(foreground.any(axis=1))[0]
    cols = np.where(foreground.any(axis=0))[0]
    r0, r1 = int(rows[0]), int(rows[-1])
    c0, c1 = int(cols[0]), int(cols[-1])
    crop = arr[r0 : r1 + 1, c0 : c1 + 1]

    fill = float(foreground[r0 : r1 + 1, c0 : c1 + 1].mean())
    height, width = crop.shape[0], crop.shape[1]
    aspect = min(width, height) / max(width, height)
    aspect_score = max(0.0, 1.0 - abs(aspect - _CARD_ASPECT) / _CARD_ASPECT)
    quality = float(np.clip(0.5 * fill + 0.5 * aspect_score, 0.0, 1.0))
    return CardCrop(image=crop, quality=quality)
