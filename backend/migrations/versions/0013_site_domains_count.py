"""Store domain counts for cached projects.

Revision ID: 0013_site_domains_count
Revises: 0012_site_internal_pages
Create Date: 2026-08-12
"""

from alembic import op


revision = "0013_site_domains_count"
down_revision = "0012_site_internal_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS domains_count INTEGER DEFAULT 0 NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS domains_count")
