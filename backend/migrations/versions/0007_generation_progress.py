"""Track per-topic content generation progress.

Revision ID: 0007_generation_progress
Revises: 0006_task_archive
Create Date: 2026-08-05
"""

from alembic import op


revision = "0007_generation_progress"
down_revision = "0006_task_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS generation_progress INTEGER DEFAULT 0 NOT NULL")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS generation_error TEXT")
    op.execute(
        "UPDATE content_items SET generation_progress = 100 "
        "WHERE generated_at IS NOT NULL AND status IN ('generated', 'approved', 'scheduled', 'retry_scheduled', 'publication_paused', 'publishing', 'published')"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS generation_error")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS generation_progress")
