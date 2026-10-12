"""Preserve manually supplied Fibery names during Webdev synchronization."""
from alembic import op
import sqlalchemy as sa

revision = "0058_manual_fibery_name"
down_revision = "0057_template_source_drafts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sites", sa.Column("fibery_name_manual", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("sites", "fibery_name_manual")
