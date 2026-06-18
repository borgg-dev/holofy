from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import PriceBasis, PriceSource
from app.db.models.price import PriceObservation


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        card_id: uuid.UUID,
        value_eur: Decimal,
        source: PriceSource,
        basis: PriceBasis,
        observed_at: datetime,
        currency: str = "EUR",
    ) -> PriceObservation:
        """Persist one price point — the daily-snapshot write that builds our history."""
        observation = PriceObservation(
            card_id=card_id,
            value_eur=value_eur,
            currency=currency,
            source=source,
            basis=basis,
            observed_at=observed_at,
        )
        self._session.add(observation)
        await self._session.flush()
        return observation

    async def latest(
        self, card_id: uuid.UUID, *, basis: PriceBasis | None = None
    ) -> PriceObservation | None:
        """The freshest cached point for a card, optionally constrained to one basis."""
        stmt = select(PriceObservation).where(PriceObservation.card_id == card_id)
        if basis is not None:
            stmt = stmt.where(PriceObservation.basis == basis)
        stmt = stmt.order_by(PriceObservation.observed_at.desc()).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def history(
        self, card_id: uuid.UUID, *, basis: PriceBasis, limit: int | None = None
    ) -> list[PriceObservation]:
        """Newest-first price history for a card on one basis — our own trend line."""
        stmt = (
            select(PriceObservation)
            .where(
                PriceObservation.card_id == card_id,
                PriceObservation.basis == basis,
            )
            .order_by(PriceObservation.observed_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list((await self._session.execute(stmt)).scalars())
