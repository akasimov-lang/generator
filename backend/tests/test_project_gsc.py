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


def test_saved_value_survives_session_reload_and_domain_changes_without_outbound_work(setup):
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
    assert db.scalar(select(models.BackgroundJob)) is None
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
