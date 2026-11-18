import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.project_gsc import router, PREFIX
from app.security import require_auth


@pytest.fixture
def setup(monkeypatch):
    def no_external_requests(*args, **kwargs):
        pytest.fail('GSC must not make external HTTP requests')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', no_external_requests)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', no_external_requests)
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='first.test', base_url='https://first.test', publication_endpoint='/')
        other = models.Site(name='second.test', base_url='https://second.test', publication_endpoint='/')
        db.add_all([site, other]); db.commit()
        app = FastAPI(); app.include_router(router)
        user = {'id': 'user', 'username': 'editor', 'is_admin': False, 'allowed_site_ids': [site.id]}
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_auth] = lambda: user
        with TestClient(app) as client:
            yield db, site, other, client, user
    engine.dispose()


def test_saved_value_survives_reload_and_domain_changes_with_original_task_snapshot(setup):
    db, site, other, client, user = setup
    site_id = site.id
    url = f'/sites/{site_id}/gsc'
    assert client.get(url).json() == {'value': ''}
    original = dict(site.network_state or {})
    response = client.put(url, json={'value': 'Вручную: account@example.test'})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    site.name = 'renamed.test'; site.cache_canon = 'new-main.test'
    db.commit(); db.expunge_all()
    result = client.get(url)
    assert result.json() == {'value': 'Вручную: account@example.test'}
    assert result.headers['Cache-Control'] == 'no-store'
    assert db.get(models.Site, site_id).network_state == original
    job = db.scalar(select(models.BackgroundJob))
    assert job.kind == "gsc_fibery"
    assert job.payload["domain"] == "first.test"
    assert job.payload["value"] == "Вручную: account@example.test"
    assert db.scalar(select(models.NetworkOperation)) is None
    assert db.scalar(select(models.ProjectNotification)) is None


def test_each_project_keeps_its_own_value_and_supports_clearing(setup):
    db, site, other, client, user = setup
    user['allowed_site_ids'] = None
    first, second = f'/sites/{site.id}/gsc', f'/sites/{other.id}/gsc'
    client.put(first, json={'value': 'first account'})
    assert client.get(second).json() == {'value': ''}
    client.put(second, json={'value': 'second account'})
    assert client.put(first, json={'value': ''}).json() == {'value': ''}
    assert client.get(first).json() == {'value': ''}
    assert client.get(second).json() == {'value': 'second account'}
    assert len(db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.startswith(PREFIX))).all()) == 2


@pytest.mark.parametrize('method', ['get', 'put'])
def test_inaccessible_or_missing_project_cannot_be_read_or_written(setup, method):
    db, site, other, client, user = setup
    kwargs = {'json': {'value': 'private'}} if method == 'put' else {}
    assert getattr(client, method)(f'/sites/{other.id}/gsc', **kwargs).status_code == 404
    user['allowed_site_ids'] = None
    assert getattr(client, method)('/sites/missing/gsc', **kwargs).status_code == 404
    assert db.scalar(select(models.AutoReglueConfig)) is None


@pytest.mark.parametrize('payload', [{'value': 'x' * 2001}, {'value': 123}, {'value': None}, {'value': 'ok', 'publish': True}])
def test_invalid_input_does_not_replace_saved_value(setup, payload):
    db, site, other, client, user = setup
    url = f'/sites/{site.id}/gsc'
    client.put(url, json={'value': 'keep'})
    assert client.put(url, json=payload).status_code == 422
    assert client.get(url).json() == {'value': 'keep'}


def test_unauthenticated_request_is_rejected(setup):
    db, site, other, client, user = setup
    del client.app.dependency_overrides[require_auth]
    assert client.get(f'/sites/{site.id}/gsc').status_code == 401
    assert client.put(f'/sites/{site.id}/gsc', json={'value': 'no'}).status_code == 401


def test_nonempty_changes_queue_receipts_but_repeats_and_clearing_do_not(setup):
    db, site, other, client, user = setup
    site.cache_canon = 'www.current.test'; site.fibery_name = '#1715_Project'; db.commit()
    url = f'/sites/{site.id}/gsc'
    value = 'account@test.example google-site-verification=<a>```</a>'
    client.put(url, json={'value': value})
    first = db.scalar(select(models.BackgroundJob))
    assert first.payload['title'] == 'www.current.test - Добавлен в GSC'
    assert first.payload['project_number'] == '1715'
    assert first.payload['value'] == value and value in first.payload['description']
    assert '````text' in first.payload['description']
    client.put(url, json={'value': value})
    client.put(url, json={'value': '  '})
    client.put(url, json={'value': ''})
    client.put(url, json={'value': value})
    assert len(db.scalars(select(models.BackgroundJob)).all()) == 1
    client.put(url, json={'value': 'other account'})
    assert len(db.scalars(select(models.BackgroundJob)).all()) == 2


def test_existing_value_is_not_backfilled_on_read_or_unchanged_save(setup):
    db, site, _, client, _ = setup
    db.add(models.AutoReglueConfig(key=PREFIX + site.id, value={'value': 'legacy'})); db.commit()
    url = f'/sites/{site.id}/gsc'
    assert client.get(url).json() == {'value': 'legacy'}
    client.put(url, json={'value': 'legacy'})
    assert db.scalar(select(models.BackgroundJob)) is None
