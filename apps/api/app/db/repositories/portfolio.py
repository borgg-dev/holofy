from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import PriceBasis
from app.db.models.portfolio import PortfolioSnapshot


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        total_value_eur: Decimal,
        item_count: int,
        valuation_basis: PriceBasis,
        total_cost_basis_eur: Decimal | None = None,
        captured_at: datetime | None = None,
    ) -> PortfolioSnapshot:
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            total_value_eur=total_value_eur,
            total_cost_basis_eur=total_cost_basis_eur,
            item_count=item_count,
            valuation_basis=valuation_basis,
        )
        if captured_at is not None:
            snapshot.captured_at = captured_at
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def history(
        self, user_id: uuid.UUID, *, limit: int | None = None
    ) -> list[PortfolioSnapshot]:
        """Newest-first value-over-time series for the chart."""
        stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(PortfolioSnapshot.captured_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list((await self._session.execute(stmt)).scalars())

    async def latest(self, user_id: uuid.UUID) -> PortfolioSnapshot | None:
        stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(PortfolioSnapshot.captured_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
