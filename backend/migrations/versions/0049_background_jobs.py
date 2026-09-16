"""Durable handoff for long user operations."""
from alembic import op
import sqlalchemy as sa

revision = "0049_background_jobs"
down_revision = "0048_project_notices"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("background_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])


def downgrade():
    op.drop_table("background_jobs")
