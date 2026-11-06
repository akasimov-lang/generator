from types import SimpleNamespace
from unittest.mock import Mock

from app import db, worker_connections


def test_threaded_planning_keeps_shared_connection_limit(monkeypatch):
    engine = SimpleNamespace(dialect=SimpleNamespace(name='postgresql'), dispose=Mock())
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setenv('WORKER_SHARED_DB_POOL', '1')
    worker_connections.release_idle_pool()
    engine.dispose.assert_not_called()


def test_prefork_worker_releases_idle_connections(monkeypatch):
    engine = SimpleNamespace(dialect=SimpleNamespace(name='postgresql'), dispose=Mock())
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.delenv('WORKER_SHARED_DB_POOL', raising=False)
    worker_connections.release_idle_pool()
    engine.dispose.assert_called_once_with()


def test_prefork_child_does_not_close_inherited_parent_connections(monkeypatch):
    engine = SimpleNamespace(dialect=SimpleNamespace(name='postgresql'), dispose=Mock())
    monkeypatch.setattr(db, 'engine', engine)
    worker_connections.reset_inherited_pool()
    engine.dispose.assert_called_once_with(close=False)
