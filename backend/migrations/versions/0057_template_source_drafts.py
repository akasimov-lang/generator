"""Autosave competitor HTML before creating a template task."""
from alembic import op
import sqlalchemy as sa
revision = "0057_template_source_drafts"
down_revision = "0056_site_fibery_name"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("template_source_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("google_html", sa.Text(), nullable=False),
        sa.Column("capture", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_template_source_drafts_user_id", "template_source_drafts", ["user_id"])


def downgrade():
    op.drop_table("template_source_drafts")
