"""Baseline the current application schema.

Revision ID: 0001_current_schema
Revises:
Create Date: 2026-07-14
"""

from alembic import op


revision = "0001_current_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(36) PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN,
            is_active BOOLEAN,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_providers (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            provider_type VARCHAR(40) NOT NULL DEFAULT 'custom',
            endpoint_url TEXT NOT NULL,
            model VARCHAR(120) NOT NULL DEFAULT 'default',
            api_key TEXT,
            prompt_tokens_used INTEGER NOT NULL DEFAULT 0,
            completion_tokens_used INTEGER NOT NULL DEFAULT 0,
            total_tokens_used INTEGER NOT NULL DEFAULT 0,
            last_used_at TIMESTAMP WITH TIME ZONE,
            validation_status VARCHAR(40) NOT NULL DEFAULT 'unchecked',
            validation_message TEXT,
            validated_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sites (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(160) NOT NULL,
            base_url TEXT NOT NULL,
            publication_endpoint TEXT NOT NULL,
            sections_endpoint TEXT,
            api_token TEXT,
            payload_mode VARCHAR(40) NOT NULL DEFAULT 'simple_page',
            editor_version VARCHAR(40) NOT NULL DEFAULT '2.31.0',
            default_menu JSON DEFAULT '{"header":[],"footer":[]}',
            default_banners JSON DEFAULT '[]',
            showcase_payload JSON,
            default_prompt_template_id VARCHAR(36),
            is_active BOOLEAN,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sections (
            id VARCHAR(36) PRIMARY KEY,
            site_id VARCHAR(36) NOT NULL REFERENCES sites(id),
            external_id VARCHAR(160) NOT NULL,
            name VARCHAR(160) NOT NULL,
            path VARCHAR(240) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id VARCHAR(36) PRIMARY KEY,
            site_id VARCHAR(36) REFERENCES sites(id),
            name VARCHAR(160) NOT NULL,
            content TEXT NOT NULL,
            is_default BOOLEAN,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_tasks (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(180) NOT NULL,
            site_id VARCHAR(36) REFERENCES sites(id),
            section_id VARCHAR(36) REFERENCES sections(id),
            ai_provider_id VARCHAR(36) REFERENCES ai_providers(id),
            geo VARCHAR(20) NOT NULL,
            language VARCHAR(20) NOT NULL,
            status VARCHAR(40),
            payload_mode VARCHAR(40) NOT NULL DEFAULT 'site_default',
            topics_count INTEGER,
            target_words INTEGER,
            prompt_template_name VARCHAR(160),
            prompt_template TEXT,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_items (
            id VARCHAR(36) PRIMARY KEY,
            task_id VARCHAR(36) NOT NULL REFERENCES generation_tasks(id),
            site_id VARCHAR(36) REFERENCES sites(id),
            topic TEXT NOT NULL,
            slug VARCHAR(240) NOT NULL,
            generated_json JSON NOT NULL,
            status VARCHAR(40),
            word_count INTEGER,
            section_id VARCHAR(160),
            generation_prompt_name VARCHAR(160),
            generated_at TIMESTAMP WITH TIME ZONE,
            idempotency_key VARCHAR(240) NOT NULL UNIQUE,
            scheduled_at TIMESTAMP WITH TIME ZONE,
            published_at TIMESTAMP WITH TIME ZONE,
            published_url TEXT,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_campaigns (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(180) NOT NULL,
            site_id VARCHAR(36) NOT NULL REFERENCES sites(id),
            status VARCHAR(40),
            interval_minutes INTEGER,
            items_per_run INTEGER,
            start_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_logs (
            id VARCHAR(36) PRIMARY KEY,
            content_item_id VARCHAR(36) REFERENCES content_items(id),
            endpoint_url TEXT NOT NULL,
            request_payload JSON,
            response_status INTEGER,
            response_body JSON,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    _add_column_if_missing("sites", "payload_mode VARCHAR(40) NOT NULL DEFAULT 'simple_page'")
    _add_column_if_missing("sites", "editor_version VARCHAR(40) NOT NULL DEFAULT '2.31.0'")
    _add_column_if_missing("sites", """default_menu JSON DEFAULT '{"header":[],"footer":[]}'""")
    _add_column_if_missing("sites", "default_banners JSON DEFAULT '[]'")
    _add_column_if_missing("sites", "showcase_payload JSON")
    _add_column_if_missing("sites", "default_prompt_template_id VARCHAR(36)")

    _add_column_if_missing("ai_providers", "provider_type VARCHAR(40) NOT NULL DEFAULT 'custom'")
    _add_column_if_missing("ai_providers", "prompt_tokens_used INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing("ai_providers", "completion_tokens_used INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing("ai_providers", "total_tokens_used INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing("ai_providers", "last_used_at TIMESTAMP WITH TIME ZONE")
    _add_column_if_missing("ai_providers", "validation_status VARCHAR(40) NOT NULL DEFAULT 'unchecked'")
    _add_column_if_missing("ai_providers", "validation_message TEXT")
    _add_column_if_missing("ai_providers", "validated_at TIMESTAMP WITH TIME ZONE")

    _add_column_if_missing("generation_tasks", "payload_mode VARCHAR(40) NOT NULL DEFAULT 'site_default'")
    _add_column_if_missing("generation_tasks", "target_words INTEGER")
    _add_column_if_missing("generation_tasks", "prompt_template_name VARCHAR(160)")
    _add_column_if_missing("generation_tasks", "prompt_template TEXT")

    _add_column_if_missing("content_items", "site_id VARCHAR(36)")
    _add_column_if_missing("content_items", "generation_prompt_name VARCHAR(160)")
    _add_column_if_missing("content_items", "generated_at TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    # Baseline migrations intentionally do not drop production tables.
    pass


def _add_column_if_missing(table_name: str, column_sql: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_sql}")
