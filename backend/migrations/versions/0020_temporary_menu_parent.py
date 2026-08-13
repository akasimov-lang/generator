"""Track temporary parent menu references.

Revision ID: 0020_temporary_menu_parent
Revises: 0019_site_menu_capabilities
Create Date: 2026-08-13
"""

from alembic import op


revision = "0020_temporary_menu_parent"
down_revision = "0019_site_menu_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS is_temporary_parent BOOLEAN DEFAULT FALSE NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE sections DROP COLUMN IF EXISTS is_temporary_parent")
