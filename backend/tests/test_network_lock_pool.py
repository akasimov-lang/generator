"""Nested advisory locks must fit a small Celery connection pool."""
from types import SimpleNamespace
import pytest
from app.project_network import network_lock, NetworkConflict


class Connection:
    def __init__(self):
        self.locks = []; self.closed = False; self.refuse = False
    def scalar(self, sql, args):
        if self.refuse: return False
        self.locks.append(args['key']); return True
    def execute(self, sql, args):
        assert self.locks.pop() == args['key']
    def close(self):
        assert not self.locks
        self.closed = True


class Pool:
    dialect = SimpleNamespace(name='postgresql')
    def __init__(self): self.connections = []
    def connect(self):
        assert not self.connections or self.connections[-1].closed, 'pool exhausted'
        connection = Connection(); self.connections.append(connection); return connection


def test_nested_keys_and_reentrant_lock_use_one_connection_and_release_on_error():
    db = SimpleNamespace(bind=Pool(), info={})
    with pytest.raises(ValueError, match='stop'):
        with network_lock(db, 'run'):
            with network_lock(db, 'domain-a'), network_lock(db, 'domain-b'), network_lock(db, 'site'):
                with network_lock(db, 'site'):
                    assert len(db.bind.connections) == 1
                    raise ValueError('stop')
    assert db.bind.connections[0].closed and not db.info
    with network_lock(db, 'next'):
        assert len(db.bind.connections) == 2


def test_conflict_does_not_release_outer_lock():
    db = SimpleNamespace(bind=Pool(), info={})
    with network_lock(db, 'outer'):
        connection = db.bind.connections[0]; connection.refuse = True
        with pytest.raises(NetworkConflict):
            with network_lock(db, 'busy'): pytest.fail('must not enter')
        assert len(connection.locks) == 1 and not connection.closed
    assert connection.closed and not db.info
