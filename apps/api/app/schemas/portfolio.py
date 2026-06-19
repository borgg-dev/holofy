"""Request/response contract for the portfolio — the value-over-time retention feature.

The portfolio total is the collection valued in € at a moment in time; a snapshot pins that
total into the append-only series the chart reads. ``valuation_basis`` records which price
statistic the total was built from so two points are comparable.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PortfolioTotal(BaseModel):
    total_value_eur: Decimal
    total_cost_basis_eur: Decimal | None
    item_count: int
    valuation_basis: str
    currency: str = "EUR"


class PortfolioSnapshotView(BaseModel):
    captured_at: datetime
    total_value_eur: Decimal
    total_cost_basis_eur: Decimal | None
    item_count: int
    valuation_basis: str


class PortfolioHistoryResponse(BaseModel):
    """Newest-first series of valuation snapshots for the chart."""

    snapshots: list[PortfolioSnapshotView]
    currency: str = "EUR"


class PortfolioView(BaseModel):
    """The Vault header's view: the live total now, plus the prior snapshot for the delta.

    ``latest`` is the collection valued *at request time* (so the header is never stale);
    ``previous`` is the most recent pinned snapshot, or ``None`` on a fresh account with no
    history yet — in which case the client shows no change figure rather than a fake one.
    """

    latest: PortfolioSnapshotView
    previous: PortfolioSnapshotView | None
    currency: str = "EUR"
