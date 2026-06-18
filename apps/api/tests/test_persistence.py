"""Persistence-layer coverage, run on in-memory SQLite (no Postgres, no Docker).

The cases here are the ones with real stakes: that a card and its observed prices
round-trip, that training consent is *off* unless asked for (the privacy-by-design
guarantee), that the row-level guards reject impossible states, that a portfolio snapshot
records and reads back as a value-over-time series, and that erasing a user actually takes
their collection, scans and snapshots with it — while leaving shared catalog data intact.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.erasure import plan_erasure
from app.db.models import (
    CardCondition,
    CollectionItem,
    PortfolioSnapshot,
    PriceBasis,
    PriceObservation,
    PriceSource,
    ScanOutcome,
    ScanRecord,
    Variant,
)
from app.db.repositories import (
    CardRepository,
    CollectionRepository,
    PortfolioRepository,
    PriceRepository,
    ScanRepository,
    UserRepository,
)

_EMBERWYRM = dict(
    canonical_id="origins-12",
    name="Emberwyrm Sovereign",
    set_name="Origins Vault",
    set_code="origins",
    collector_number="12",
    language="en",
    variant=Variant.HOLO,
)


async def _emberwyrm(session: AsyncSession):
    return await CardRepository(session).upsert(**_EMBERWYRM)


@pytest.mark.asyncio
async def test_card_round_trips_with_canonical_lookup(session: AsyncSession) -> None:
    cards = CardRepository(session)
    created = await cards.upsert(**_EMBERWYRM)
    await session.commit()

    fetched = await cards.get_by_canonical_id("origins-12")
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Emberwyrm Sovereign"
    assert fetched.variant is Variant.HOLO
    # Timestamps land timezone-aware in UTC, not naive.
    assert fetched.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_card_upsert_is_idempotent_on_canonical_id(session: AsyncSession) -> None:
    cards = CardRepository(session)
    first = await cards.upsert(**_EMBERWYRM)
    again = await cards.upsert(**{**_EMBERWYRM, "name": "Emberwyrm Sovereign (corrected)"})
    await session.commit()

    assert first.id == again.id
    count = await session.scalar(select(func.count()).select_from(_card_table()))
    assert count == 1


@pytest.mark.asyncio
async def test_same_art_reprint_is_a_distinct_card(session: AsyncSession) -> None:
    cards = CardRepository(session)
    await cards.upsert(**_EMBERWYRM)
    # Same name/art, different set — the ~31× variant the disambiguation tuple separates.
    await cards.upsert(
        **{**_EMBERWYRM, "canonical_id": "echo-12", "set_code": "echo"}
    )
    await session.commit()

    total = await session.scalar(select(func.count()).select_from(_card_table()))
    assert total == 2


@pytest.mark.asyncio
async def test_scan_training_consent_defaults_to_not_consented(
    session: AsyncSession,
) -> None:
    user = await UserRepository(session).create()
    scan = await ScanRepository(session).record(
        user_id=user.id,
        capture_ref="s3://eu/captures/abc",
        outcome=ScanOutcome.RESOLVED,
        top_confidence=0.97,
    )
    await session.commit()

    # The moat is consent-gated: a fresh scan is never training-eligible by default.
    assert scan.training_consent is False
    assert scan.consent_revoked_at is None
    eligible = await ScanRepository(session).list_training_eligible()
    assert eligible == []


@pytest.mark.asyncio
async def test_consented_scan_is_training_eligible_until_revoked(
    session: AsyncSession,
) -> None:
    repo = ScanRepository(session)
    user = await UserRepository(session).create()
    scan = await repo.record(
        user_id=user.id,
        capture_ref="s3://eu/captures/def",
        outcome=ScanOutcome.RESOLVED,
        training_consent=True,
        consent_note="onboarding v1, training opt-in",
    )
    await session.commit()

    assert [s.id for s in await repo.list_training_eligible()] == [scan.id]

    await repo.revoke_training_consent(scan)
    await session.commit()

    assert scan.training_consent is False
    assert scan.consent_revoked_at is not None
    assert await repo.list_training_eligible() == []


@pytest.mark.asyncio
async def test_consent_revocation_is_idempotent(session: AsyncSession) -> None:
    repo = ScanRepository(session)
    user = await UserRepository(session).create()
    scan = await repo.record(
        user_id=user.id,
        capture_ref="s3://eu/captures/ghi",
        outcome=ScanOutcome.RESOLVED,
        training_consent=True,
    )
    await session.commit()

    await repo.revoke_training_consent(scan)
    await session.commit()
    first_stamp = scan.consent_revoked_at

    await repo.revoke_training_consent(scan)
    await session.commit()
    assert scan.consent_revoked_at == first_stamp


@pytest.mark.asyncio
async def test_active_consent_with_revocation_stamp_is_rejected(
    session: AsyncSession,
) -> None:
    user = await UserRepository(session).create()
    await session.commit()
    # The row-level guard: consent can't be active and revoked at once.
    session.add(
        ScanRecord(
            user_id=user.id,
            capture_ref="s3://eu/captures/bad",
            outcome=ScanOutcome.RESOLVED,
            training_consent=True,
            consent_revoked_at=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_price_observations_persist_history(session: AsyncSession) -> None:
    card = await _emberwyrm(session)
    prices = PriceRepository(session)
    await prices.record(
        card_id=card.id,
        value_eur=Decimal("529.99"),
        source=PriceSource.TCGDEX,
        basis=PriceBasis.AVG_30D,
        observed_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    await prices.record(
        card_id=card.id,
        value_eur=Decimal("757.10"),
        source=PriceSource.TCGDEX,
        basis=PriceBasis.AVG_30D,
        observed_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
    )
    await session.commit()

    latest = await prices.latest(card.id, basis=PriceBasis.AVG_30D)
    assert latest is not None
    assert latest.value_eur == Decimal("757.10")

    history = await prices.history(card.id, basis=PriceBasis.AVG_30D)
    assert [o.value_eur for o in history] == [Decimal("757.10"), Decimal("529.99")]


@pytest.mark.asyncio
async def test_duplicate_price_snapshot_is_rejected(session: AsyncSession) -> None:
    card = await _emberwyrm(session)
    prices = PriceRepository(session)
    observed = datetime(2026, 6, 18, tzinfo=timezone.utc)
    args = dict(
        card_id=card.id,
        value_eur=Decimal("757.10"),
        source=PriceSource.TCGDEX,
        basis=PriceBasis.TREND,
        observed_at=observed,
    )
    await prices.record(**args)
    await session.commit()

    # The repository flushes on write, so the uniqueness violation surfaces there.
    with pytest.raises(IntegrityError):
        await prices.record(**args)


@pytest.mark.asyncio
async def test_negative_price_is_rejected(session: AsyncSession) -> None:
    card = await _emberwyrm(session)
    session.add(
        PriceObservation(
            card_id=card.id,
            value_eur=Decimal("-1.00"),
            source=PriceSource.TCGDEX,
            basis=PriceBasis.TREND,
            observed_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_portfolio_snapshot_records_and_reads_as_series(
    session: AsyncSession,
) -> None:
    user = await UserRepository(session).create()
    portfolio = PortfolioRepository(session)
    await portfolio.record(
        user_id=user.id,
        total_value_eur=Decimal("812.40"),
        item_count=3,
        valuation_basis=PriceBasis.TREND,
        total_cost_basis_eur=Decimal("210.00"),
        captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    await portfolio.record(
        user_id=user.id,
        total_value_eur=Decimal("905.10"),
        item_count=4,
        valuation_basis=PriceBasis.TREND,
        total_cost_basis_eur=Decimal("260.00"),
        captured_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
    )
    await session.commit()

    latest = await portfolio.latest(user.id)
    assert latest is not None
    assert latest.total_value_eur == Decimal("905.10")

    series = await portfolio.history(user.id)
    assert [s.total_value_eur for s in series] == [
        Decimal("905.10"),
        Decimal("812.40"),
    ]


@pytest.mark.asyncio
async def test_collection_item_constraints(session: AsyncSession) -> None:
    user = await UserRepository(session).create()
    card = await _emberwyrm(session)
    await session.commit()

    session.add(
        CollectionItem(
            user_id=user.id,
            card_id=card.id,
            condition=CardCondition.NEAR_MINT,
            quantity=0,  # violates quantity > 0
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_collection_lists_with_card_eager_loaded(session: AsyncSession) -> None:
    user = await UserRepository(session).create()
    card = await _emberwyrm(session)
    await CollectionRepository(session).add(
        user_id=user.id,
        card_id=card.id,
        condition=CardCondition.NEAR_MINT,
        quantity=2,
        acquired_price_eur=Decimal("180.00"),
        acquired_on=date(2024, 12, 1),
    )
    await session.commit()

    items = await CollectionRepository(session).list_for_user(user.id)
    assert len(items) == 1
    assert items[0].card.canonical_id == "origins-12"
    assert items[0].acquired_price_eur == Decimal("180.00")


@pytest.mark.asyncio
async def test_user_erasure_cascades_personal_data_and_spares_catalog(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create()
    card = await _emberwyrm(session)
    await CollectionRepository(session).add(
        user_id=user.id, card_id=card.id, condition=CardCondition.NEAR_MINT
    )
    scan = await ScanRepository(session).record(
        user_id=user.id,
        capture_ref="s3://eu/captures/jkl",
        outcome=ScanOutcome.RESOLVED,
        resolved_card_id=card.id,
        training_consent=True,
    )
    await PortfolioRepository(session).record(
        user_id=user.id,
        total_value_eur=Decimal("757.10"),
        item_count=1,
        valuation_basis=PriceBasis.TREND,
    )
    await PriceRepository(session).record(
        card_id=card.id,
        value_eur=Decimal("757.10"),
        source=PriceSource.TCGDEX,
        basis=PriceBasis.TREND,
        observed_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
    )
    await session.commit()

    # The erasure manifest enumerates out-of-band personal data before the rows vanish.
    manifest = await plan_erasure(session, user.id)
    assert manifest.capture_refs == ["s3://eu/captures/jkl"]
    assert manifest.training_eligible_scan_ids == [scan.id]

    await users.delete(user)
    await session.commit()

    # Personal data is gone...
    assert await _count(session, CollectionItem) == 0
    assert await _count(session, ScanRecord) == 0
    assert await _count(session, PortfolioSnapshot) == 0
    # ...but the shared catalog and its market price history remain.
    assert await CardRepository(session).get_by_canonical_id("origins-12") is not None
    assert await _count(session, PriceObservation) == 1


@pytest.mark.asyncio
async def test_erasure_manifest_includes_pregrade_and_authenticity_captures(
    session: AsyncSession,
) -> None:
    # Every object-storage still the user produced — not just scan bundles — must be enumerated
    # for the out-of-band purge, or pre-grade / authenticity captures would survive a delete.
    from app.db.models import AuthenticityRecord, PreGradeRecord
    from app.db.models.enums import AuthenticityStatus, PregradeStatus

    users = UserRepository(session)
    user = await users.create()
    card = await _emberwyrm(session)
    await ScanRepository(session).record(
        user_id=user.id,
        capture_ref="s3://eu/captures/scan-1",
        outcome=ScanOutcome.RESOLVED,
        resolved_card_id=card.id,
    )
    session.add(
        PreGradeRecord(
            user_id=user.id,
            capture_ref="s3://eu/captures/pregrade-1",
            card_id=card.id,
            status=PregradeStatus.RETAKE,
        )
    )
    session.add(
        AuthenticityRecord(
            user_id=user.id,
            capture_ref="s3://eu/captures/authenticity-1",
            card_id=card.id,
            status=AuthenticityStatus.RETAKE,
        )
    )
    await session.commit()

    manifest = await plan_erasure(session, user.id)
    assert set(manifest.capture_refs) == {
        "s3://eu/captures/scan-1",
        "s3://eu/captures/pregrade-1",
        "s3://eu/captures/authenticity-1",
    }


def _card_table():
    from app.db.models import Card

    return Card


async def _count(session: AsyncSession, model) -> int:  # noqa: ANN001
    return await session.scalar(select(func.count()).select_from(model))
