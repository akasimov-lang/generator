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
        def build(db, user, offset, limit, q='', group='all'):
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


def test_cache_key_fits_production_column_without_weakening_scope():
    user={'username':'a'*300,'allowed_site_ids':['s'*100]*100}
    assert len(cache.key(user,0,50,'q'*200)) <= models.AutoReglueConfig.__table__.c.key.type.length


def test_cache_storage_failure_keeps_list_available(monkeypatch):
    from sqlalchemy.exc import OperationalError
    with session() as db:
        monkeypatch.setattr('app.auto_pilot.tasks',lambda *a,**k:{'items':[{'id':'visible'}],'total':1})
        def unavailable(self):raise OperationalError('cache commit',{},Exception('unavailable'))
        monkeypatch.setattr(Session,'commit',unavailable)
        assert cache.tasks(db,{'username':'anton'})['items']==[{'id':'visible'}]


def test_site_cache_timestamp_refresh_does_not_rebuild_report_list(monkeypatch):
    with session() as db:
        site=models.Site(name='example.test',base_url='https://example.test',publication_endpoint='/publish',brand='Lemon',cache_geo='PL')
        db.add(site);db.commit();calls=[]
        monkeypatch.setattr('app.auto_pilot.tasks',lambda *a,**k:calls.append(1) or {'items':[]})
        cache.tasks(db,{'username':'anton'})
        site.cache_synced_at=datetime.now(timezone.utc);site.homepage_title='Refreshed';db.commit()
        cache.tasks(db,{'username':'anton'})
        assert len(calls)==1


def test_search_cache_tracks_brand_and_domain_changes_but_not_polling(monkeypatch):
    with session() as db:
        site=models.Site(name='example.test',base_url='https://example.test',publication_endpoint='/publish',brand='Lemon',cache_geo='PL',cache_domains=[{'domain':'old.test','status':'active'}])
        db.add(site);db.commit();calls=[]
        monkeypatch.setattr('app.auto_pilot.tasks',lambda *a,**k:calls.append(1) or {'items':[]})
        cache.tasks(db,{'username':'anton'},q='Lemon')
        site.cache_synced_at=datetime.now(timezone.utc);db.commit()
        cache.tasks(db,{'username':'anton'},q='Lemon');assert len(calls)==1
        site.brand='Pelican';db.commit()
        cache.tasks(db,{'username':'anton'},q='Lemon');assert len(calls)==2
        site.cache_domains=[{'domain':'new.test','status':'active'}];db.commit()
        cache.tasks(db,{'username':'anton'},q='Lemon');assert len(calls)==3
