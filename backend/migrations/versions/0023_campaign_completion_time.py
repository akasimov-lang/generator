"""Store campaign completion time.

Revision ID: 0023_campaign_completed
Revises: 0022_task_gen_options
Create Date: 2026-08-17
"""

from alembic import op


revision = "0023_campaign_completed"
down_revision = "0022_task_gen_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE publication_campaigns "
        "ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE publication_campaigns DROP COLUMN IF EXISTS completed_at")
