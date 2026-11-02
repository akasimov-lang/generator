"""Metadata drafts and provider-free structural transformations."""
from alembic import op
import sqlalchemy as sa
revision='0063_page_draft_metadata'
down_revision='0062_site_added_to_system'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('project_page_drafts') as batch:
        batch.alter_column('provider_id',existing_type=sa.String(36),nullable=True)
        batch.add_column(sa.Column('input_metadata',sa.JSON(),nullable=True))
        batch.add_column(sa.Column('result_metadata',sa.JSON(),nullable=True))


def downgrade():
    with op.batch_alter_table('project_page_drafts') as batch:
        batch.drop_column('result_metadata')
        batch.drop_column('input_metadata')
    # Provider-free trim history is retained; it cannot acquire a fictitious provider.
