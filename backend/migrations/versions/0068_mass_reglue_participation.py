"""Per-project participation and confirmed Main-change timestamp."""
from alembic import op
import sqlalchemy as sa
revision = '0068_mass_reglue_participation'
down_revision = '0067_reglue_reserve_domains'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sites', sa.Column('reglue_participation', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('sites', sa.Column('last_reglue_at', sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column('sites', 'last_reglue_at')
    op.drop_column('sites', 'reglue_participation')
