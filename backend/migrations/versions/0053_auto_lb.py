"""Project-scoped AutoLB anchor lists and topics."""
from alembic import op
import sqlalchemy as sa

revision = "0053_auto_lb"
down_revision = "0052_site_templates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auto_lb_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("ai_providers.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("result_text", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auto_lb_generations_site_id", "auto_lb_generations", ["site_id"])


def downgrade():
    op.drop_table("auto_lb_generations")
