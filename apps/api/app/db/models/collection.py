"""A user owning a specific card: the row a scan appends to and the portfolio sums over.

Condition and quantity live here, not on ``Card``, because they are facts about *this
collector's copy*, not the catalog entry — and condition is what bridges the catalog price
to a realistic personal valuation. A user may own the same card in two conditions (a NM
and a played copy), so the row is not unique on ``(user, card)``; it is unique on
``(user, card, condition)`` and quantity carries duplicates within a condition.

Deleting the user cascades these away (``ON DELETE CASCADE``); deleting a ``Card`` is a
catalog operation that is restricted while any collector still owns it.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import CardCondition
from app.db.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.db.models.card import Card
    from app.db.models.user import User


class CollectionItem(TimestampMixin, Base):
    __tablename__ = "collection_items"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", "condition"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "acquired_price_eur IS NULL OR acquired_price_eur >= 0",
            name="acquired_price_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("cards.id", ondelete="RESTRICT"), index=True
    )

    condition: Mapped[CardCondition] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # What the collector paid, for cost-basis vs current value. The unit is the column
    # name (EUR); precision is fixed so cents never drift in floating point.
    acquired_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    acquired_on: Mapped[date | None] = mapped_column(Date)

    user: Mapped["User"] = relationship(back_populates="collection_items")
    card: Mapped["Card"] = relationship(back_populates="collection_items")
