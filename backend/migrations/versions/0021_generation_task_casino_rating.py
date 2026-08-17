"""Add optional casino rating generation setting.

Revision ID: 0021_casino_rating
Revises: 0020_temporary_menu_parent
Create Date: 2026-08-17
"""

from alembic import op


revision = "0021_casino_rating"
down_revision = "0020_temporary_menu_parent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE generation_tasks "
        "ADD COLUMN IF NOT EXISTS include_casino_rating BOOLEAN DEFAULT FALSE NOT NULL"
    )
    op.execute(
        "ALTER TABLE content_items "
        "ADD COLUMN IF NOT EXISTS include_casino_rating BOOLEAN DEFAULT FALSE NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS include_casino_rating")
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS include_casino_rating")
