"""Store editor-requested content revision history.

Revision ID: 0033_content_revisions
Revises: 0032_published_tasks
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op


revision = "0033_content_revisions"
down_revision = "0032_published_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_item_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=False),
        sa.Column("generate_title", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("source_json", sa.JSON(), nullable=False),
        sa.Column("revised_json", sa.JSON(), nullable=True),
        sa.Column("source_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revised_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_revisions_content_item_id", "content_revisions", ["content_item_id"])
    op.create_index("ix_content_revisions_status", "content_revisions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_content_revisions_status", table_name="content_revisions")
    op.drop_index("ix_content_revisions_content_item_id", table_name="content_revisions")
    op.drop_table("content_revisions")
