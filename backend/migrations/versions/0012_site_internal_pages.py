"""Store internal page counts for cached projects.

Revision ID: 0012_site_internal_pages
Revises: 0011_site_project_status
Create Date: 2026-08-12
"""

from alembic import op


revision = "0012_site_internal_pages"
down_revision = "0011_site_project_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS internal_pages_count INTEGER DEFAULT 0 NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS internal_pages_count")
