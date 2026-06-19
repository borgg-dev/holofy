"""The "is there a (Pokémon) card here?" guard — run before recognition spends an OCR pass.

A cheap binary gate: if the frame doesn't hold a cleanly-framed card (a hand, the table, a
random object, a blurred miss), short-circuit recognition rather than running the reader on
nothing. v1 reuses the card-detection quality (shape + fill); it genuinely rejects non-cards
but does *not* yet distinguish a Pokémon card from another game's — that multi-game classifier
is the deliberate expansion point, and it drops in behind this same ``assess`` (Pokémon-only
focus for now). Kept a Protocol so the trained classifier replaces the heuristic with no change
at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.identify.vision.detect import detect_card_crop


@dataclass(frozen=True, slots=True)
class CardPresence:
    present: bool
    confidence: float  # 0–1; the detection quality the decision was made on


class CardPresenceProvider(Protocol):
    def assess(self, image_bytes: bytes) -> CardPresence:
        """Decide whether a capture frames a gradeable card at all."""
        ...


# Below this detection quality the frame isn't a cleanly-framed card. Set a little below the
# point a real card lands so a slightly-skewed-but-genuine card still passes the gate; the
# recognizer's own quality-capping handles borderline reads from there.
_PRESENCE_THRESHOLD = 0.45


class HeuristicCardPresence:
    """v1 gate from the card-detection quality. The trained classifier replaces this later."""

    def __init__(self, threshold: float = _PRESENCE_THRESHOLD) -> None:
        self._threshold = threshold

    def assess(self, image_bytes: bytes) -> CardPresence:
        try:
            quality = float(detect_card_crop(image_bytes).quality)
        except Exception:
            # Undecodable / unreadable bytes are, by definition, not a card we can scan.
            return CardPresence(present=False, confidence=0.0)
        return CardPresence(present=quality >= self._threshold, confidence=round(quality, 4))
