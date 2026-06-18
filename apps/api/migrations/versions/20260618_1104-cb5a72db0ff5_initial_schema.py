"""Initial Holofy schema.

The full P1.2 domain: users, the canonical card catalog, owned collection items, the
portfolio value-over-time series, scan events (with the revocable training-consent flag),
and the persisted € price observations. Authored against SQLite (test) but applies to the
Postgres prod target — the GUID/timestamp types degrade portably and ``render_as_batch``
keeps the SQLite path valid.

Revision ID: cb5a72db0ff5
Revises:
Create Date: 2026-06-18 11:04:59.842690
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

import app.db.types


revision: str = 'cb5a72db0ff5'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('cards',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('canonical_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('set_name', sa.String(length=255), nullable=False),
    sa.Column('set_code', sa.String(length=32), nullable=False),
    sa.Column('collector_number', sa.String(length=16), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('variant', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cards')),
    sa.UniqueConstraint('set_code', 'collector_number', 'variant', 'language', name=op.f('uq_cards_set_code_collector_number_variant_language'))
    )
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cards_canonical_id'), ['canonical_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_cards_name'), ['name'], unique=False)

    op.create_table('users',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('auth_provider', sa.String(length=32), nullable=True),
    sa.Column('auth_subject', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('auth_provider', 'auth_subject', name=op.f('uq_users_auth_provider_auth_subject'))
    )
    op.create_table('collection_items',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('user_id', app.db.types.GUID(), nullable=False),
    sa.Column('card_id', app.db.types.GUID(), nullable=False),
    sa.Column('condition', sa.String(length=16), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('acquired_price_eur', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('acquired_on', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('acquired_price_eur IS NULL OR acquired_price_eur >= 0', name=op.f('ck_collection_items_acquired_price_non_negative')),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_collection_items_quantity_positive')),
    sa.ForeignKeyConstraint(['card_id'], ['cards.id'], name=op.f('fk_collection_items_card_id_cards'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_collection_items_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_collection_items')),
    sa.UniqueConstraint('user_id', 'card_id', 'condition', name=op.f('uq_collection_items_user_id_card_id_condition'))
    )
    with op.batch_alter_table('collection_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_collection_items_card_id'), ['card_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_collection_items_user_id'), ['user_id'], unique=False)

    op.create_table('portfolio_snapshots',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('user_id', app.db.types.GUID(), nullable=False),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('total_value_eur', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('total_cost_basis_eur', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('item_count', sa.Integer(), nullable=False),
    sa.Column('valuation_basis', sa.String(length=16), nullable=False),
    sa.CheckConstraint('item_count >= 0', name=op.f('ck_portfolio_snapshots_item_count_non_negative')),
    sa.CheckConstraint('total_value_eur >= 0', name=op.f('ck_portfolio_snapshots_total_value_non_negative')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_portfolio_snapshots_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_portfolio_snapshots')),
    sa.UniqueConstraint('user_id', 'captured_at', name=op.f('uq_portfolio_snapshots_user_id_captured_at'))
    )
    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_snapshots_captured_at'), ['captured_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_portfolio_snapshots_user_id'), ['user_id'], unique=False)

    op.create_table('price_observations',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('card_id', app.db.types.GUID(), nullable=False),
    sa.Column('value_eur', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('source', sa.String(length=24), nullable=False),
    sa.Column('basis', sa.String(length=16), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('value_eur >= 0', name=op.f('ck_price_observations_value_non_negative')),
    sa.ForeignKeyConstraint(['card_id'], ['cards.id'], name=op.f('fk_price_observations_card_id_cards'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_price_observations')),
    sa.UniqueConstraint('card_id', 'source', 'basis', 'observed_at', name=op.f('uq_price_observations_card_id_source_basis_observed_at'))
    )
    with op.batch_alter_table('price_observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_price_observations_card_id'), ['card_id'], unique=False)
        batch_op.create_index('ix_price_observations_card_id_observed_at', ['card_id', 'observed_at'], unique=False)

    op.create_table('scan_records',
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('user_id', app.db.types.GUID(), nullable=False),
    sa.Column('capture_ref', sa.String(length=512), nullable=False),
    sa.Column('candidates', sa.JSON(), nullable=False),
    sa.Column('top_confidence', sa.Float(), nullable=True),
    sa.Column('outcome', sa.String(length=24), nullable=False),
    sa.Column('resolved_card_id', app.db.types.GUID(), nullable=True),
    sa.Column('training_consent', sa.Boolean(), nullable=False),
    sa.Column('consent_revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consent_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('NOT (training_consent AND consent_revoked_at IS NOT NULL)', name=op.f('ck_scan_records_consent_not_active_when_revoked')),
    sa.CheckConstraint('top_confidence IS NULL OR (top_confidence >= 0 AND top_confidence <= 1)', name=op.f('ck_scan_records_top_confidence_unit_interval')),
    sa.ForeignKeyConstraint(['resolved_card_id'], ['cards.id'], name=op.f('fk_scan_records_resolved_card_id_cards'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_scan_records_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scan_records'))
    )
    with op.batch_alter_table('scan_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_scan_records_resolved_card_id'), ['resolved_card_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_scan_records_user_id'), ['user_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('scan_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scan_records_user_id'))
        batch_op.drop_index(batch_op.f('ix_scan_records_resolved_card_id'))

    op.drop_table('scan_records')
    with op.batch_alter_table('price_observations', schema=None) as batch_op:
        batch_op.drop_index('ix_price_observations_card_id_observed_at')
        batch_op.drop_index(batch_op.f('ix_price_observations_card_id'))

    op.drop_table('price_observations')
    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_snapshots_user_id'))
        batch_op.drop_index(batch_op.f('ix_portfolio_snapshots_captured_at'))

    op.drop_table('portfolio_snapshots')
    with op.batch_alter_table('collection_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_collection_items_user_id'))
        batch_op.drop_index(batch_op.f('ix_collection_items_card_id'))

    op.drop_table('collection_items')
    op.drop_table('users')
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cards_name'))
        batch_op.drop_index(batch_op.f('ix_cards_canonical_id'))

    op.drop_table('cards')
