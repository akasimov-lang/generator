"""Track deletion of published project pages.

Revision ID: 0028_published_content_deletion
Revises: 0027_live_menu_visibility
Create Date: 2026-08-25
"""

from alembic import op


revision = "0028_published_content_deletion"
down_revision = "0027_live_menu_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS deletion_confirmed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS deletion_error TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS deletion_error")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS deletion_confirmed_at")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS deletion_requested_at")
