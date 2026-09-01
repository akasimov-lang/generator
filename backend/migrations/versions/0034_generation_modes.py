"""Add dedicated casino review and menu-structure generation modes.

Revision ID: 0034_generation_modes
Revises: 0033_content_revisions
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0034_generation_modes"
down_revision = "0033_content_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_tasks",
        sa.Column("generation_mode", sa.String(length=40), nullable=False, server_default="standard"),
    )
    op.add_column(
        "generation_tasks",
        sa.Column("auto_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("content_items", sa.Column("generation_context", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_items", "generation_context")
    op.drop_column("generation_tasks", "auto_publish")
    op.drop_column("generation_tasks", "generation_mode")
