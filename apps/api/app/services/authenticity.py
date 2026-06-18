"""Authenticity composition: visual signals + catalog cross-check → a *risk band*.

This composes the four visual signals the provider reads (print pattern, holo, font/layout,
cardstock) with the deterministic catalog-existence cross-check into an honest authenticity
**risk band** — never a binary fake/genuine verdict (charter §3.5). The honesty rules live
in the composition, not in copy:

1. **Value-gate first.** Authenticity screening is only meaningful on cards worth faking;
   below the configured value threshold the service returns ``not_assessed`` rather than a
   fake-precise score on a card no one counterfeits.
2. **Refuse over guess.** If too few signals can be read confidently, the service returns
   ``retake`` with reasons rather than a confident wrong band — the same refuse posture as
   pre-grade. Unreadable signals widen uncertainty; they are never scored as evidence either
   way.
3. **A never-printed variant is the strongest contributor.** A catalog ``not_in_catalog``
   read (a variant that was never issued for a real card) pushes hard toward elevated risk;
   a ``confirmed`` printing reassures; an ``unverifiable`` one is our reference gap and must
   not count against the card.
4. **Band, not boolean.** The composite is a confidence-weighted lean across the signals,
   mapped to ``strong_signals`` / ``inconclusive`` / ``elevated_risk``. The most adverse
   thing the service can say is "elevated risk — seek professional authentication". There is
   no code path that emits "fake" or "genuine".

The service does not own persistence; the endpoint logs the result through the repository,
mirroring the scan and pre-grade flows.
"""

from __future__ import annotations

from decimal import Decimal

from app.authenticity.catalog_existence import (
    CatalogExistence,
    CatalogExistenceChecker,
    CardTuple,
)
from app.providers.base import AuthenticityCapture, AuthenticityProvider
from app.schemas.authenticity import (
    AuthenticityAssessment,
    AuthenticityResponse,
    AuthenticitySignal,
    AuthenticityStatus,
    RiskBand,
    SignalDetail,
    SignalKind,
    SignalObservation,
)

# How each visual observation leans, in [-1, +1]: positive = consistent with genuine,
# negative = diverges the way fakes do. ``inconclusive``/``unreadable`` carry no lean — they
# only erode confidence, never count as evidence either way (rule 2).
_OBSERVATION_LEAN: dict[SignalObservation, float] = {
    SignalObservation.CONSISTENT: 1.0,
    SignalObservation.INCONCLUSIVE: 0.0,
    SignalObservation.DEVIATION: -1.0,
    SignalObservation.UNREADABLE: 0.0,
}

# The catalog cross-check is weighted above any single visual signal: a never-printed variant
# is near-dispositive evidence, where one coarse dot pattern is suggestive. ``confirmed``
# reassures but never *proves* genuine, so its positive lean is capped below 1.0.
_CATALOG_LEAN: dict[CatalogExistence, float] = {
    CatalogExistence.CONFIRMED: 0.6,
    CatalogExistence.UNVERIFIABLE: 0.0,
    CatalogExistence.NOT_IN_CATALOG: -1.0,
}
_CATALOG_WEIGHT = 2.5
# The catalog read carries its own confidence: a definitive reference lookup, not a noisy
# pixel read. ``unverifiable`` contributes nothing, so its confidence is irrelevant.
_CATALOG_CONFIDENCE = 0.95

# Band thresholds on the composite lean (confidence-weighted mean in [-1, +1]). Above the
# upper bound the evidence is consistent with genuine; below the lower bound it diverges
# enough to flag. The asymmetry is deliberate — we lean toward "inconclusive" over an
# adverse call, because a false risk flag is the costlier error (charter §3.5).
_STRONG_SIGNALS_AT = 0.45
_ELEVATED_RISK_AT = -0.2

# Below this many signals read with usable confidence, the capture can't support an honest
# assessment and the service refuses (retake). The catalog check counts toward this when it
# is decisive (confirmed / not_in_catalog), since it needs no pixels.
_MIN_READABLE_SIGNALS = 2
# A signal read below this confidence is treated as not usable evidence.
_USABLE_CONFIDENCE = 0.4


class AuthenticityService:
    def __init__(
        self,
        *,
        provider: AuthenticityProvider,
        catalog: CatalogExistenceChecker,
        min_value_eur: float,
    ) -> None:
        self._provider = provider
        self._catalog = catalog
        self._min_value_eur = min_value_eur

    async def assess(
        self,
        capture: AuthenticityCapture,
        *,
        card: CardTuple,
        value_eur: Decimal | None,
    ) -> AuthenticityResponse:
        """Screen a capture for authenticity risk, gated on the card's value.

        ``card`` is the resolved disambiguation tuple (for the catalog cross-check);
        ``value_eur`` is the card's current € value (for the value gate). A card below the
        screening threshold returns ``not_assessed``; a capture too poor to read returns
        ``retake``; otherwise an ``assessed`` risk band with the per-signal breakdown.
        """
        if not self._worth_screening(value_eur):
            return _not_assessed(value_eur, self._min_value_eur)

        visual_signals = await self._provider.analyze(capture)
        catalog_existence = await self._catalog.check(card)
        catalog_signal = _catalog_signal(catalog_existence)
        signals = [*visual_signals, catalog_signal]

        # A decisive catalog read needs no pixels — a never-printed variant alone is enough
        # evidence to assess. Otherwise the visual signals must carry the floor, or we refuse
        # rather than guess from a capture too poor to read.
        decisive_catalog = catalog_existence is CatalogExistence.NOT_IN_CATALOG
        if not decisive_catalog and _usable_signal_count(signals) < _MIN_READABLE_SIGNALS:
            return _retake(visual_signals)

        risk_band, confidence = _compose(signals, existence=catalog_existence)
        value = float(value_eur) if value_eur is not None else None
        assessment = AuthenticityAssessment(
            risk_band=risk_band,
            confidence=confidence,
            signals=signals,
            # Above the value threshold we always surface the "seek a professional" prompt —
            # the screen is a pre-check before paying for authentication, not a substitute.
            recommend_authentication=True,
            reference_value_eur=value,
        )
        return AuthenticityResponse(
            status=AuthenticityStatus.ASSESSED, assessment=assessment
        )

    def _worth_screening(self, value_eur: Decimal | None) -> bool:
        # No value resolved → we can't justify screening (and can't claim it's needed). An
        # unpriced card is treated as below-threshold: screening is offered once it's valued.
        if value_eur is None:
            return False
        return value_eur >= Decimal(str(self._min_value_eur))


def _catalog_signal(existence: CatalogExistence) -> AuthenticitySignal:
    """Render the catalog cross-check as a signal in the same shape as the visual reads."""
    observation, detail = _CATALOG_OBSERVATION[existence]
    return AuthenticitySignal(
        kind=SignalKind.CATALOG_EXISTENCE,
        observation=observation,
        confidence=_CATALOG_CONFIDENCE if existence is not CatalogExistence.UNVERIFIABLE else 0.2,
        detail=detail,
    )


_CATALOG_OBSERVATION: dict[CatalogExistence, tuple[SignalObservation, SignalDetail]] = {
    CatalogExistence.CONFIRMED: (
        SignalObservation.CONSISTENT,
        SignalDetail.CATALOG_PRINTING_CONFIRMED,
    ),
    CatalogExistence.NOT_IN_CATALOG: (
        SignalObservation.DEVIATION,
        SignalDetail.CATALOG_PRINTING_NOT_FOUND,
    ),
    CatalogExistence.UNVERIFIABLE: (
        SignalObservation.INCONCLUSIVE,
        SignalDetail.CATALOG_NO_COVERAGE,
    ),
}


def _usable_signal_count(signals: list[AuthenticitySignal]) -> int:
    """How many signals carry usable evidence — a readable observation read confidently.

    ``unreadable`` reads never count (no evidence); a confidently-read consistent or deviating
    signal does. This is what the refuse threshold gates on.
    """
    return sum(
        1
        for s in signals
        if s.observation is not SignalObservation.UNREADABLE
        and s.confidence >= _USABLE_CONFIDENCE
    )


def _compose(
    signals: list[AuthenticitySignal], *, existence: CatalogExistence
) -> tuple[RiskBand, float]:
    """Combine the signals into a risk band and an overall confidence.

    A ``not_in_catalog`` read is **dispositive** (rule 3): a variant that was never printed
    floors the band at ``elevated_risk`` no matter how clean the visuals look — that is the
    strongest single fake contributor, and clean print on a never-issued card is exactly the
    pattern it exists to catch. Otherwise the band is a confidence-weighted mean of each
    signal's lean (rule 4), with the catalog read weighted above any single visual signal.
    Confidence is the mean confidence of the signals that carried evidence, so a band resting
    on one barely-read signal reports low confidence rather than false certainty.
    """
    weighted_lean = 0.0
    total_weight = 0.0
    evidence_confidences: list[float] = []

    for signal in signals:
        lean, base = _signal_lean(signal)
        if lean is None:
            continue
        weight = base * signal.confidence
        weighted_lean += lean * weight
        total_weight += weight
        evidence_confidences.append(signal.confidence)

    # Guarded by the readable-signal gate upstream, but stay total: no evidence → inconclusive.
    if total_weight == 0.0 or not evidence_confidences:
        confidence = (
            _CATALOG_CONFIDENCE if existence is CatalogExistence.NOT_IN_CATALOG else 0.0
        )
        band = (
            RiskBand.ELEVATED_RISK
            if existence is CatalogExistence.NOT_IN_CATALOG
            else RiskBand.INCONCLUSIVE
        )
        return band, confidence

    composite = weighted_lean / total_weight
    confidence = sum(evidence_confidences) / len(evidence_confidences)
    band = _band_for(composite)
    if existence is CatalogExistence.NOT_IN_CATALOG:
        band = RiskBand.ELEVATED_RISK
    return band, round(confidence, 3)


def _signal_lean(signal: AuthenticitySignal) -> tuple[float | None, float]:
    """Return a signal's directional lean and its base weight, or ``(None, _)`` if no evidence.

    The catalog cross-check leans on its own (stronger) scale and weight; the visual signals
    share a unit base weight. A non-leaning observation (inconclusive/unreadable) returns
    ``None`` so it erodes nothing and contributes no direction — only confidence is affected,
    via the readable-count gate.
    """
    if signal.kind is SignalKind.CATALOG_EXISTENCE:
        existence = _EXISTENCE_BY_OBSERVATION.get(signal.observation)
        lean = _CATALOG_LEAN[existence] if existence is not None else 0.0
        if lean == 0.0:
            return None, 0.0
        return lean, _CATALOG_WEIGHT

    lean = _OBSERVATION_LEAN[signal.observation]
    if lean == 0.0:
        return None, 0.0
    return lean, 1.0


# The catalog signal's observation maps back to the existence verdict that set it, so the
# composer can apply the catalog-specific lean without re-querying.
_EXISTENCE_BY_OBSERVATION: dict[SignalObservation, CatalogExistence] = {
    SignalObservation.CONSISTENT: CatalogExistence.CONFIRMED,
    SignalObservation.DEVIATION: CatalogExistence.NOT_IN_CATALOG,
    SignalObservation.INCONCLUSIVE: CatalogExistence.UNVERIFIABLE,
}


def _band_for(composite: float) -> RiskBand:
    if composite >= _STRONG_SIGNALS_AT:
        return RiskBand.STRONG_SIGNALS
    if composite <= _ELEVATED_RISK_AT:
        return RiskBand.ELEVATED_RISK
    return RiskBand.INCONCLUSIVE


def _retake(visual_signals: list[AuthenticitySignal]) -> AuthenticityResponse:
    """Refuse on a capture too poor to screen — name the signals that couldn't be read."""
    unreadable = [
        s
        for s in visual_signals
        if s.observation is SignalObservation.UNREADABLE or s.confidence < _USABLE_CONFIDENCE
    ]
    reasons = [
        "The capture couldn't support an authenticity screen. Re-capture sharp, well-lit, "
        "and close enough to resolve fine print, with a few tilt angles for the foil."
    ]
    reasons.extend(f"{s.kind.value}: {s.detail}" for s in unreadable)
    return AuthenticityResponse(status=AuthenticityStatus.RETAKE, reasons=reasons)


def _not_assessed(value_eur: Decimal | None, threshold: float) -> AuthenticityResponse:
    """Below the value threshold: screening isn't meaningful, so we don't fake a score."""
    if value_eur is None:
        reason = (
            "This card isn't valued yet, so authenticity screening isn't offered — it's a "
            "check worth running on higher-value cards, not on every scan."
        )
    else:
        reason = (
            f"At about €{value_eur:.0f} this card is below the €{threshold:.0f} threshold "
            "where authenticity screening is worthwhile — cards at this value are rarely "
            "counterfeited."
        )
    return AuthenticityResponse(status=AuthenticityStatus.NOT_ASSESSED, reasons=[reason])
