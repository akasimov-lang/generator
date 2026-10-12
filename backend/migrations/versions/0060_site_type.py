"""Store explicit project type independently of detected brand."""
from alembic import op
import sqlalchemy as sa
revision = "0060_site_type"
down_revision = "0059_hidden_projects"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sites", sa.Column("site_type", sa.String(24), nullable=True))

def downgrade():
    op.drop_column("sites", "site_type")
