"""Remove local credentials; preserve identity foreign keys and audit history."""
from alembic import op

revision = '0050_external_auth'
down_revision = '0049_background_jobs'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET password_hash = '', is_admin = false, is_active = false")


def downgrade():
    # Deleted passwords cannot be recovered; never recreate a default password.
    pass
