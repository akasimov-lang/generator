"""Store language and GEO for cached projects.

Revision ID: 0014_site_language_geo
Revises: 0013_site_domains_count
Create Date: 2026-08-12
"""

from alembic import op


revision = "0014_site_language_geo"
down_revision = "0013_site_domains_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS cache_language VARCHAR(40)")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS cache_geo VARCHAR(40)")


def downgrade() -> None:
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS cache_geo")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS cache_language")
