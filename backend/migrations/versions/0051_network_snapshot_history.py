"""add network snapshot history

Revision ID: 0051_network_snapshot_history
Revises: 0050_external_auth
"""
from alembic import op
import sqlalchemy as sa


revision = "0051_network_snapshot_history"
down_revision = "0050_external_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column("network_snapshot_history", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("sites", "network_snapshot_history")
