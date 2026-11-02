"""Record project entry dates with the requested legacy dates in Moscow time."""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0062_site_added_to_system"
down_revision = "0061_project_team"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sites", sa.Column("added_to_system_at", sa.DateTime(timezone=True), nullable=True))
    sites = sa.table("sites", sa.column("created_at", sa.DateTime(timezone=True)),
                     sa.column("added_to_system_at", sa.DateTime(timezone=True)))
    # Preserve the system's original creation timestamps whenever they are known.
    # Only undated legacy records use the user-specified 1 September, Moscow time.
    legacy = datetime(2026, 8, 31, 21, tzinfo=timezone.utc)
    op.get_bind().execute(sites.update().values(
        added_to_system_at=sa.func.coalesce(sites.c.created_at, legacy)))
    with op.batch_alter_table("sites") as batch:
        batch.alter_column("added_to_system_at", existing_type=sa.DateTime(timezone=True),
                           nullable=False, server_default=sa.func.now())


def downgrade():
    op.drop_column("sites", "added_to_system_at")
