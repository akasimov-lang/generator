from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from zoneinfo import ZoneInfo

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, create_engine, insert, select


def test_entry_date_backfill_preserves_real_timestamps_and_falls_back_only_when_unknown():
    path = Path(__file__).parents[1] / 'migrations/versions/0062_site_added_to_system.py'
    spec = importlib.util.spec_from_file_location('site_added_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    original = [datetime(2026, 10, 17, 20, 59), datetime(2026, 10, 17, 21),
                datetime(2026, 10, 18, 20, 59), datetime(2026, 10, 18, 21), None]
    with engine.begin() as connection:
        sites = Table('sites', MetaData(), Column('id', Integer, primary_key=True), Column('created_at', DateTime()))
        sites.create(connection)
        connection.execute(insert(sites), [{'id': i, 'created_at': value} for i, value in enumerate(original)])
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        updated = Table('sites', MetaData(), autoload_with=connection)
        rows = connection.execute(select(updated).order_by(updated.c.id)).mappings().all()
        dates = [row['added_to_system_at'].replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Moscow')).date().isoformat() for row in rows]
        assert dates == ['2026-10-17', '2026-10-18', '2026-10-18', '2026-10-19', '2026-09-01']
        assert [row['created_at'] for row in rows] == original
        connection.execute(insert(updated).values(id=10, created_at=datetime.now(timezone.utc)))
        added = connection.scalar(select(updated.c.added_to_system_at).where(updated.c.id == 10))
        assert abs((added.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()) < 5
