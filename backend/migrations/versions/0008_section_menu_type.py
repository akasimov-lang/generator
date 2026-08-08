"""Store the header/footer placement for project menu items.

Revision ID: 0008_section_menu_type
Revises: 0007_generation_progress
Create Date: 2026-08-08
"""

from alembic import op


revision = "0008_section_menu_type"
down_revision = "0007_generation_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS menu_type VARCHAR(20) DEFAULT 'header' NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE sections DROP COLUMN IF EXISTS menu_type")
