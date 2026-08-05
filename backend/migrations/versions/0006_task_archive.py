"""Add soft-delete archive fields to generation tasks.

Revision ID: 0006_task_archive
Revises: 0005_campaign_lifecycle
Create Date: 2026-08-05
"""

from alembic import op


revision = "0006_task_archive"
down_revision = "0005_campaign_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS archived_by_user_id VARCHAR(36)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_generation_tasks_archived_at "
        "ON generation_tasks (archived_at)"
    )
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS competitor_research_progress INTEGER DEFAULT 0 NOT NULL")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS competitor_research_error TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS competitor_research_error")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS competitor_research_progress")
    op.execute("DROP INDEX IF EXISTS ix_generation_tasks_archived_at")
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS archived_by_user_id")
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS archived_at")
