"""Persist publication requester independently of short-lived request logs."""
from alembic import op
import sqlalchemy as sa

revision = "0039_publication_author"
down_revision = "0038_technical_pages"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("content_items", sa.Column("publication_author", sa.String(80), nullable=True))


def downgrade():
    op.drop_column("content_items", "publication_author")
