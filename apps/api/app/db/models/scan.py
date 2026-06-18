"""A scan event — and the consent flag that gates the training-data moat.

Every scan is logged: the capture it ran on, the ranked candidates recognition produced,
the confidence, the card it resolved to (if any), and the outcome. This is both the user's
scan history and the raw material of the proprietary dataset (architecture §3, §6).

The moat is built on consent, safely:

- ``training_consent`` defaults to ``False``. A scan is *never* eligible for the training
  data lake unless the user explicitly opted in — this default is the privacy-by-design
  guarantee the charter (§3.5) and GDPR require, and it is enforced at the column.
- That consent is **separate from app-usage consent** (a row may exist, powering the
  user's own history, with ``training_consent=False``) and **revocable**: clearing the
  flag and stamping ``consent_revoked_at`` marks the scan for purge from any derived
  training set. See ``app/db/erasure.py``.

``capture_ref`` points at the stills in object storage; the bytes are not stored in
Postgres (data minimization, §6). ``candidates`` keeps the recognition hypotheses as
JSON — useful as a training label and to audit a misfire — without a row per candidate.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import ScanOutcome
from app.db.types import GUID, Timestamp, new_uuid

if TYPE_CHECKING:
    from app.db.models.card import Card
    from app.db.models.user import User


class ScanRecord(TimestampMixin, Base):
    __tablename__ = "scan_records"
    __table_args__ = (
        CheckConstraint(
            "top_confidence IS NULL OR (top_confidence >= 0 AND top_confidence <= 1)",
            name="top_confidence_unit_interval",
        ),
        # A revocation timestamp only makes sense once consent has been withdrawn; consent
        # being true with a revocation stamp is a contradiction we forbid at the row.
        CheckConstraint(
            "NOT (training_consent AND consent_revoked_at IS NOT NULL)",
            name="consent_not_active_when_revoked",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Object-storage reference to the capture stills; never the bytes (data minimization).
    capture_ref: Mapped[str] = mapped_column(String(512))

    # Ranked recognition hypotheses as emitted, including the ones not chosen — the raw
    # signal for the variant-disambiguation training set.
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    top_confidence: Mapped[float | None] = mapped_column(Float)

    outcome: Mapped[ScanOutcome] = mapped_column(String(24))

    # Null until the scan resolves (or stays null for an unrecognized capture). SET NULL on
    # card delete keeps the scan-history row intact if a catalog entry is ever retired.
    resolved_card_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("cards.id", ondelete="SET NULL"), index=True
    )

    # --- The consent moat: explicit, revocable, separate from app-usage consent. ---
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_revoked_at: Mapped[datetime | None] = mapped_column(Timestamp)
    # Free-text capture of why/where consent was given, for audit (copy version, screen).
    consent_note: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="scans")
    resolved_card: Mapped["Card | None"] = relationship(back_populates="scans")
