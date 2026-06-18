"""Coverage for the scan orchestration rule: confirm on low confidence, else resolve."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import RecognitionFailedError
from app.providers.pricing.mock import MockPricingProvider
from app.schemas.cards import (
    CardIdentity,
    RecognitionCandidate,
    RecognitionResult,
    Variant,
)
from app.schemas.scan import CaptureBundleRef, ScanOutcome
from app.services.scan import ScanService

_THRESHOLD = 0.85


def _identity(canonical_id: str, name: str = "Charizard") -> CardIdentity:
    return CardIdentity(
        canonical_id=canonical_id,
        name=name,
        set_name="Base Set",
        collector_number="4/102",
        language="en",
        variant=Variant.HOLO,
    )


class _StubRecognition:
    def __init__(self, result: RecognitionResult) -> None:
        self._result = result

    async def recognize(self, _bundle) -> RecognitionResult:  # noqa: ANN001
        return self._result


def _service(result: RecognitionResult) -> ScanService:
    return ScanService(
        recognition=_StubRecognition(result),
        pricing=MockPricingProvider(),
        confirm_threshold=_THRESHOLD,
    )


@pytest.mark.asyncio
async def test_confident_top_candidate_resolves_with_price() -> None:
    result = RecognitionResult(
        candidates=[RecognitionCandidate(identity=_identity("base1-4"), confidence=0.97)]
    )
    response = await _service(result).scan(CaptureBundleRef(bundle_id="b"))

    assert response.outcome is ScanOutcome.RESOLVED
    assert response.card is not None
    assert response.card.price is not None
    assert response.card.price.value == Decimal("757.10")
    assert response.choices is None


@pytest.mark.asyncio
async def test_low_confidence_returns_top_two_with_price_delta() -> None:
    result = RecognitionResult(
        candidates=[
            RecognitionCandidate(identity=_identity("base1-4"), confidence=0.61),
            RecognitionCandidate(identity=_identity("base2-4"), confidence=0.55),
        ]
    )
    response = await _service(result).scan(CaptureBundleRef(bundle_id="b"))

    assert response.outcome is ScanOutcome.NEEDS_CONFIRMATION
    assert response.card is None
    assert response.choices is not None and len(response.choices) == 2
    # 757.10 (base1-4) vs 24.50 (base2-4) in the mock — the delta that justifies asking.
    assert response.price_delta == Decimal("732.60")


@pytest.mark.asyncio
async def test_resolved_card_with_unpriced_identity_keeps_identity_and_nulls_price() -> None:
    result = RecognitionResult(
        candidates=[
            RecognitionCandidate(identity=_identity("long-tail-999"), confidence=0.99)
        ]
    )
    response = await _service(result).scan(CaptureBundleRef(bundle_id="b"))

    assert response.outcome is ScanOutcome.RESOLVED
    assert response.card is not None
    assert response.card.price is None


@pytest.mark.asyncio
async def test_empty_recognition_raises_recognition_failed() -> None:
    result = RecognitionResult(candidates=[])
    with pytest.raises(RecognitionFailedError):
        await _service(result).scan(CaptureBundleRef(bundle_id="b"))
