"""Shared brand/GEO competitor examples and generic-site structure."""
from alembic import op
import sqlalchemy as sa
revision = '0064_template_knowledge'
down_revision = '0063_page_draft_metadata'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('template_knowledge_examples',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('brand', sa.String(160), nullable=False),
        sa.Column('brand_key', sa.String(200), nullable=False),
        sa.Column('geo', sa.String(2), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('structure', sa.JSON(), nullable=False),
        sa.Column('created_by_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('brand_key','geo','sha256',name='uq_template_knowledge_scope_sha'))
    op.create_index('ix_template_knowledge_examples_brand_key','template_knowledge_examples',['brand_key'])


def downgrade():
    op.drop_table('template_knowledge_examples')
