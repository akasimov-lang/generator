from collections.abc import Generator

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    apply_lightweight_migrations()
    ensure_default_admin()


def apply_lightweight_migrations() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "sites" in tables:
        columns = {column["name"] for column in inspector.get_columns("sites")}
        site_columns = {
            "payload_mode": "VARCHAR(40) DEFAULT 'simple_page' NOT NULL",
            "editor_version": "VARCHAR(40) DEFAULT '2.31.0' NOT NULL",
            "default_menu": "JSON DEFAULT '{\"header\":[],\"footer\":[]}'",
            "menu_library": "JSON DEFAULT '[]'",
            "default_banners": "JSON DEFAULT '[]'",
            "showcase_payload": "JSON",
            "default_prompt_template_id": "VARCHAR(36)",
            "external_project_id": "VARCHAR(200)",
            "cache_canon": "TEXT",
            "cache_language": "VARCHAR(40)",
            "cache_geo": "VARCHAR(40)",
            "homepage_title": "TEXT",
            "internal_pages_count": "INTEGER DEFAULT 0 NOT NULL",
            "domains_count": "INTEGER DEFAULT 0 NOT NULL",
            "cache_domains": "JSON DEFAULT '[]'",
            "cache_server_ip": "VARCHAR(120)",
            "project_status": "VARCHAR(32) DEFAULT 'working' NOT NULL",
            "is_test_project": "BOOLEAN DEFAULT FALSE NOT NULL",
            "has_menu": "BOOLEAN DEFAULT FALSE NOT NULL",
            "cache_synced_at": "TIMESTAMP WITH TIME ZONE",
            "menu_capabilities_checked_at": "TIMESTAMP WITH TIME ZONE",
            "header_menu_template_rendered": "BOOLEAN",
            "header_menu_rendered": "BOOLEAN",
            "header_menu_nested": "BOOLEAN",
            "footer_menu_template_rendered": "BOOLEAN",
            "footer_menu_rendered": "BOOLEAN",
            "footer_menu_nested": "BOOLEAN",
        }
        _add_missing_columns("sites", columns, site_columns)

    if "sections" in tables:
        columns = {column["name"] for column in inspector.get_columns("sections")}
        _add_missing_columns(
            "sections",
            columns,
            {
                "menu_type": "VARCHAR(20) DEFAULT 'header' NOT NULL",
                "sync_status": "VARCHAR(20) DEFAULT 'pending' NOT NULL",
                "synced_at": "TIMESTAMP WITH TIME ZONE",
                "parent_id": "VARCHAR(36)",
                "is_temporary_parent": "BOOLEAN DEFAULT FALSE NOT NULL",
            },
        )

    if "ai_providers" in tables:
        columns = {column["name"] for column in inspector.get_columns("ai_providers")}
        provider_columns = {
            "provider_type": "VARCHAR(40) DEFAULT 'custom' NOT NULL",
            "prompt_tokens_used": "INTEGER DEFAULT 0 NOT NULL",
            "completion_tokens_used": "INTEGER DEFAULT 0 NOT NULL",
            "total_tokens_used": "INTEGER DEFAULT 0 NOT NULL",
            "last_used_at": "TIMESTAMP WITH TIME ZONE",
            "validation_status": "VARCHAR(40) DEFAULT 'unchecked' NOT NULL",
            "validation_message": "TEXT",
            "validated_at": "TIMESTAMP WITH TIME ZONE",
        }
        _add_missing_columns("ai_providers", columns, provider_columns)

    if "generation_tasks" in tables:
        columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
        _add_missing_columns(
            "generation_tasks",
            columns,
            {
                "created_by_user_id": "VARCHAR(36)",
                "payload_mode": "VARCHAR(40) DEFAULT 'site_default' NOT NULL",
                "target_words": "INTEGER",
                "prompt_template_name": "VARCHAR(160)",
                "prompt_template": "TEXT",
                "include_toc": "BOOLEAN DEFAULT TRUE NOT NULL",
                "include_faq": "BOOLEAN DEFAULT TRUE NOT NULL",
                "generate_title": "BOOLEAN DEFAULT FALSE NOT NULL",
                "collect_competitors": "BOOLEAN DEFAULT FALSE NOT NULL",
                "include_casino_rating": "BOOLEAN DEFAULT FALSE NOT NULL",
                "archived_at": "TIMESTAMP WITH TIME ZONE",
                "archived_by_user_id": "VARCHAR(36)",
            },
        )

    if "content_items" in tables:
        columns = {column["name"] for column in inspector.get_columns("content_items")}
        _add_missing_columns(
            "content_items",
            columns,
            {
                "site_id": "VARCHAR(36)",
                "publication_campaign_id": "VARCHAR(36)",
                "generation_prompt_name": "VARCHAR(160)",
                "include_casino_rating": "BOOLEAN DEFAULT FALSE NOT NULL",
                "generated_at": "TIMESTAMP WITH TIME ZONE",
                "generation_progress": "INTEGER DEFAULT 0 NOT NULL",
                "generation_error": "TEXT",
                "competitor_research_status": "VARCHAR(40) DEFAULT 'not_requested' NOT NULL",
                "competitor_research_progress": "INTEGER DEFAULT 0 NOT NULL",
                "competitor_research_error": "TEXT",
                "competitor_brief": "JSON",
                "competitor_brief_text": "TEXT",
                "section_content_mode": "VARCHAR(24) DEFAULT 'nested' NOT NULL",
                "section_source_slug": "VARCHAR(240)",
            },
        )
        backfill_content_site_ids()

    if "publication_campaigns" in tables:
        columns = {column["name"] for column in inspector.get_columns("publication_campaigns")}
        _add_missing_columns(
            "publication_campaigns",
            columns,
            {"completed_at": "TIMESTAMP WITH TIME ZONE"},
        )


def ensure_default_admin() -> None:
    from app import models
    from app.security import hash_password

    with SessionLocal() as db:
        settings = get_settings()
        admin = db.scalar(select(models.User).where(models.User.username == settings.admin_username))
        active_admin = db.scalar(select(models.User).where(models.User.is_admin.is_(True), models.User.is_active.is_(True)).limit(1))

        if active_admin:
            return

        if not admin:
            admin = models.User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
                is_active=True,
            )
            db.add(admin)
        else:
            admin.is_admin = True
            admin.is_active = True
            if not admin.password_hash:
                admin.password_hash = hash_password(settings.admin_password)
        db.commit()


def backfill_content_site_ids() -> None:
    statement = text(
        """
        UPDATE content_items
        SET site_id = generation_tasks.site_id
        FROM generation_tasks
        WHERE content_items.task_id = generation_tasks.id
          AND content_items.site_id IS NULL
          AND generation_tasks.site_id IS NOT NULL
        """
    )
    with engine.begin() as connection:
        connection.execute(statement)


def _add_missing_columns(table: str, existing_columns: set[str], columns: dict[str, str]) -> None:
    statements = [
        text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")
        for column_name, column_type in columns.items()
        if column_name not in existing_columns
    ]
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(statement)
