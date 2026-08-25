"""Track template support separately from live menu visibility.

Revision ID: 0027_live_menu_visibility
Revises: 0026_default_working_prompt
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_live_menu_visibility"
down_revision = "0026_default_working_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS header_menu_template_rendered BOOLEAN")
    op.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS footer_menu_template_rendered BOOLEAN")
    op.execute("UPDATE sites SET header_menu_template_rendered = header_menu_rendered")
    op.execute("UPDATE sites SET footer_menu_template_rendered = footer_menu_rendered")
    op.execute("UPDATE sites SET menu_capabilities_checked_at = NULL")
    op.create_table(
        "menu_visibility_checks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_visibility_checks_site_id", "menu_visibility_checks", ["site_id"])
    op.create_index("ix_menu_visibility_checks_status", "menu_visibility_checks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_menu_visibility_checks_status", table_name="menu_visibility_checks")
    op.drop_index("ix_menu_visibility_checks_site_id", table_name="menu_visibility_checks")
    op.drop_table("menu_visibility_checks")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS footer_menu_template_rendered")
    op.execute("ALTER TABLE sites DROP COLUMN IF EXISTS header_menu_template_rendered")
