"""Coverage for the scan orchestration: confirm on low confidence, else resolve and persist.

Runs against the in-memory ``session`` fixture so the service's ScanRecord write and catalog
upsert exercise the real persistence path, not a stub.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RecognitionFailedError
from app.datalake.mock import MockDataLakeSink
from app.db.models import ScanOutcome as PersistedScanOutcome
from app.db.repositories import CardRepository, ScanRepository, UserRepository
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


def _identity(canonical_id: str, name: str = "Emberwyrm Sovereign") -> CardIdentity:
    return CardIdentity(
        canonical_id=canonical_id,
        name=name,
        set_name="Origins Vault",
        collector_number="12/120",
        language="en",
        variant=Variant.HOLO,
    )


class _StubRecognition:
    def __init__(self, result: RecognitionResult) -> None:
        self._result = result

    async def recognize(self, _bundle) -> RecognitionResult:  # noqa: ANN001
        return self._result


def _service(
    result: RecognitionResult, sink: MockDataLakeSink | None = None
) -> ScanService:
    return ScanService(
        recognition=_StubRecognition(result),
        pricing=MockPricingProvider(),
        data_lake=sink or MockDataLakeSink(),
        confirm_threshold=_THRESHOLD,
    )


async def _run(service: ScanService, session: AsyncSession):
    user = await UserRepository(session).create()
    return user, await service.scan(
        CaptureBundleRef(bundle_id="b"),
        user_id=user.id,
        scans=ScanRepository(session),
        cards=CardRepository(session),
    )


@pytest.mark.asyncio
async def test_confident_top_candidate_resolves_with_price(
    session: AsyncSession,
) -> None:
    result = RecognitionResult(
        candidates=[RecognitionCandidate(identity=_identity("origins-12"), confidence=0.97)]
    )
    user, response = await _run(_service(result), session)

    assert response.outcome is ScanOutcome.RESOLVED
    assert response.card is not None
    assert response.card.price is not None
    assert response.card.price.value == Decimal("757.10")
    assert response.choices is None

    # The resolved scan is logged and points at the upserted catalog card.
    records = await ScanRepository(session).list_for_user(user.id)
    assert records[0].outcome == PersistedScanOutcome.RESOLVED
    assert records[0].resolved_card_id is not None
    assert await CardRepository(session).get_by_canonical_id("origins-12") is not None


@pytest.mark.asyncio
async def test_low_confidence_returns_top_two_with_price_delta(
    session: AsyncSession,
) -> None:
    result = RecognitionResult(
        candidates=[
            RecognitionCandidate(identity=_identity("origins-12"), confidence=0.61),
            RecognitionCandidate(identity=_identity("echo-12"), confidence=0.55),
        ]
    )
    user, response = await _run(_service(result), session)

    assert response.outcome is ScanOutcome.NEEDS_CONFIRMATION
    assert response.card is None
    assert response.choices is not None and len(response.choices) == 2
    # 757.10 (origins-12) vs 24.50 (echo-12) in the mock — the delta that justifies asking.
    assert response.price_delta == Decimal("732.60")

    records = await ScanRepository(session).list_for_user(user.id)
    assert records[0].outcome == PersistedScanOutcome.NEEDS_CONFIRMATION
    assert records[0].resolved_card_id is None


@pytest.mark.asyncio
async def test_resolved_card_with_unpriced_identity_keeps_identity_and_nulls_price(
    session: AsyncSession,
) -> None:
    result = RecognitionResult(
        candidates=[
            RecognitionCandidate(identity=_identity("long-tail-999"), confidence=0.99)
        ]
    )
    _user, response = await _run(_service(result), session)

    assert response.outcome is ScanOutcome.RESOLVED
    assert response.card is not None
    assert response.card.price is None


@pytest.mark.asyncio
async def test_empty_recognition_raises_recognition_failed(
    session: AsyncSession,
) -> None:
    result = RecognitionResult(candidates=[])
    user = await UserRepository(session).create()
    with pytest.raises(RecognitionFailedError):
        await _service(result).scan(
            CaptureBundleRef(bundle_id="b"),
            user_id=user.id,
            scans=ScanRepository(session),
            cards=CardRepository(session),
        )

    # The unrecognized capture is still logged as scan history.
    records = await ScanRepository(session).list_for_user(user.id)
    assert records[0].outcome == PersistedScanOutcome.UNRECOGNIZED
