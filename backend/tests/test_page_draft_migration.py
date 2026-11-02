import importlib.util
from pathlib import Path
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_metadata_migration_preserves_old_drafts_and_allows_provider_free_drafts():
    engine=sa.create_engine('sqlite://')
    meta=sa.MetaData()
    table=sa.Table('project_page_drafts',meta,sa.Column('id',sa.String(36),primary_key=True),sa.Column('provider_id',sa.String(36),nullable=False))
    meta.create_all(engine)
    spec=importlib.util.spec_from_file_location('migration',Path(__file__).resolve().parents[1]/'migrations/versions/0063_page_draft_metadata.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with engine.begin() as connection:
        connection.execute(table.insert().values(id='old',provider_id='original-provider'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns={c['name']:c for c in sa.inspect(connection).get_columns('project_page_drafts')}
        assert columns['provider_id']['nullable']
        assert {'input_metadata','result_metadata'} <= columns.keys()
        assert connection.execute(sa.text("SELECT provider_id FROM project_page_drafts WHERE id='old'")).scalar()=='original-provider'
        connection.execute(sa.text("INSERT INTO project_page_drafts(id,provider_id) VALUES ('trim',NULL)"))
