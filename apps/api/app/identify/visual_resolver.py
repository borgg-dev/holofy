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
from app.identify.image_index import ScoredMatch
from app.schemas.cards import CardIdentity, RecognitionCandidate, RecognitionResult

# Collector-number agreement on top of the visual score.
_NUMBER_BOOST: dict[NumberMatch, float] = {
    NumberMatch.EXACT: 0.22,   # number + set total agree → pins this printing
    NumberMatch.PARTIAL: 0.08,  # numerator only → narrows
    NumberMatch.NONE: 0.0,
}
# A discriminative name read must be *decisive*, like an exact collector number — because the
# index holds both the English and French print of every card, and a same-art EN/FR twin shares
# the artwork (so the embedding ties them) AND usually the collector number (so the number boost
# lifts both equally). The *name* is then the only separator, and only when the localized names
# actually differ ("Dracaufeu" vs "Charizard"): there the read pins the language and must clear the
# ambiguity gate to commit. When the names match across languages ("Pikachu" = "Pikachu"), no
# candidate is boosted over the other, the pair stays tied, and the flow honestly routes to confirm
# — we genuinely cannot tell EN from FR from the picture, and the price differs by market. Hence the
# boost is set above _AMBIGUITY_DELTA so a discriminative name decides, while a same-name reprint or
# same-name twin stays ambiguous and a differing collector number still does the reprint tie-break.
_NAME_BOOST = 0.18
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


def _gate_ambiguous_leader(
    ranked: list[tuple["CardIdentity", float]], preferred_language: str | None = None
) -> list[tuple["CardIdentity", float]]:
    """Hold an ambiguous result in the confirm band so nothing auto-commits a guess.

    When the top two fused scores sit within ``_AMBIGUITY_DELTA``, no signal pulled the leader
    clear — the same-art reprint / same-name EN·FR twin case (ADR 0002). The whole result is then
    capped to ``_CONFIRM_CAP``: the tied leaders land below the commit threshold for the user to
    pick between, and — crucially — a *lower, non-tied* candidate can't keep its uncapped score and
    leapfrog the capped leaders into a wrong auto-commit (the failure where a correct EN·FR 58/102
    pair was held at 0.6 while an unrelated 87/130 print stayed at 0.98 and committed). Capping the
    full list keeps the genuinely-likely cards on top (order is preserved) while guaranteeing an
    ambiguous scan asks rather than commits.

    The one tie a *locale* can break: when the ambiguity is purely a language twin — every tied
    member shares the leader's name and collector number, differing only in language (a card and
    its EN·FR counterpart, which the picture cannot separate because the spelling is identical, e.g.
    "Pikachu") — and the user has a language preference matching exactly one tied member, that
    member commits. The user's locale tells us which market's print they actually hold, which the
    art genuinely cannot. This never overrides text evidence: a discriminative name read already
    pulls the right-language print clear *before* this gate fires, so we only reach here when the
    names match and only language separates the tie.
    """
    if len(ranked) < 2 or ranked[0][1] - ranked[1][1] >= _AMBIGUITY_DELTA:
        return ranked
    leader = ranked[0][0]
    cluster = [(i, s) for i, s in ranked if ranked[0][1] - s < _AMBIGUITY_DELTA]
    if preferred_language:
        twins = all(i.name == leader.name and i.collector_number == leader.collector_number for i, _ in cluster)
        preferred = [i for i, _ in cluster if i.language == preferred_language]
        if twins and len(preferred) == 1:
            chosen = preferred[0]
            # The chosen twin keeps its (committing) score; everything else drops to confirm so it
            # leads cleanly and nothing else can auto-commit.
            return [(i, s if i is chosen else min(s, _CONFIRM_CAP)) for i, s in ranked]
    return [(identity, min(score, _CONFIRM_CAP)) for identity, score in ranked]


def _name_matches(read_name: str | None, card_name: str) -> bool:
    if not read_name:
        return False
    r = set(read_name.split())
    c = set(_normalize_name(card_name).split())
    return bool(r) and bool(c) and (r <= c or c <= r)


class VisualCardResolver:
    """Rank artwork matches into a ``RecognitionResult``, corroborated by the OCR read."""

    def resolve(
        self,
        matches: list[ScoredMatch],
        read: CardRead,
        quality: float,
        preferred_language: str | None = None,
    ) -> RecognitionResult:
        if not matches:
            return RecognitionResult(candidates=[])

        read_number = parse_collector_number(read.collector_number)
        read_name = _normalize_name(read.name) if read.name else None
        quality_factor = _QUALITY_FLOOR + (1.0 - _QUALITY_FLOOR) * float(quality)

        # Score unclipped so the differentiating signals (a number that pins one reprint) survive
        # to the ranking and ambiguity comparison; _MAX_RAW is applied only to the emitted value.
        # ``base_score`` is the descriptor's own 0–1 confidence — hash falloff or calibrated cosine
        # — so this fusion is identical whether the matches came from the hash or embedding index.
        ranked: list[tuple[CardIdentity, float]] = []
        for match in matches:
            base = match.base_score
            number_match = match_strength(read_number, parse_collector_number(match.identity.collector_number))
            base += _NUMBER_BOOST[number_match]
            if _name_matches(read_name, match.identity.name):
                base += _NAME_BOOST
            ranked.append((match.identity, base * quality_factor))

        # A collector number that pins a *lower-ranked* reprint must be able to overtake the
        # art-nearest one (same-art pair: art ties, the number's boost decides). Rank by the
        # fused score, then gate the decision on how clearly the leader stands out.
        ranked.sort(key=lambda r: r[1], reverse=True)
        ranked = _gate_ambiguous_leader(ranked, preferred_language)
        # Re-sort after the gate: capping an ambiguous top cluster to the confirm band can drop it
        # below an uncapped lower candidate, so the emitted order (and thus the flow's top pick)
        # must reflect the *final* confidences, not the pre-cap ranking.
        ranked.sort(key=lambda r: r[1], reverse=True)
        return RecognitionResult(
            candidates=[
                RecognitionCandidate(identity=identity, confidence=round(min(_MAX_RAW, score), 4))
                for identity, score in ranked
            ]
        )
