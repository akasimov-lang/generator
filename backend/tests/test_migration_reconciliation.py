import importlib.util
from pathlib import Path
import sys

import pytest
import sqlalchemy as sa

spec = importlib.util.spec_from_file_location('reconcile', Path(__file__).resolve().parents[1] / 'scripts' / 'reconcile_production_migrations.py')
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


@pytest.fixture
def ledger(monkeypatch):
    engine = sa.create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(sa.text('CREATE TABLE alembic_version(version_num VARCHAR(64) NOT NULL)'))
        c.execute(sa.text("INSERT INTO alembic_version VALUES ('0064_template_knowledge')"))
    monkeypatch.setattr(reconcile, 'engine', engine)
    monkeypatch.setattr(reconcile, 'verify', lambda *_: None)
    yield engine
    engine.dispose()


def revision(engine):
    with engine.connect() as c:
        return c.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one()


def test_dry_run_does_not_change_ledger(ledger, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['reconcile'])
    reconcile.main()
    assert revision(ledger) == '0064_template_knowledge'


def test_apply_aligns_only_ledger_after_verification(ledger, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['reconcile', '--apply'])
    reconcile.main()
    assert revision(ledger) == '0069_archived_content_urls'
    assert sa.inspect(ledger).get_table_names() == ['alembic_version']


def test_failed_schema_verification_prevents_stamp(ledger, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['reconcile', '--apply'])
    def reject(*_):
        raise RuntimeError('schema differs')
    monkeypatch.setattr(reconcile, 'verify', reject)
    with pytest.raises(RuntimeError, match='schema differs'):
        reconcile.main()
    assert revision(ledger) == '0064_template_knowledge'


def test_unknown_revision_is_not_overwritten(ledger, monkeypatch):
    with ledger.begin() as c:
        c.execute(sa.text("UPDATE alembic_version SET version_num='unexpected'"))
    monkeypatch.setattr(sys, 'argv', ['reconcile', '--apply'])
    with pytest.raises(RuntimeError, match='Unexpected migration revision'):
        reconcile.main()
    assert revision(ledger) == 'unexpected'


def test_column_type_difference_is_rejected(ledger):
    with pytest.raises(RuntimeError, match='type differs'):
        reconcile.check_column({'type': sa.Integer(), 'nullable': False}, sa.Column('value', sa.Boolean(), nullable=False), ledger.dialect, 'test')


def test_column_nullability_difference_is_rejected(ledger):
    with pytest.raises(RuntimeError, match='nullability differs'):
        reconcile.check_column({'type': sa.Boolean(), 'nullable': True}, sa.Column('value', sa.Boolean(), nullable=False), ledger.dialect, 'test')


def test_column_default_difference_is_rejected(ledger):
    with pytest.raises(RuntimeError, match='server default differs'):
        reconcile.check_column({'type': sa.Boolean(), 'nullable': False, 'default': 'true'}, sa.Column('value', sa.Boolean(), nullable=False, server_default='false'), ledger.dialect, 'test')
