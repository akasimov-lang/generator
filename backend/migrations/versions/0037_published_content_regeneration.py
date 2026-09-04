"""Store settings for published content replacements.

Revision ID: 0037_published_regeneration
Revises: 0036_content_indexing
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0037_published_regeneration"
down_revision = "0036_content_indexing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_revisions", sa.Column("generation_options", sa.JSON(), nullable=True))
    op.add_column("content_revisions", sa.Column("source_status", sa.String(length=40), nullable=False, server_default="generated"))
    op.add_column("content_revisions", sa.Column("is_published_replacement", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("content_revisions", "is_published_replacement")
    op.drop_column("content_revisions", "source_status")
    op.drop_column("content_revisions", "generation_options")
