"""Persist shared project brands and protect manual overrides."""
from alembic import op
import sqlalchemy as sa

revision = "0047_site_brand"
down_revision = "0046_auto_reglue_schedule"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sites", sa.Column("brand", sa.String(160), nullable=False, server_default="Общие ключи"))
    op.add_column("sites", sa.Column("brand_source", sa.String(20), nullable=False, server_default="generic"))

def downgrade():
    op.drop_column("sites", "brand_source")
    op.drop_column("sites", "brand")
