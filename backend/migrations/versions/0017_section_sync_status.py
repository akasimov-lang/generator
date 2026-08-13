"""Store menu item synchronization state.

Revision ID: 0017_section_sync_status
Revises: 0016_site_menu_library
Create Date: 2026-08-12
"""

from alembic import op


revision = "0017_section_sync_status"
down_revision = "0016_site_menu_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'pending' NOT NULL")
    op.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    op.execute("ALTER TABLE sections DROP COLUMN IF EXISTS synced_at")
    op.execute("ALTER TABLE sections DROP COLUMN IF EXISTS sync_status")
