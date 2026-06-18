"""Add the pregrade_records table — the user's honest pre-grade history.

One row per pre-grade: the capture it ran on, whether it produced an estimate or refused
(``status``), the grade *probability range* (``likely_low``/``likely_high`` + ``at_least``/
``p_at_least`` — deliberately no single-grade column), the overall confidence, and the four
axis sub-scores as JSON. A check constraint forbids an inverted band. Authored against
SQLite (test) but applies to the Postgres prod target via ``render_as_batch``.

Revision ID: c42e26561d8c
Revises: cb5a72db0ff5
Create Date: 2026-06-18 12:17:55.108859
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

import app.db.types


revision: str = 'c42e26561d8c'
down_revision: str | None = 'cb5a72db0ff5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('pregrade_records',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('user_id', app.db.types.GUID(), nullable=False),
    sa.Column('capture_ref', sa.String(length=512), nullable=False),
    sa.Column('card_id', app.db.types.GUID(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('likely_low', sa.Integer(), nullable=True),
    sa.Column('likely_high', sa.Integer(), nullable=True),
    sa.Column('at_least', sa.Integer(), nullable=True),
    sa.Column('p_at_least', sa.Float(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('sub_scores', sa.JSON(), nullable=False),
    sa.Column('retake_reasons', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)', name=op.f('ck_pregrade_records_confidence_unit_interval')),
    sa.CheckConstraint('likely_high IS NULL OR likely_low IS NULL OR likely_high >= likely_low', name=op.f('ck_pregrade_records_band_not_inverted')),
    sa.CheckConstraint('p_at_least IS NULL OR (p_at_least >= 0 AND p_at_least <= 1)', name=op.f('ck_pregrade_records_p_at_least_unit_interval')),
    sa.ForeignKeyConstraint(['card_id'], ['cards.id'], name=op.f('fk_pregrade_records_card_id_cards'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_pregrade_records_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pregrade_records'))
    )
    with op.batch_alter_table('pregrade_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pregrade_records_card_id'), ['card_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_pregrade_records_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('pregrade_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pregrade_records_user_id'))
        batch_op.drop_index(batch_op.f('ix_pregrade_records_card_id'))

    op.drop_table('pregrade_records')
