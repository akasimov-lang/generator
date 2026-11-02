"""Project notification journal, including failures before a native operation exists."""
from alembic import op
import sqlalchemy as sa

revision = '0066_project_notifications'
down_revision = '0065_article_images'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('project_notifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_key', sa.String(240), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(12), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('context', sa.Text(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('occurrences', sa.Integer(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('site_id', 'event_key', name='uq_project_notification_event'))
    op.create_index('ix_project_notifications_site_id', 'project_notifications', ['site_id'])


def downgrade():
    op.drop_table('project_notifications')
