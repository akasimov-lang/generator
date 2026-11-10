from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.fibery_tasks import feed
from app.dashboard_activity import router
from app.security import require_auth

AT = datetime(2026, 11, 10, 9, tzinfo=timezone.utc)
USER = {'username': 'anton', 'allowed_site_ids': None}
URL = 'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Tasks/'


@pytest.fixture
def env():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='ionickiss.pl', base_url='https://ionickiss.pl', publication_endpoint='/', fibery_name='#254_Общие ключи_PL', cache_canon='current.test')
        other = models.Site(name='other.test', base_url='https://other.test', publication_endpoint='/', fibery_name='#626_Other_CZ')
        db.add_all([site, other]); db.commit()
        yield db, site, other
    engine.dispose()


def job(db, site, number='33313', minutes=0, status='completed'):
    at = AT + timedelta(minutes=minutes)
    row = models.BackgroundJob(id=str(uuid4()), kind='fibery_reglue', status=status,
        payload={'site_id': site.id, 'title': 'Переклей: old.test → new.test', 'due_at': (at + timedelta(minutes=3)).isoformat()},
        result={'task': {'public_id': number, 'title': 'Переклей: old.test → new.test', 'project_number': '254', 'url': URL + number}, 'verified_at': at.isoformat()} if status == 'completed' else {},
        created_at=at, updated_at=at, finished_at=at if status == 'completed' else None)
    db.add(row); db.commit()
    return row


def legacy(db, key='earlier', title='Ionickiss: витрина', minutes=0):
    at = AT + timedelta(minutes=minutes)
    row = models.AutoReglueConfig(key=key, value={'fibery_task': {
        'fibery/public-id': '33302', 'Alfasearch Config/Name': title, 'verified_at': at.isoformat(),
        'Alfasearch Config/SEO Project': {'fibery/public-id': '254'}, 'url': URL + '33302'}}, created_at=at, updated_at=at)
    db.add(row); db.commit()
    return row


def test_existing_seo_task_updates_are_deduplicated_with_latest_title(env):
    db, site, _ = env
    legacy(db)
    legacy(db, 'later', 'Ionickiss: витрина и ссылки', minutes=10)
    job(db, site, minutes=20)
    result = feed(db, USER)
    assert result['total'] == 2
    old = result['items'][1]
    assert old['number'] == '33302' and old['title'] == 'Ionickiss: витрина и ссылки'
    assert old['at'] == AT.isoformat()
    assert old['projects'][0]['id'] == site.id


def test_pending_and_failed_jobs_are_not_counted_as_created_tasks(env):
    db, site, _ = env
    job(db, site, status='queued')
    bad = job(db, site, status='failed'); bad.error = 'Ошибка связи'; db.commit()
    result = feed(db, USER)
    assert result['total'] == 0 and not result['items']
    assert {row['status'] for row in result['pending']} == {'collecting', 'error'}
    assert all('url' not in row for row in result['pending'])


def test_restricted_user_sees_only_own_project_tasks_and_no_legacy_leak(env):
    db, site, other = env
    legacy(db); job(db, site); job(db, other, '33312'); job(db, site, status='queued')
    result = feed(db, {**USER, 'allowed_site_ids': [other.id]})
    assert [row['number'] for row in result['items']] == ['33312']
    assert result['items'][0]['projects'][0]['id'] == other.id
    assert not result['pending']


def test_empty_permission_scope_does_not_expose_counts_or_tasks(env):
    db, site, _ = env
    legacy(db); job(db, site); job(db, site, status='queued')
    result = feed(db, {**USER, 'allowed_site_ids': []})
    assert result['total'] == 0 and not result['items'] and not result['pending']


def test_cursor_keeps_same_timestamp_tasks_and_incoming_rows_without_duplicates(env):
    db, site, _ = env
    job(db, site, '101'); job(db, site, '102'); job(db, site, '103')
    first = feed(db, USER, limit=2)
    assert [r['number'] for r in first['items']] == ['103', '102']
    job(db, site, '104', minutes=1)
    second = feed(db, USER, before=first['next_before'], limit=2)
    assert [r['number'] for r in second['items']] == ['101']
    assert second['total'] == 4 and second['next_before'] is None


def test_search_by_fibery_project_name_and_current_domain(env):
    db, site, _ = env
    job(db, site)
    assert feed(db, USER, query='ОБЩИЕ КЛЮЧИ')['total'] == 1
    assert feed(db, USER, query='current.test')['total'] == 1
    assert feed(db, USER, query='absent')['total'] == 0


def test_search_by_task_number_with_hash(env):
    db, site, _ = env
    job(db, site)
    assert feed(db, USER, query='#33313')['total'] == 1


def test_untrusted_saved_links_are_not_exposed_as_fibery_tasks(env):
    db, site, _ = env
    row = job(db, site)
    row.result = {'task': {'public_id': '33313', 'url': 'https://untrusted.test/33313'}}
    db.commit()
    assert feed(db, USER)['total'] == 0


def test_unknown_legacy_project_is_kept_for_admin_without_guessing_site(env):
    db, _, _ = env
    row = legacy(db)
    row.value = {'fibery_task': {**row.value['fibery_task'], 'Alfasearch Config/SEO Project': {'fibery/public-id': '999'}}}
    db.commit()
    item, = feed(db, USER)['items']
    assert not item['projects'] and item['fibery_project_url'].endswith('/999')


def test_legacy_binary_backups_do_not_hide_task_receipts(env):
    db, _, _ = env
    row = legacy(db)
    row.value = {**row.value, 'before': {'shortcodes': [{'name': '.DS_Store', 'data': '\x00binary'}]}}
    db.add(models.AutoReglueConfig(key='unrelated-backup', value={'before': {'data': '\x00binary'}}))
    db.commit()
    item, = feed(db, USER)['items']
    assert item['number'] == '33302'
    assert 'before' not in item and 'binary' not in str(item)


def test_http_collection_requires_auth_and_validates_pagination(env):
    db, site, _ = env
    job(db, site)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get('/dashboard-activity/fibery-tasks').status_code == 401
    app.dependency_overrides[require_auth] = lambda: USER
    response = client.get('/dashboard-activity/fibery-tasks?q=33313')
    assert response.status_code == 200 and response.json()['total'] == 1
    assert client.get('/dashboard-activity/fibery-tasks?limit=0').status_code == 422
