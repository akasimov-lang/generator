"""Persistent images used by generated articles."""
from alembic import op
import sqlalchemy as sa

revision = '0065_article_images'
down_revision = '0064_template_knowledge'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('article_images',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('site_id', sa.String(36), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('request_key', sa.String(64), nullable=False, unique=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('model', sa.String(120), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('error', sa.Text()), sa.Column('sha256', sa.String(64)),
        sa.Column('image_data', sa.LargeBinary()), sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_article_images_site_id', 'article_images', ['site_id'])
    op.create_index('ix_article_images_sha256', 'article_images', ['sha256'])


def downgrade():
    op.drop_table('article_images')
