"""Add email verification + session-revocation epoch to users.

``email_verified_at`` records when the account confirmed its email (null = unverified). The account
works unverified during the beta; the column lets a flow require ownership later. ``sessions_valid_from``
is the session-revocation epoch: a session bearer issued before this instant is rejected, so a
password reset (or an explicit log-out-everywhere) can invalidate every outstanding token — the
revocation the stateless bearer otherwise lacks. Both nullable. Authored against SQLite (test) and
applies to the Postgres prod target via batch alter.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-06-23 16:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e9f0a1b2c3'
down_revision: str | None = 'c7d8e9f0a1b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('sessions_valid_from', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('sessions_valid_from')
        batch_op.drop_column('email_verified_at')
