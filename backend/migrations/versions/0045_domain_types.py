"""Persist manually assigned network domain types."""
from alembic import op
import sqlalchemy as sa

revision = "0045_domain_types"
down_revision = "0044_auto_reglue"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sites", sa.Column("domain_types", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade():
    op.drop_column("sites", "domain_types")
