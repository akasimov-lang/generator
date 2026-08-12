"""Store external cache metadata for sites.

Revision ID: 0009_site_cache_sync
Revises: 0008_section_menu_type
Create Date: 2026-08-12
"""

from alembic import op


revision = "0009_site_cache_sync"
down_revision = "0008_section_menu_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS external_project_id VARCHAR(200)")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS cache_canon TEXT")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS is_test_project BOOLEAN DEFAULT FALSE NOT NULL")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS has_menu BOOLEAN DEFAULT FALSE NOT NULL")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS cache_synced_at TIMESTAMP WITH TIME ZONE")
    op.execute("UPDATE sites SET is_test_project = TRUE WHERE external_project_id IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sites_external_project_id ON sites (external_project_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sites_external_project_id")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS cache_synced_at")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS has_menu")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS is_test_project")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS cache_canon")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS external_project_id")
