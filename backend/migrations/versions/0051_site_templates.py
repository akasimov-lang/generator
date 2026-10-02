"""Standalone website template drafts."""
from alembic import op
import sqlalchemy as sa

revision = "0051_site_templates"
down_revision = "0050_external_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("brand", sa.String(160), nullable=False),
        sa.Column("geo", sa.String(40), nullable=False),
        sa.Column("language", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("phase", sa.String(120), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("request_data", sa.JSON(), nullable=False),
        sa.Column("document", sa.JSON()),
        sa.Column("html", sa.Text()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("site_templates")
