"""Store project-specific menu libraries.

Revision ID: 0016_site_menu_library
Revises: 0015_site_cache_domains
Create Date: 2026-08-12
"""

from alembic import op


revision = "0016_site_menu_library"
down_revision = "0015_site_cache_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS menu_library JSON DEFAULT '[]'")


def downgrade() -> None:
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS menu_library")
