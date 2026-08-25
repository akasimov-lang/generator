"""Add optional generated page titles.

Revision ID: 0030_generate_title
Revises: 0029_publication_status_code
Create Date: 2026-08-25
"""

from alembic import op


revision = "0030_generate_title"
down_revision = "0029_publication_status_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE generation_tasks "
        "ADD COLUMN IF NOT EXISTS generate_title BOOLEAN DEFAULT FALSE NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS generate_title")
