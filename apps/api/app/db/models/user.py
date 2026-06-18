"""The account a collection, scans and portfolio history hang off.

Minimal by design: auth (Supabase/Clerk) is a later slice, so this carries only the
internal id and audit timestamps. The seam for it is ``auth_provider`` /
``auth_subject`` — nullable now, uniquely paired when linkage lands — so adding federated
identity is an additive migration, not a reshape.

Erasure note (GDPR right-to-erasure): deleting a ``User`` cascades to every owned
row — collection, scans, portfolio snapshots — via ``ON DELETE CASCADE`` at the FK and
``cascade="all, delete-orphan"`` on the relationships. ``Card`` and ``PriceObservation``
are catalog/market reference data, not personal data, and are intentionally *not* owned by
the user. See ``app/db/erasure.py`` for the data-lake propagation strategy.

Training consent lives here, on the account, as its durable source of truth: the privacy
screen reads and writes this one flag, and every new capture inherits it at capture time.
Deriving it from per-record counts would lose the intent of a user who opts in *before* they
have any captures — so the account carries it explicitly, off by default (charter §3.5, GDPR).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import GUID, Timestamp, new_uuid

if TYPE_CHECKING:
    from app.db.models.authenticity import AuthenticityRecord
    from app.db.models.collection import CollectionItem
    from app.db.models.portfolio import PortfolioSnapshot
    from app.db.models.pregrade import PreGradeRecord
    from app.db.models.scan import ScanRecord


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("auth_provider", "auth_subject"),
        # Consent active and a revocation stamp is a contradiction — forbid it at the row,
        # mirroring the per-record constraint the capture tables carry.
        CheckConstraint(
            "NOT (training_consent AND training_consent_revoked_at IS NOT NULL)",
            name="consent_not_active_when_revoked",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    # Auth linkage seam — both null until the auth slice lands, then set together.
    auth_provider: Mapped[str | None] = mapped_column(String(32))
    auth_subject: Mapped[str | None] = mapped_column(String(255))

    # --- Account-level training consent: the durable source of truth for the moat. ---
    # Off by default. ``training_consent_at`` stamps when it was granted; revoking clears the
    # flag and stamps ``training_consent_revoked_at`` so a later opt-in's history is auditable.
    # New captures inherit this flag at capture time (see the scan/pregrade/authenticity paths).
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    training_consent_at: Mapped[datetime | None] = mapped_column(Timestamp)
    training_consent_revoked_at: Mapped[datetime | None] = mapped_column(Timestamp)
    # The surface/copy version the choice was made under, for audit.
    consent_note: Mapped[str | None] = mapped_column(Text)

    collection_items: Mapped[list["CollectionItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scans: Mapped[list["ScanRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pregrades: Mapped[list["PreGradeRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    authenticity_screens: Mapped[list["AuthenticityRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
