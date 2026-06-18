"""A point on a user's value-over-time chart — the retention feature.

One row per valuation run: the user's whole collection totalled in € at a moment in time.
The series is append-only and read by ``(user, captured_at)``, so that pair is both the
index and the uniqueness guard (one snapshot per user per instant). ``item_count`` and the
cost-basis total are denormalized alongside the value so the chart and the
"up/down since you bought" delta render without re-summing the collection.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID, Timestamp, new_uuid, utcnow

if TYPE_CHECKING:
    from app.db.models.user import User


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "captured_at"),
        CheckConstraint("total_value_eur >= 0", name="total_value_non_negative"),
        CheckConstraint("item_count >= 0", name="item_count_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    captured_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow, index=True)

    total_value_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_cost_basis_eur: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    item_count: Mapped[int] = mapped_column(Integer, default=0)

    # Which price statistic the total was built from, so two snapshots are comparable.
    valuation_basis: Mapped[str] = mapped_column(String(16))

    user: Mapped["User"] = relationship(back_populates="portfolio_snapshots")
