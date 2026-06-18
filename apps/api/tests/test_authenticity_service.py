"""Coverage for the authenticity composition: risk bands, the catalog cross-check, refuse,
value-threshold gating, and — the hard gate — that no path ever emits a fake/genuine verdict.

The visual signals come from a stub provider and the catalog read from a stub checker, so
each branch is pinned exactly. The §3.5 assertions are the load-bearing ones: the most
adverse output is ``elevated_risk`` (never "fake"), an absent reference never reads against
the card, a poor capture refuses, and a cheap card is "not assessed" rather than fake-scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.authenticity.catalog_existence import CatalogExistence, CardTuple
from app.schemas.authenticity import (
    AuthenticitySignal,
    AuthenticityStatus,
    RiskBand,
    SignalDetail,
    SignalKind,
    SignalObservation,
)
from app.services.authenticity import AuthenticityService

_MIN_VALUE_EUR = 50.0
# A card comfortably over the screening threshold — value isn't the variable under test here.
_HIGH_VALUE = Decimal("500.00")
_CARD = CardTuple(set_code="origins", collector_number="12/120", variant="holo", language="en")


@dataclass
class _Capture:
    capture_ref: str = "capture-x"
    image_count: int = 1


# The stub feeds only visual signals; map each observation to a representative print detail
# from the closed vocabulary so the fixtures construct (``detail`` is no longer a free string).
_STUB_DETAIL = {
    SignalObservation.CONSISTENT: SignalDetail.PRINT_MATCHES_REFERENCE,
    SignalObservation.DEVIATION: SignalDetail.PRINT_DIFFERS_FROM_REFERENCE,
    SignalObservation.INCONCLUSIVE: SignalDetail.LAYOUT_WITHIN_TOLERANCE,
    SignalObservation.UNREADABLE: SignalDetail.PRINT_TOO_COARSE_TO_READ,
}


def _stub_detail(observation: SignalObservation) -> SignalDetail:
    return _STUB_DETAIL[observation]


class _StubProvider:
    """Returns fixed visual signals, independent of the capture."""

    def __init__(self, *signals: tuple[SignalKind, SignalObservation, float]) -> None:
        self._signals = [
            AuthenticitySignal(
                kind=kind, observation=obs, confidence=conf, detail=_stub_detail(obs)
            )
            for kind, obs, conf in signals
        ]

    async def analyze(self, _capture) -> list[AuthenticitySignal]:  # noqa: ANN001
        return list(self._signals)


class _StubCatalog:
    def __init__(self, existence: CatalogExistence) -> None:
        self._existence = existence

    async def check(self, _card: CardTuple) -> CatalogExistence:  # noqa: ANN001
        return self._existence


def _service(
    provider: _StubProvider,
    *,
    existence: CatalogExistence = CatalogExistence.CONFIRMED,
    min_value: float = _MIN_VALUE_EUR,
) -> AuthenticityService:
    return AuthenticityService(
        provider=provider,
        catalog=_StubCatalog(existence),
        min_value_eur=min_value,
    )


def _all_consistent(confidence: float) -> _StubProvider:
    return _StubProvider(
        (SignalKind.PRINT_PATTERN, SignalObservation.CONSISTENT, confidence),
        (SignalKind.HOLO_SIGNATURE, SignalObservation.CONSISTENT, confidence),
        (SignalKind.FONT_LAYOUT, SignalObservation.CONSISTENT, confidence),
        (SignalKind.CARDSTOCK, SignalObservation.CONSISTENT, confidence),
    )


def _all_deviation(confidence: float) -> _StubProvider:
    return _StubProvider(
        (SignalKind.PRINT_PATTERN, SignalObservation.DEVIATION, confidence),
        (SignalKind.HOLO_SIGNATURE, SignalObservation.DEVIATION, confidence),
        (SignalKind.FONT_LAYOUT, SignalObservation.DEVIATION, confidence),
        (SignalKind.CARDSTOCK, SignalObservation.DEVIATION, confidence),
    )


async def _assess(service: AuthenticityService, value: Decimal | None = _HIGH_VALUE):
    return await service.assess(_Capture(), card=_CARD, value_eur=value)


@pytest.mark.asyncio
async def test_consistent_signals_and_confirmed_catalog_read_as_strong_signals() -> None:
    result = await _assess(_service(_all_consistent(0.9)))

    assert result.status is AuthenticityStatus.ASSESSED
    assert result.assessment is not None
    assert result.assessment.risk_band is RiskBand.STRONG_SIGNALS
    # Even the most reassuring read recommends authentication on a high-value card and never
    # claims the card is genuine.
    assert result.assessment.recommend_authentication is True


@pytest.mark.asyncio
async def test_no_path_emits_a_binary_fake_or_genuine_verdict() -> None:
    # The §3.5 hard gate, checked structurally (not by banning the words from the honest
    # disclaimer, which legitimately says "not a determination that a card is genuine or
    # counterfeit"): no verdict field, and the band value is never a fake/genuine boolean.
    deviating = await _assess(
        _service(_all_deviation(0.9), existence=CatalogExistence.NOT_IN_CATALOG)
    )
    dumped = deviating.model_dump()

    assert deviating.assessment.risk_band is RiskBand.ELEVATED_RISK
    # No verdict-shaped field anywhere in the response or the assessment.
    forbidden_fields = {"is_fake", "is_genuine", "fake", "genuine", "verdict", "authentic"}
    assert forbidden_fields.isdisjoint(dumped)
    assert forbidden_fields.isdisjoint(dumped["assessment"])
    # The band vocabulary itself is the three-band scale — no fake/genuine value exists.
    assert {b.value for b in RiskBand} == {"strong_signals", "inconclusive", "elevated_risk"}
    # The most adverse band is "elevated_risk", never a "counterfeit"/"fake" value.
    assert dumped["assessment"]["risk_band"] == "elevated_risk"


@pytest.mark.asyncio
async def test_a_never_printed_variant_drives_elevated_risk_even_with_clean_visuals() -> None:
    # Visuals all read consistent, but the catalog says this variant was never printed: the
    # cross-check is weighted above the visual signals, so the composite must flag risk.
    result = await _assess(
        _service(_all_consistent(0.9), existence=CatalogExistence.NOT_IN_CATALOG)
    )
    assert result.assessment.risk_band is RiskBand.ELEVATED_RISK
    catalog = next(
        s for s in result.assessment.signals if s.kind is SignalKind.CATALOG_EXISTENCE
    )
    assert catalog.observation is SignalObservation.DEVIATION


@pytest.mark.asyncio
async def test_an_unverifiable_catalog_read_never_counts_against_the_card() -> None:
    # An absent reference is our gap, not a finding: clean visuals with an unverifiable
    # catalog must not be pushed toward risk by the missing reference.
    confirmed = await _assess(
        _service(_all_consistent(0.9), existence=CatalogExistence.CONFIRMED)
    )
    unverifiable = await _assess(
        _service(_all_consistent(0.9), existence=CatalogExistence.UNVERIFIABLE)
    )
    assert confirmed.assessment.risk_band is RiskBand.STRONG_SIGNALS
    # Without the catalog's reassurance the band may soften, but it must never be elevated by
    # the gap alone.
    assert unverifiable.assessment.risk_band is not RiskBand.ELEVATED_RISK


@pytest.mark.asyncio
async def test_low_confidence_visuals_lower_overall_confidence() -> None:
    confident = await _assess(_service(_all_consistent(0.9)))
    unsure = await _assess(_service(_all_consistent(0.5)))
    assert unsure.assessment.confidence < confident.assessment.confidence


@pytest.mark.asyncio
async def test_a_capture_too_poor_to_read_refuses_with_a_retake() -> None:
    # Visuals unreadable, and the catalog can't decide either: too little usable evidence to
    # assess honestly — refuse rather than guess.
    poor = _StubProvider(
        (SignalKind.PRINT_PATTERN, SignalObservation.UNREADABLE, 0.2),
        (SignalKind.HOLO_SIGNATURE, SignalObservation.UNREADABLE, 0.18),
        (SignalKind.FONT_LAYOUT, SignalObservation.INCONCLUSIVE, 0.25),
        (SignalKind.CARDSTOCK, SignalObservation.UNREADABLE, 0.2),
    )
    result = await _assess(_service(poor, existence=CatalogExistence.UNVERIFIABLE))

    assert result.status is AuthenticityStatus.RETAKE
    assert result.assessment is None
    assert result.reasons and "re-capture" in result.reasons[0].lower()


@pytest.mark.asyncio
async def test_a_decisive_catalog_check_can_carry_an_otherwise_poor_capture() -> None:
    # Even with unreadable visuals, a definitive "never printed" catalog read is enough usable
    # evidence to assess — and it points at elevated risk.
    poor_visuals = _StubProvider(
        (SignalKind.PRINT_PATTERN, SignalObservation.UNREADABLE, 0.2),
        (SignalKind.HOLO_SIGNATURE, SignalObservation.UNREADABLE, 0.18),
        (SignalKind.FONT_LAYOUT, SignalObservation.UNREADABLE, 0.2),
        (SignalKind.CARDSTOCK, SignalObservation.UNREADABLE, 0.2),
    )
    result = await _assess(
        _service(poor_visuals, existence=CatalogExistence.NOT_IN_CATALOG)
    )
    assert result.status is AuthenticityStatus.ASSESSED
    assert result.assessment.risk_band is RiskBand.ELEVATED_RISK


@pytest.mark.asyncio
async def test_a_card_below_the_value_threshold_is_not_assessed() -> None:
    result = await _assess(_service(_all_consistent(0.9)), value=Decimal("12.00"))

    assert result.status is AuthenticityStatus.NOT_ASSESSED
    assert result.assessment is None
    assert result.reasons and "threshold" in result.reasons[0].lower()


@pytest.mark.asyncio
async def test_an_unpriced_card_is_not_assessed_rather_than_fake_scored() -> None:
    result = await _assess(_service(_all_consistent(0.9)), value=None)
    assert result.status is AuthenticityStatus.NOT_ASSESSED
    assert result.assessment is None


@pytest.mark.asyncio
async def test_a_card_at_the_threshold_is_assessed() -> None:
    result = await _assess(_service(_all_consistent(0.9)), value=Decimal(str(_MIN_VALUE_EUR)))
    assert result.status is AuthenticityStatus.ASSESSED
