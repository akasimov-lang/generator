"""Explicit per-menu-item casino review switch, disabled by default."""
from alembic import op
import sqlalchemy as sa

revision = "0040_section_review"
down_revision = "0039_publication_author"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sections", sa.Column("is_review", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("sections", "is_review")
