"""Durable schedule cursors independent of config and run update timestamps."""
from alembic import op
import sqlalchemy as sa

revision = "0046_auto_reglue_schedule"
down_revision = "0045_domain_types"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auto_reglue_schedules",
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("anchor_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auto_reglue_schedules_next_run_at", "auto_reglue_schedules", ["next_run_at"])


def downgrade():
    op.drop_table("auto_reglue_schedules")
