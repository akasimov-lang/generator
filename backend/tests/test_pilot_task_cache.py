from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models, pilot_task_cache as cache
from app.db import Base


def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    return Session(engine)


def test_saved_list_survives_new_sessions_and_skips_full_report_build(monkeypatch):
    with session() as db:
        calls = []
        def build(*args, **kwargs):
            calls.append(1); return {'items': [{'id': 'plan', 'created_at': datetime.now(timezone.utc)}], 'total': 1, 'has_more': False}
        monkeypatch.setattr('app.auto_pilot.tasks', build)
        cache.tasks(db, {'username': 'anton'})
        db.expunge_all()
        assert cache.tasks(db, {'username': 'anton'})['items'][0]['id'] == 'plan'
        assert len(calls) == 1


def test_cache_separates_users_permissions_search_and_pagination(monkeypatch):
    with session() as db:
        calls = []
        def build(db, user, offset, limit, q=''):
            calls.append(1); return {'items': [], 'total': len(calls), 'has_more': False}
        monkeypatch.setattr('app.auto_pilot.tasks', build)
        assert cache.tasks(db, {'username': 'anton'})['total'] == 1
        assert cache.tasks(db, {'username': 'other'})['total'] == 2
        assert cache.tasks(db, {'username': 'anton', 'allowed_site_ids': []})['total'] == 3
        assert cache.tasks(db, {'username': 'anton'}, q='Lemon')['total'] == 4
        assert cache.tasks(db, {'username': 'anton'}, offset=50)['total'] == 5
        assert cache.tasks(db, {'username': 'anton'})['total'] == 1


def test_child_status_change_invalidates_list(monkeypatch):
    with session() as db:
        child = models.BackgroundJob(kind='pilot_text', status='queued', payload={})
        db.add(child); db.commit()
        monkeypatch.setattr('app.auto_pilot.tasks', lambda *a, **k: {'items': [], 'status': child.status})
        assert cache.tasks(db, {'username': 'anton'})['status'] == 'queued'
        child.status='completed'; db.commit()
        assert cache.tasks(db, {'username': 'anton'})['status'] == 'completed'


def test_deletion_marker_invalidates_list(monkeypatch):
    with session() as db:
        calls = []
        monkeypatch.setattr('app.auto_pilot.tasks', lambda *a, **k: calls.append(1) or {'items': []})
        cache.tasks(db, {'username': 'anton'})
        db.add(models.AutoReglueConfig(key='pilot-cancel:deleted', value={'deleted': True})); db.commit()
        cache.tasks(db, {'username': 'anton'})
        assert len(calls) == 2


def test_manual_refresh_rebuilds_unchanged_snapshot(monkeypatch):
    with session() as db:
        calls = []
        monkeypatch.setattr('app.auto_pilot.tasks', lambda *a, **k: calls.append(1) or {'items': []})
        cache.tasks(db, {'username': 'anton'})
        cache.tasks(db, {'username': 'anton'}, refresh=True)
        assert len(calls) == 2
