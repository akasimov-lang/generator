"""Audit page edits, including snapshots and uncertain external write results."""
from alembic import op
import sqlalchemy as sa

revision = "0055_project_page_edits"
down_revision = "0054_template_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("project_page_edits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("page_key", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.String(160), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("before_page", sa.JSON(), nullable=False),
        sa.Column("after_page", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_project_page_edits_site_id", "project_page_edits", ["site_id"])

    op.create_table("project_page_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("page_key", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.String(160), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("ai_providers.id"), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("input_content", sa.JSON(), nullable=False),
        sa.Column("result_content", sa.JSON()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_project_page_drafts_site_id", "project_page_drafts", ["site_id"])


def downgrade():
    op.drop_table("project_page_drafts")
    op.drop_table("project_page_edits")
