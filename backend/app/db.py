from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
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


def apply_lightweight_migrations() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "sites" in tables:
        columns = {column["name"] for column in inspector.get_columns("sites")}
        site_columns = {
            "payload_mode": "VARCHAR(40) DEFAULT 'simple_page' NOT NULL",
            "editor_version": "VARCHAR(40) DEFAULT '2.31.0' NOT NULL",
            "default_menu": "JSON DEFAULT '{\"header\":[],\"footer\":[]}'",
            "default_banners": "JSON DEFAULT '[]'",
            "showcase_payload": "JSON",
        }
        _add_missing_columns("sites", columns, site_columns)

    if "generation_tasks" in tables:
        columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
        _add_missing_columns(
            "generation_tasks",
            columns,
            {"payload_mode": "VARCHAR(40) DEFAULT 'site_default' NOT NULL"},
        )


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
