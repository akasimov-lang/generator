"""Track publication campaign membership and lifecycle.

Revision ID: 0005_campaign_lifecycle
Revises: 0004_task_author
Create Date: 2026-08-05
"""

from alembic import op


revision = "0005_campaign_lifecycle"
down_revision = "0004_task_author"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS publication_campaign_id VARCHAR(36)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_items_publication_campaign_id "
        "ON content_items (publication_campaign_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_content_items_publication_campaign_id")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS publication_campaign_id")
