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
