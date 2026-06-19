"""Add password-account credentials to users (email + password_hash).

Real accounts: a registered user carries a unique ``email`` login handle and a self-describing
scrypt ``password_hash`` (never plaintext). Both are nullable — dev/federated users have no
password, and existing rows backfill to null — and ``email`` is uniquely indexed so two
accounts can't share a login. Authored against SQLite (test) and applies to the Postgres prod
target via ``render_as_batch``.

Revision ID: b1f2a3c4d5e6
Revises: f7c6cff46e4c
Create Date: 2026-06-19 17:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b1f2a3c4d5e6'
down_revision: str | None = 'f7c6cff46e4c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=320), nullable=True))
        batch_op.add_column(sa.Column('password_hash', sa.Text(), nullable=True))
        batch_op.create_unique_constraint(batch_op.f('uq_users_email'), ['email'])


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_users_email'), type_='unique')
        batch_op.drop_column('password_hash')
        batch_op.drop_column('email')
