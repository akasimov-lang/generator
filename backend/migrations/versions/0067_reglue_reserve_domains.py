"""Shared reserve pool with exclusive allocation and assignment history."""
from alembic import op
import sqlalchemy as sa

revision = '0067_reglue_reserve_domains'
down_revision = '0066_project_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('reglue_reserve_domains',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('domain', sa.String(253), nullable=False, unique=True),
        sa.Column('domain_type', sa.String(12), nullable=False),
        sa.Column('brand', sa.String(160)),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('added_by', sa.String(160), nullable=False),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id', ondelete='SET NULL')),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('auto_reglue_runs.id', ondelete='SET NULL')),
        sa.Column('assigned_at', sa.DateTime(timezone=True)),
        sa.Column('error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_reglue_reserve_domains_status', 'reglue_reserve_domains', ['status'])


def downgrade():
    op.drop_table('reglue_reserve_domains')
