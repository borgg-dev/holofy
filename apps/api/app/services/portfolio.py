"""Portfolio orchestration: total the collection in €, snapshot it, read the series.

The total is the live sum of the collection valuation; a snapshot pins that total (plus the
item count and cost basis) into the append-only history the chart reads. Valuation is
delegated to the collection service so "what the portfolio is worth" and "what the
collection lists at" can never disagree.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.db.models.enums import PriceBasis
from app.db.repositories import PortfolioRepository
from app.schemas.collection import CollectionResponse
from app.schemas.portfolio import (
    PortfolioHistoryResponse,
    PortfolioSnapshotView,
    PortfolioTotal,
    PortfolioView,
)
from app.services.collection import CollectionService

# The mock/TCGdex quotes report a trend value; snapshots record that basis so two points are
# compared like-for-like. A per-basis valuation choice is a later refinement.
_VALUATION_BASIS = PriceBasis.TREND


class PortfolioService:
    def __init__(
        self,
        *,
        collection: CollectionService,
        portfolio: PortfolioRepository,
    ) -> None:
        self._collection = collection
        self._portfolio = portfolio

    async def total(self, user_id: uuid.UUID) -> PortfolioTotal:
        valued = await self._collection.list_valued(user_id)
        return _total_of(valued)

    async def view(self, user_id: uuid.UUID) -> PortfolioView:
        """The Vault header view: the live total now + the most recent prior snapshot.

        ``latest`` is computed at request time so the header is never stale; ``previous`` is
        the last pinned snapshot (or ``None`` on a fresh account), which the client diffs
        against to show the value change.
        """
        total = await self.total(user_id)
        latest = PortfolioSnapshotView(
            captured_at=datetime.now(UTC),
            total_value_eur=total.total_value_eur,
            total_cost_basis_eur=total.total_cost_basis_eur,
            item_count=total.item_count,
            valuation_basis=total.valuation_basis,
        )
        history = await self._portfolio.history(user_id, limit=1)
        previous = (
            PortfolioSnapshotView(
                captured_at=history[0].captured_at,
                total_value_eur=history[0].total_value_eur,
                total_cost_basis_eur=history[0].total_cost_basis_eur,
                item_count=history[0].item_count,
                valuation_basis=history[0].valuation_basis,
            )
            if history
            else None
        )
        return PortfolioView(latest=latest, previous=previous)

    async def snapshot(self, user_id: uuid.UUID) -> PortfolioTotal:
        """Pin the current total into the value-over-time series and return it."""
        valued = await self._collection.list_valued(user_id)
        total = _total_of(valued)
        await self._portfolio.record(
            user_id=user_id,
            total_value_eur=total.total_value_eur,
            item_count=total.item_count,
            valuation_basis=_VALUATION_BASIS,
            total_cost_basis_eur=total.total_cost_basis_eur,
        )
        return total

    async def snapshot_all_due(self, *, min_interval_hours: float = 20.0) -> int:
        """Snapshot every holder whose last snapshot is older than ``min_interval_hours`` (or who
        has none). The daily job calls this; the interval makes it idempotent — a second run the
        same day is a no-op — and tolerant of an off-schedule run, so the value-over-time series
        accrues one honest point per day without duplicates. Returns how many were written."""
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(hours=min_interval_hours)
        written = 0
        for user_id in await self._collection.holder_ids():
            latest = await self._portfolio.latest(user_id)
            if latest is not None:
                captured = latest.captured_at
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=UTC)
                if captured > cutoff:
                    continue  # already snapshotted within the window — skip to stay daily
            await self.snapshot(user_id)
            written += 1
        return written

    async def history(
        self, user_id: uuid.UUID, *, limit: int | None = None
    ) -> PortfolioHistoryResponse:
        snapshots = await self._portfolio.history(user_id, limit=limit)
        return PortfolioHistoryResponse(
            snapshots=[
                PortfolioSnapshotView(
                    captured_at=s.captured_at,
                    total_value_eur=s.total_value_eur,
                    total_cost_basis_eur=s.total_cost_basis_eur,
                    item_count=s.item_count,
                    valuation_basis=s.valuation_basis,
                )
                for s in snapshots
            ]
        )


def _total_of(valued: CollectionResponse) -> PortfolioTotal:
    priced = [
        item for item in valued.items if item.acquired_price_eur is not None
    ]
    # None — not 0 — when no holding records what it cost, so "no basis" stays distinct
    # from "bought for free".
    cost_basis = (
        sum(
            (item.acquired_price_eur * item.quantity for item in priced),
            Decimal("0.00"),
        )
        if priced
        else None
    )
    return PortfolioTotal(
        total_value_eur=valued.total_value_eur,
        total_cost_basis_eur=cost_basis,
        item_count=sum(item.quantity for item in valued.items),
        valuation_basis=_VALUATION_BASIS.value,
    )
