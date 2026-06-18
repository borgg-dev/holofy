"""The canonical card reference that recognition, pricing and ownership resolve to.

This is catalog data (synced nightly from the aggregator, per architecture §4), not
personal data: it is shared across all users and is never erased on a user delete. The
``(set, collector number, variant, language)`` tuple is what disambiguates same-art
reprints whose prices diverge ×10 — so it carries a uniqueness constraint, and the
``canonical_id`` that the pricing key is built from is unique and indexed as the lookup
path the hot scan loop hits.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import Variant
from app.db.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.db.models.authenticity import AuthenticityRecord
    from app.db.models.collection import CollectionItem
    from app.db.models.pregrade import PreGradeRecord
    from app.db.models.price import PriceObservation
    from app.db.models.scan import ScanRecord


class Card(TimestampMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        # The disambiguation tuple: the same artwork in a different set/edition/language is
        # a distinct, separately-priced card and must be a distinct row.
        UniqueConstraint(
            "set_code", "collector_number", "variant", "language"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    # The external catalog key (e.g. TCGdex ``origins-12``); the pricing provider is keyed on
    # this, so it is the join target for price lookups and must be unique.
    canonical_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    name: Mapped[str] = mapped_column(String(255), index=True)
    set_name: Mapped[str] = mapped_column(String(255))
    set_code: Mapped[str] = mapped_column(String(32))
    collector_number: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8))
    variant: Mapped[Variant] = mapped_column(String(16))

    collection_items: Mapped[list["CollectionItem"]] = relationship(
        back_populates="card"
    )
    price_observations: Mapped[list["PriceObservation"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scans: Mapped[list["ScanRecord"]] = relationship(back_populates="resolved_card")
    pregrades: Mapped[list["PreGradeRecord"]] = relationship(back_populates="card")
    authenticity_screens: Mapped[list["AuthenticityRecord"]] = relationship(
        back_populates="card"
    )
