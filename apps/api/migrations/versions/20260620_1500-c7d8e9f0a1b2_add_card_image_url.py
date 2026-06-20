"""Add image_url to cards (catalog artwork for the real card face).

The app renders the detected card's real artwork as the foil-card face; the URL is the
TCGdex card image resolved to a concrete high-res asset. Nullable — a printing the catalog
has no image for keeps the placeholder. Authored against SQLite (test) and applies to the
Postgres prod target via batch alter.

Revision ID: c7d8e9f0a1b2
Revises: b1f2a3c4d5e6
Create Date: 2026-06-20 15:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: str | None = 'b1f2a3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.drop_column('image_url')
