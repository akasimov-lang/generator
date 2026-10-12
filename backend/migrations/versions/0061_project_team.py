"""Cache project team; NULL means not yet known, empty means unassigned."""
from alembic import op
import sqlalchemy as sa
revision = "0061_project_team"
down_revision = "0060_site_type"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sites", sa.Column("project_team", sa.String(160), nullable=True))

def downgrade():
    op.drop_column("sites", "project_team")
