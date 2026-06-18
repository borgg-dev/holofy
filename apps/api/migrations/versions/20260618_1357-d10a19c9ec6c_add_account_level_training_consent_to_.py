"""Add account-level training consent to users.

Training consent gets a durable home on the account, the source of truth the privacy screen
reads and writes: ``training_consent`` (default ``False`` — the privacy-by-design guarantee,
charter §3.5 / GDPR), a ``training_consent_at`` grant stamp, a ``training_consent_revoked_at``
revocation stamp, and an audit ``consent_note``. A check constraint forbids the
consent-active-and-revoked contradiction, mirroring the per-record capture tables.

``training_consent`` is added NOT NULL with a temporary ``server_default`` of false so existing
users backfill to "not consented" — the only safe default for accounts created before this
preference existed — then the server default is dropped so the column matches the model (which
sets the default in Python, like the capture tables) and ``alembic check`` stays clean.
Authored against SQLite (test) but applies to the Postgres prod target via ``render_as_batch``.

Revision ID: d10a19c9ec6c
Revises: ae8e7df2bb19
Create Date: 2026-06-18 13:57:37.188785
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd10a19c9ec6c'
down_revision: str | None = 'ae8e7df2bb19'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'training_consent',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column('training_consent_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column('training_consent_revoked_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column('consent_note', sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            'consent_not_active_when_revoked',
            'NOT (training_consent AND training_consent_revoked_at IS NOT NULL)',
        )
    # The server default existed only to backfill existing rows; the model carries the default
    # in Python (as the capture tables do), so drop it to keep the column aligned.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('training_consent', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        # The naming convention rendered the create as ck_users_<constraint>; drop the rendered
        # name verbatim (op.f) so the convention isn't applied a second time.
        batch_op.drop_constraint(
            op.f('ck_users_consent_not_active_when_revoked'), type_='check'
        )
        batch_op.drop_column('consent_note')
        batch_op.drop_column('training_consent_revoked_at')
        batch_op.drop_column('training_consent_at')
        batch_op.drop_column('training_consent')
