"""Prevent duplicate page and menu URLs inside a project.

Revision ID: 0031_unique_project_urls
Revises: 0030_generate_title
Create Date: 2026-08-26
"""

from alembic import op


revision = "0031_unique_project_urls"
down_revision = "0030_generate_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the newest published owner of a URL. Older rows are historical and
    # cannot represent a second physical page on the same project URL.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY site_id, slug
                       ORDER BY
                           CASE WHEN status = 'published' THEN 0 ELSE 1 END,
                           created_at DESC,
                           id DESC
                   ) AS duplicate_rank
            FROM content_items
            WHERE site_id IS NOT NULL AND status <> 'deleted'
        )
        UPDATE content_items
        SET status = 'deleted',
            deletion_confirmed_at = COALESCE(deletion_confirmed_at, NOW()),
            deletion_error = NULL
        WHERE id IN (SELECT id FROM ranked WHERE duplicate_rank > 1)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_content_items_active_site_slug
        ON content_items (site_id, slug)
        WHERE site_id IS NOT NULL AND status <> 'deleted'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sections_site_menu_path
        ON sections (site_id, menu_type, path)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sections_site_menu_path")
    op.execute("DROP INDEX IF EXISTS uq_content_items_active_site_slug")
