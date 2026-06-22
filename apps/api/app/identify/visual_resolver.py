"""Fuse the artwork match with the OCR read into a ranked, confidence-scored result.

The visual matcher (perceptual-hash nearest-neighbour over catalog art) is the *primary*
signal — it identifies the card from its picture, robust to a collector number that never
OCR'd. The OCR read is demoted to what it's actually good for: corroboration, and the precise
tie-break between same-art reprints (ADR 0002), which the artwork alone cannot separate because
the reprints *share* that artwork.

Scoring encodes that hierarchy:
- Each candidate's base confidence comes from how close its art sat to the capture (Hamming
  distance → a calibrated 0–1 visual score).
- A collector-number agreement *pins* a printing: an exact "n/total" match is the strong boost
  that lets a confident read commit; a numerator-only match nudges; a disagreement is left
  alone (the art already carries the identity).
- The single best candidate earns a margin bonus when it sits clearly ahead of the runner-up —
  an unambiguous card can commit, while a same-art reprint pair (near-equal distances, tiny
  margin) stays just below the commit line and routes to the user's confirm, exactly as the
  product requires for high-value variants.
- Localization quality gently caps confidence: a poorly-framed capture can't yield a certain
  identification even on a lucky hash, but a clean crop isn't punished into permanent confirm.
"""

from __future__ import annotations

from app.identify.catalog import CardRead, _normalize_name
from app.identify.collector_number import NumberMatch, match_strength, parse_collector_number
from app.identify.image_index import ImageMatch
from app.schemas.cards import CardIdentity, RecognitionCandidate, RecognitionResult

# Hamming distance → visual base score, over the 384-bit YCbCr hash. Scaled from the original
# 64-bit calibration (falloff 24) by the 6× bit increase: a true match lands at a small fraction
# of the bits while distinct artwork sits far higher, so this falloff keeps the true card high
# and pushes unrelated cards toward the floor. Because the score normalises distance by this
# falloff, every downstream boost/threshold in 0–1 score space stays calibrated across bit lengths.
_VISUAL_FALLOFF = 144.0

# Collector-number agreement on top of the visual score.
_NUMBER_BOOST: dict[NumberMatch, float] = {
    NumberMatch.EXACT: 0.22,   # number + set total agree → pins this printing
    NumberMatch.PARTIAL: 0.08,  # numerator only → narrows
    NumberMatch.NONE: 0.0,
}
_NAME_BOOST = 0.05
# Localization quality cap: never a hard multiplier (that forced clean cards to perpetually
# confirm). 0.7 floor means even a loosely-framed but correctly-matched card stays decisive.
_QUALITY_FLOOR = 0.7
# Even a flawless fusion stays shy of 1.0 — recognition is never certain.
_MAX_RAW = 0.98
# When the top two candidates land within this confidence gap, the decision is *ambiguous* —
# the runner-up is nearly as good and nothing has pulled the leader clear. The classic case is a
# same-art reprint pair with no distinguishing collector number (ADR 0002): identical artwork
# ties their visual score, and a number that pinned one would have opened a gap wider than this.
_AMBIGUITY_DELTA = 0.12
# An ambiguous top is held in the confirm band (below the 0.70 commit threshold, above the 0.35
# recognition floor) so the flow surfaces both candidates instead of silently committing one.
_CONFIRM_CAP = 0.6


def _visual_score(distance: int) -> float:
    return max(0.0, 1.0 - distance / _VISUAL_FALLOFF)


def _gate_ambiguous_leader(ranked: list[tuple["CardIdentity", float]]) -> list[tuple["CardIdentity", float]]:
    """Hold a non-decisive leader (and its near-tie peers) in the confirm band.

    When the top two fused scores sit within ``_AMBIGUITY_DELTA``, no signal pulled the leader
    clear — the same-art reprint case ADR 0002 guards. Every candidate within that gap of the
    leader is capped to ``_CONFIRM_CAP`` so the pair lands together below the commit threshold
    and the flow surfaces both for the user to confirm, rather than committing the arbitrary
    nearer hash. (Capping only the leader would leave a tied peer ranked above it.)
    """
    if len(ranked) < 2 or ranked[0][1] - ranked[1][1] >= _AMBIGUITY_DELTA:
        return ranked
    leader = ranked[0][1]
    return [
        (identity, min(score, _CONFIRM_CAP)) if leader - score < _AMBIGUITY_DELTA else (identity, score)
        for identity, score in ranked
    ]


def _name_matches(read_name: str | None, card_name: str) -> bool:
    if not read_name:
        return False
    r = set(read_name.split())
    c = set(_normalize_name(card_name).split())
    return bool(r) and bool(c) and (r <= c or c <= r)


class VisualCardResolver:
    """Rank artwork matches into a ``RecognitionResult``, corroborated by the OCR read."""

    def resolve(self, matches: list[ImageMatch], read: CardRead, quality: float) -> RecognitionResult:
        if not matches:
            return RecognitionResult(candidates=[])

        read_number = parse_collector_number(read.collector_number)
        read_name = _normalize_name(read.name) if read.name else None
        quality_factor = _QUALITY_FLOOR + (1.0 - _QUALITY_FLOOR) * float(quality)

        # Score unclipped so the differentiating signals (a number that pins one reprint) survive
        # to the ranking and ambiguity comparison; _MAX_RAW is applied only to the emitted value.
        ranked: list[tuple[CardIdentity, float]] = []
        for match in matches:
            base = _visual_score(match.distance)
            number_match = match_strength(read_number, parse_collector_number(match.identity.collector_number))
            base += _NUMBER_BOOST[number_match]
            if _name_matches(read_name, match.identity.name):
                base += _NAME_BOOST
            ranked.append((match.identity, base * quality_factor))

        # A collector number that pins a *lower-ranked* reprint must be able to overtake the
        # art-nearest one (same-art pair: art ties, the number's boost decides). Rank by the
        # fused score, then gate the decision on how clearly the leader stands out.
        ranked.sort(key=lambda r: r[1], reverse=True)
        ranked = _gate_ambiguous_leader(ranked)
        return RecognitionResult(
            candidates=[
                RecognitionCandidate(identity=identity, confidence=round(min(_MAX_RAW, score), 4))
                for identity, score in ranked
            ]
        )
