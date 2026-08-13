"""Store project menu capabilities and section hierarchy.

Revision ID: 0019_site_menu_capabilities
Revises: 0018_user_favorite_sites
Create Date: 2026-08-13
"""

from alembic import op


revision = "0019_site_menu_capabilities"
down_revision = "0018_user_favorite_sites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS cache_server_ip VARCHAR(120)")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS menu_capabilities_checked_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS header_menu_rendered BOOLEAN")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS header_menu_nested BOOLEAN")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS footer_menu_rendered BOOLEAN")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS footer_menu_nested BOOLEAN")
    op.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS parent_id VARCHAR(36)")


def downgrade() -> None:
    op.execute("ALTER TABLE sections DROP COLUMN IF EXISTS parent_id")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS footer_menu_nested")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS footer_menu_rendered")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS header_menu_nested")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS header_menu_rendered")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS menu_capabilities_checked_at")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS cache_server_ip")
