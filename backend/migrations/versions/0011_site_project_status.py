"""Add editable project focus status.

Revision ID: 0011_site_project_status
Revises: 0010_site_homepage_title
Create Date: 2026-08-12
"""

from alembic import op


revision = "0011_site_project_status"
down_revision = "0010_site_homepage_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS project_status VARCHAR(32) DEFAULT 'working' NOT NULL")
    op.execute("UPDATE sites SET project_status = CASE WHEN is_test_project THEN 'test' ELSE 'working' END")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sites_project_status ON sites (project_status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sites_project_status")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS project_status")
