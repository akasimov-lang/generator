"""Allow global prompt templates without a site.

Revision ID: 0002_prompt_site_nullable
Revises: 0001_current_schema
Create Date: 2026-07-14
"""

from alembic import op


revision = "0002_prompt_site_nullable"
down_revision = "0001_current_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("prompt_templates", "site_id", nullable=True)


def downgrade() -> None:
    op.alter_column("prompt_templates", "site_id", nullable=False)
