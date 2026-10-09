"""Keep competitor HTML snapshots separate from template polling payloads."""
from alembic import op
import sqlalchemy as sa

revision = "0054_template_sources"
down_revision = "0053_auto_lb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("template_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("site_templates.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("raw_html", sa.Text()),
        sa.Column("rendered_html", sa.Text()),
        sa.Column("google_html", sa.Text()),
        sa.Column("capture", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_template_sources_template_id", "template_sources", ["template_id"])


def downgrade():
    op.drop_table("template_sources")
