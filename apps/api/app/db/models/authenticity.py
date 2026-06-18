"""An authenticity-screen event — a private risk band persisted against a user (and a card).

Every assessment is logged: the capture it ran on, whether it produced a band, refused
(``retake``), or was skipped below the value threshold (``not_assessed``), the composite
``risk_band``, the per-signal breakdown, and the overall confidence. This is the owner's
private screening history and — alongside any eventual real PSA/CGC outcome, which is a
verified-genuine label — a clean feature row for the authenticity model (architecture §3.3).

The defamation guardrail (charter §3.5) is enforced at the column, not just in the API DTO:
there is no ``is_fake`` / ``verdict`` field. The most adverse value ``risk_band`` can hold is
``elevated_risk``; a check constraint pins it to the three-band vocabulary so no boolean
verdict can ever be written. A refused or not-assessed capture stores its reasons and no
band, so the outcomes can't be confused.

``capture_ref`` points at the stills in object storage; the bytes are never stored
(data minimization, §6). ``signals`` keeps the per-signal reads as JSON — a training label
and an audit trail — without a row per signal.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import AuthenticityRiskBand, AuthenticityStatus
from app.db.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.db.models.card import Card
    from app.db.models.user import User


class AuthenticityRecord(TimestampMixin, Base):
    __tablename__ = "authenticity_records"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_unit_interval",
        ),
        # The risk read is a band from a closed vocabulary or null — never a boolean verdict.
        # This is the persistence-layer half of the §3.5 defamation guard.
        CheckConstraint(
            "risk_band IS NULL OR risk_band IN "
            "('strong_signals', 'inconclusive', 'elevated_risk')",
            name="risk_band_is_a_band",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Object-storage reference to the capture stills; never the bytes (data minimization).
    capture_ref: Mapped[str] = mapped_column(String(512))

    # The screened card. SET NULL on card delete keeps the screening history intact if a
    # catalog entry is ever retired.
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("cards.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[AuthenticityStatus] = mapped_column(String(16))

    # The composite read (assessed path only; null on retake / not_assessed). Deliberately a
    # band, never a boolean verdict — honest framing is structural (charter §3.5).
    risk_band: Mapped[AuthenticityRiskBand | None] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    # The € value that put the card over the screening threshold, for history legibility.
    reference_value_eur: Mapped[float | None] = mapped_column(Float)

    # The per-signal reads as ``[{kind, observation, confidence, detail}, …]`` — a training
    # label and a misfire audit trail. Empty on the refuse / not-assessed paths.
    signals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # On retake / not_assessed: why no band was produced, for the owner's history.
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="authenticity_screens")
    card: Mapped["Card | None"] = relationship(back_populates="authenticity_screens")
