"""Track generation task author.

Revision ID: 0004_task_author
Revises: 0003_competitor_research
Create Date: 2026-08-04
"""

from alembic import op


revision = "0004_task_author"
down_revision = "0003_competitor_research"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS created_by_user_id VARCHAR(36)")


def downgrade() -> None:
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS created_by_user_id")
