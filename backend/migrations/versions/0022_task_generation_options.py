"""Persist task generation display options.

Revision ID: 0022_task_gen_options
Revises: 0021_casino_rating
Create Date: 2026-08-17
"""

from alembic import op


revision = "0022_task_gen_options"
down_revision = "0021_casino_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE generation_tasks "
        "ADD COLUMN IF NOT EXISTS include_toc BOOLEAN DEFAULT TRUE NOT NULL"
    )
    op.execute(
        "ALTER TABLE generation_tasks "
        "ADD COLUMN IF NOT EXISTS include_faq BOOLEAN DEFAULT TRUE NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS include_faq")
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS include_toc")
