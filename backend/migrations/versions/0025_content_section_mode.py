"""Add content placement mode for menu sections.

Revision ID: 0025_content_section_mode
Revises: 0024_default_prompt_v6
Create Date: 2026-08-25
"""

from alembic import op


revision = "0025_content_section_mode"
down_revision = "0024_default_prompt_v6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE content_items "
        "ADD COLUMN IF NOT EXISTS section_content_mode VARCHAR(24) DEFAULT 'nested' NOT NULL"
    )
    op.execute(
        "ALTER TABLE content_items "
        "ADD COLUMN IF NOT EXISTS section_source_slug VARCHAR(240)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS section_source_slug")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS section_content_mode")
