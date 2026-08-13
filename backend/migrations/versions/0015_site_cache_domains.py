"""Store cached project domain lists.

Revision ID: 0015_site_cache_domains
Revises: 0014_site_language_geo
Create Date: 2026-08-12
"""

from alembic import op


revision = "0015_site_cache_domains"
down_revision = "0014_site_language_geo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS cache_domains JSON DEFAULT '[]'")


def downgrade() -> None:
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS cache_domains")
