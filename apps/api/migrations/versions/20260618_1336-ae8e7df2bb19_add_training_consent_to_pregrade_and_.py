"""Add per-record training consent to pregrade_records and authenticity_records.

Pre-grades and authenticity screens become first-class members of the consented training
moat: each gains its own revocable ``training_consent`` (default ``False`` — the
privacy-by-design guarantee, charter §3.5 / GDPR), a ``consent_revoked_at`` stamp, and an
audit ``consent_note``, mirroring ``scan_records``. A check constraint forbids the
consent-active-and-revoked contradiction on each table.

``training_consent`` is added NOT NULL with a temporary ``server_default`` of false so
existing rows backfill to "not consented" — the only safe default for personal data already
captured without a training opt-in — then the server default is dropped so the column matches
the model (which sets the default in Python, like ``scan_records``) and ``alembic check`` stays
clean. Authored against SQLite (test) but applies to the Postgres prod target via
``render_as_batch``.

Revision ID: ae8e7df2bb19
Revises: a5554d18a50b
Create Date: 2026-06-18 13:36:00.387671
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'ae8e7df2bb19'
down_revision: str | None = 'a5554d18a50b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table, constraint in (
        ('authenticity_records', 'authenticity_consent_not_active_when_revoked'),
        ('pregrade_records', 'pregrade_consent_not_active_when_revoked'),
    ):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'training_consent',
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
            batch_op.add_column(
                sa.Column('consent_revoked_at', sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.add_column(sa.Column('consent_note', sa.Text(), nullable=True))
            batch_op.create_check_constraint(
                constraint,
                'NOT (training_consent AND consent_revoked_at IS NOT NULL)',
            )
        # The server default existed only to backfill existing rows; the model carries the
        # default in Python (as scan_records does), so drop it to keep the column aligned.
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('training_consent', server_default=None)


def downgrade() -> None:
    for table, constraint in (
        ('pregrade_records', 'pregrade_consent_not_active_when_revoked'),
        ('authenticity_records', 'authenticity_consent_not_active_when_revoked'),
    ):
        with op.batch_alter_table(table, schema=None) as batch_op:
            # The naming convention rendered the create as ck_<table>_<constraint>; drop the
            # rendered name verbatim (op.f) so the convention isn't applied a second time.
            batch_op.drop_constraint(op.f(f'ck_{table}_{constraint}'), type_='check')
            batch_op.drop_column('consent_note')
            batch_op.drop_column('consent_revoked_at')
            batch_op.drop_column('training_consent')
