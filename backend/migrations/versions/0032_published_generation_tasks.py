"""Mark fully published generation tasks as published.

Revision ID: 0032_published_tasks
Revises: 0031_unique_project_urls
Create Date: 2026-08-26
"""

from alembic import op


revision = "0032_published_tasks"
down_revision = "0031_unique_project_urls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE generation_tasks AS task
        SET status = 'published'
        WHERE EXISTS (
            SELECT 1
            FROM content_items AS published_item
            WHERE published_item.task_id = task.id
              AND published_item.status = 'published'
        )
          AND NOT EXISTS (
            SELECT 1
            FROM content_items AS remaining_item
            WHERE remaining_item.task_id = task.id
              AND remaining_item.status NOT IN ('published', 'deleted')
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE generation_tasks
        SET status = 'generated'
        WHERE status = 'published'
        """
    )
