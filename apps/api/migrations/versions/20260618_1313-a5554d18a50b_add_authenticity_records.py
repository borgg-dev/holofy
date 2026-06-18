"""Add the authenticity_records table — the owner's private authenticity-screen history.

One row per screen: the capture it ran on, whether it produced a risk band, refused
(``status='retake'``), or was skipped below the value threshold (``status='not_assessed'``),
the composite ``risk_band`` (deliberately a three-band value, **never** a fake/genuine
boolean — charter §3.5), the overall confidence, the value that crossed the threshold, and
the per-signal reads as JSON. A check constraint pins ``risk_band`` to the closed three-band
vocabulary so no verdict can be written. Authored against SQLite (test) but applies to the
Postgres prod target via ``render_as_batch``.

Revision ID: a5554d18a50b
Revises: c42e26561d8c
Create Date: 2026-06-18 13:13:18.478144
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

import app.db.types


revision: str = 'a5554d18a50b'
down_revision: str | None = 'c42e26561d8c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('authenticity_records',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('user_id', app.db.types.GUID(), nullable=False),
    sa.Column('capture_ref', sa.String(length=512), nullable=False),
    sa.Column('card_id', app.db.types.GUID(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('risk_band', sa.String(length=16), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('reference_value_eur', sa.Float(), nullable=True),
    sa.Column('signals', sa.JSON(), nullable=False),
    sa.Column('reasons', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("risk_band IS NULL OR risk_band IN ('strong_signals', 'inconclusive', 'elevated_risk')", name=op.f('ck_authenticity_records_risk_band_is_a_band')),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)', name=op.f('ck_authenticity_records_confidence_unit_interval')),
    sa.ForeignKeyConstraint(['card_id'], ['cards.id'], name=op.f('fk_authenticity_records_card_id_cards'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_authenticity_records_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_authenticity_records'))
    )
    with op.batch_alter_table('authenticity_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_authenticity_records_card_id'), ['card_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_authenticity_records_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('authenticity_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_authenticity_records_user_id'))
        batch_op.drop_index(batch_op.f('ix_authenticity_records_card_id'))

    op.drop_table('authenticity_records')
