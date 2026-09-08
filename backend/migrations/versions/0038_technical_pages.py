"""Technical page settings and persistent comparison corpus."""
from alembic import op
import sqlalchemy as sa

revision = "0038_technical_pages"
down_revision = "0037_published_regeneration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("technical_page_settings", sa.JSON(), nullable=True))
    op.create_table(
        "technical_page_texts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_item_id", sa.String(36), nullable=False),
        sa.Column("group_key", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_technical_page_texts_group_key", "technical_page_texts", ["group_key"])
    op.create_index("ix_technical_page_texts_content_item_id", "technical_page_texts", ["content_item_id"])


def downgrade() -> None:
    op.drop_table("technical_page_texts")
    op.drop_column("sites", "technical_page_settings")
