"""Network observations and durable operation receipts."""
from alembic import op
import sqlalchemy as sa

revision = "0043_network_operations"
down_revision = "0042_main_domain_history"
branch_labels = None
depends_on = None


def upgrade():
    for name, default in (("x_default_history", "[]"), ("alternate_domain_history", "[]"), ("network_state", "{}")):
        op.add_column("sites", sa.Column(name, sa.JSON(), nullable=False, server_default=default))
    op.create_table(
        "network_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("initiator", sa.String(80), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_network_operations_site_id", "network_operations", ["site_id"])


def downgrade():
    op.drop_table("network_operations")
    for name in ("network_state", "alternate_domain_history", "x_default_history"):
        op.drop_column("sites", name)
