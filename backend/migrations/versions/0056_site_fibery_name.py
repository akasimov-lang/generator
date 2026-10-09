"""Cache the Webdev Fibery project name independently of its technical domain."""
from alembic import op
import sqlalchemy as sa
revision = "0056_site_fibery_name"
down_revision = "0055_project_page_edits"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sites", sa.Column("fibery_name", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("sites", "fibery_name")
