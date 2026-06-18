"""Drop the redundant single-column card_id index on price_observations.

The composite ``ix_price_observations_card_id_observed_at`` already leads with ``card_id``,
so a query filtering on ``card_id`` alone is served by that index's leading column. The
standalone ``ix_price_observations_card_id`` (created with the initial schema) only duplicated
that prefix and added write overhead on every price-snapshot insert, so it is dropped here;
the composite index — the one the hot "latest point for this card" read needs — stays.

Authored against SQLite (test) but applies to the Postgres prod target via ``render_as_batch``.

Revision ID: f7c6cff46e4c
Revises: d10a19c9ec6c
Create Date: 2026-06-18 15:08:05.432802
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = 'f7c6cff46e4c'
down_revision: str | None = 'd10a19c9ec6c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('price_observations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_price_observations_card_id'))


def downgrade() -> None:
    with op.batch_alter_table('price_observations', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_price_observations_card_id'), ['card_id'], unique=False
        )
