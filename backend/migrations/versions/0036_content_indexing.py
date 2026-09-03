"""Track indexing requests for published content.

Revision ID: 0036_content_indexing
Revises: 0035_casinos_menu_library
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0036_content_indexing"
down_revision = "0035_casinos_menu_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("indexing_status", sa.String(length=24), nullable=True))
    op.add_column("content_items", sa.Column("indexing_task_id", sa.String(length=120), nullable=True))
    op.add_column("content_items", sa.Column("indexing_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_items", sa.Column("indexing_error", sa.Text(), nullable=True))
    op.create_index("ix_content_items_indexing_status", "content_items", ["indexing_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_content_items_indexing_status", table_name="content_items")
    op.drop_column("content_items", "indexing_error")
    op.drop_column("content_items", "indexing_requested_at")
    op.drop_column("content_items", "indexing_task_id")
    op.drop_column("content_items", "indexing_status")
