import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def load_migration(name):
    path = Path(__file__).parents[1] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_network_migrations_preserve_existing_sites_and_backfill_main():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sites (id VARCHAR(36) PRIMARY KEY, cache_canon TEXT, name TEXT)"))
        connection.execute(text("INSERT INTO sites VALUES ('site-1', 'https://MAIN.test/', 'keep-name')"))
        migrations = [load_migration(name) for name in ("0042_main_domain_history.py", "0043_network_operations.py")]
        with Operations.context(MigrationContext.configure(connection)):
            for migration in migrations: migration.upgrade()
            row = connection.execute(text("SELECT * FROM sites")).mappings().one()
            assert row["name"] == "keep-name"
            assert row["main_domain_history"] == '["main.test"]'
            assert row["x_default_history"] == '[]'
            assert row["network_state"] == '{}'
            assert "network_operations" in inspect(connection).get_table_names()
            for migration in reversed(migrations): migration.downgrade()
            assert connection.execute(text("SELECT name FROM sites")).scalar() == "keep-name"
