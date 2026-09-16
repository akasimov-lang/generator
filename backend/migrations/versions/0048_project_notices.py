"""Persist shared project warning state."""
from alembic import op
import sqlalchemy as sa

revision = "0048_project_notices"
down_revision = "0047_site_brand"
branch_labels = None
depends_on = None


def upgrade():
    for name, size in [("menu_warning", 40), ("core_update_notice", 160), ("core_update_acknowledged", 160)]:
        op.add_column("sites", sa.Column(name, sa.String(size), nullable=True))


def downgrade():
    for name in ["core_update_acknowledged", "core_update_notice", "menu_warning"]:
        op.drop_column("sites", name)
