"""Add competitor research workflow data.

Revision ID: 0003_competitor_research
Revises: 0002_prompt_site_nullable
Create Date: 2026-08-04
"""

from alembic import op


revision = "0003_competitor_research"
down_revision = "0002_prompt_site_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS collect_competitors BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS competitor_research_status VARCHAR(40) NOT NULL DEFAULT 'not_requested'")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS competitor_brief JSON")
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS competitor_brief_text TEXT")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS competitor_queries (
            id VARCHAR(36) PRIMARY KEY,
            content_item_id VARCHAR(36) NOT NULL REFERENCES content_items(id),
            query TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 1,
            status VARCHAR(40) NOT NULL DEFAULT 'draft',
            result_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_competitor_queries_content_item_id ON competitor_queries (content_item_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS competitor_results (
            id VARCHAR(36) PRIMARY KEY,
            content_item_id VARCHAR(36) NOT NULL REFERENCES content_items(id),
            query_id VARCHAR(36) REFERENCES competitor_queries(id),
            query_text TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            url TEXT NOT NULL,
            normalized_url TEXT NOT NULL,
            title TEXT,
            snippet TEXT,
            source_provider VARCHAR(80) NOT NULL DEFAULT 'dataforseo',
            status VARCHAR(40) NOT NULL DEFAULT 'discovered',
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_competitor_results_content_item_id ON competitor_results (content_item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_competitor_results_query_id ON competitor_results (query_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS competitor_pages (
            id VARCHAR(36) PRIMARY KEY,
            content_item_id VARCHAR(36) NOT NULL REFERENCES content_items(id),
            competitor_result_id VARCHAR(36) NOT NULL REFERENCES competitor_results(id),
            url TEXT NOT NULL,
            http_status INTEGER,
            title TEXT,
            h1 TEXT,
            meta_description TEXT,
            headings JSON DEFAULT '[]',
            text_content TEXT,
            tables JSON DEFAULT '[]',
            lists JSON DEFAULT '[]',
            faq JSON DEFAULT '[]',
            word_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            fetched_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_competitor_pages_content_item_id ON competitor_pages (content_item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_competitor_pages_competitor_result_id ON competitor_pages (competitor_result_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS competitor_pages")
    op.execute("DROP TABLE IF EXISTS competitor_results")
    op.execute("DROP TABLE IF EXISTS competitor_queries")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS competitor_brief_text")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS competitor_brief")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS competitor_research_status")
    op.execute("ALTER TABLE generation_tasks DROP COLUMN IF EXISTS collect_competitors")
