"""Preserve local project list exclusions across synchronization."""
from alembic import op
import sqlalchemy as sa
revision = "0059_hidden_projects"
down_revision = "0058_manual_fibery_name"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sites", sa.Column("hidden_from_projects", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("sites", "hidden_from_projects")
