"""Remember domains observed as the project's Main."""
from alembic import op
import sqlalchemy as sa

revision = "0042_main_domain_history"
down_revision = "0041_canonical_faq_blocks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sites", sa.Column("main_domain_history", sa.JSON(), nullable=False, server_default="[]"))
    sites = sa.table("sites", sa.column("id", sa.String()), sa.column("cache_canon", sa.Text()), sa.column("main_domain_history", sa.JSON()))
    connection = op.get_bind()
    for row in connection.execute(sa.select(sites.c.id, sites.c.cache_canon)).mappings():
        canon = (row["cache_canon"] or "").strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
        if canon:
            connection.execute(sites.update().where(sites.c.id == row["id"]).values(main_domain_history=[canon]))


def downgrade():
    op.drop_column("sites", "main_domain_history")
