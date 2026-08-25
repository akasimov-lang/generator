"""Store the latest publication HTTP status on each content item.

Revision ID: 0029_publication_status_code
Revises: 0028_published_content_deletion
Create Date: 2026-08-25
"""

from alembic import op


revision = "0029_publication_status_code"
down_revision = "0028_published_content_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS last_publication_status_code INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS last_publication_status_code")
