"""Store each user's favorite sites.

Revision ID: 0018_user_favorite_sites
Revises: 0017_section_sync_status
Create Date: 2026-08-13
"""

from alembic import op


revision = "0018_user_favorite_sites"
down_revision = "0017_section_sync_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_site_ids JSON DEFAULT '[]' NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS favorite_site_ids")
