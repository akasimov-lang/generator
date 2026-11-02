import importlib.util
from pathlib import Path
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_knowledge_migration_preserves_existing_rows_and_enforces_scope_uniqueness():
    engine = sa.create_engine('sqlite://')
    meta = sa.MetaData()
    users = sa.Table('users', meta, sa.Column('id', sa.String(36), primary_key=True))
    meta.create_all(engine)
    spec = importlib.util.spec_from_file_location('migration', Path(__file__).resolve().parents[1] / 'migrations/versions/0064_template_knowledge.py')
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    with engine.begin() as connection:
        connection.execute(users.insert().values(id='existing-user'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(sa.text('SELECT id FROM users')).scalar() == 'existing-user'
        inspector = sa.inspect(connection)
        assert {c['name'] for c in inspector.get_columns('template_knowledge_examples')} >= {'html', 'structure', 'geo', 'brand_key'}
        assert inspector.get_unique_constraints('template_knowledge_examples')[0]['column_names'] == ['brand_key', 'geo', 'sha256']
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(sa.text('SELECT id FROM users')).scalar() == 'existing-user'
