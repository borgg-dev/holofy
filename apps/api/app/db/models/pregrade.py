"""A pre-grade event — the honest grade *estimate* persisted against a user (and a card).

Every pre-grade is logged: the capture it ran on, whether it produced an estimate or
refused (``retake``), the probability range it landed on, the per-axis sub-scores, and the
overall confidence. This is the user's pre-grade history and, alongside the eventual real
PSA/CGC outcome, a clean feature row for the proprietary grading model (architecture §3.2,
the moat loop).

Honest framing is enforced at the column, not just in the API DTO: there is no "grade"
field. A pre-grade is a *range* — ``likely_low``/``likely_high`` plus ``p_at_least`` /
``at_least`` — and a check constraint forbids an inverted band. A refused capture stores
``status='retake'`` with the reasons and no range, so the two outcomes can't be confused.

``capture_ref`` points at the stills in object storage; the bytes are never stored
(data minimization, §6). ``sub_scores`` keeps the four axis reads as JSON — a training
label and an audit trail — without a row per axis.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import PregradeStatus
from app.db.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.db.models.card import Card
    from app.db.models.user import User


class PreGradeRecord(TimestampMixin, Base):
    __tablename__ = "pregrade_records"
    __table_args__ = (
        # Confidence, when present, is a probability.
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_unit_interval",
        ),
        CheckConstraint(
            "p_at_least IS NULL OR (p_at_least >= 0 AND p_at_least <= 1)",
            name="p_at_least_unit_interval",
        ),
        # The band can never be inverted — an estimate is a range, and a high below a low is
        # a contradiction we forbid at the row. Null on the refuse path.
        CheckConstraint(
            "likely_high IS NULL OR likely_low IS NULL OR likely_high >= likely_low",
            name="band_not_inverted",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Object-storage reference to the capture stills; never the bytes (data minimization).
    capture_ref: Mapped[str] = mapped_column(String(512))

    # Null unless the capture was tied to a resolved catalog card. SET NULL on card delete
    # keeps the pre-grade history intact if a catalog entry is ever retired.
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("cards.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[PregradeStatus] = mapped_column(String(16))

    # --- The probability range (estimated path only; all null on a refuse). Deliberately
    # no single "grade" column: honest framing is structural, not cosmetic. ---
    likely_low: Mapped[int | None] = mapped_column(Integer)
    likely_high: Mapped[int | None] = mapped_column(Integer)
    at_least: Mapped[int | None] = mapped_column(Integer)
    p_at_least: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    # The four axis reads (centering measured in-house, the rest bought) as
    # ``[{axis, score, confidence}, …]`` — a training label and a misfire audit trail.
    sub_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # On the refuse path: why the capture couldn't be graded, for the user's history.
    retake_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="pregrades")
    card: Mapped["Card | None"] = relationship(back_populates="pregrades")
