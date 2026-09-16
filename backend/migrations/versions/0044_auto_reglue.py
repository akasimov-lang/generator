"""Explicit configuration and durable per-project automatic reglue runs."""
from alembic import op
import sqlalchemy as sa

revision = '0044_auto_reglue'
down_revision = '0043_network_operations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auto_reglue_configs',
        sa.Column('key', sa.String(80), primary_key=True),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('auto_reglue_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('initiator', sa.String(80), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('phase', sa.String(32), nullable=False),
        sa.Column('plan', sa.JSON(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_auto_reglue_runs_site_id', 'auto_reglue_runs', ['site_id'])


def downgrade():
    op.drop_table('auto_reglue_runs')
    op.drop_table('auto_reglue_configs')
