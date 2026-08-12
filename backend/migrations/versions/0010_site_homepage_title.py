"""Store the cached homepage title for sites.

Revision ID: 0010_site_homepage_title
Revises: 0009_site_cache_sync
Create Date: 2026-08-12
"""

from alembic import op


revision = "0010_site_homepage_title"
down_revision = "0009_site_cache_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS homepage_title TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS homepage_title")
