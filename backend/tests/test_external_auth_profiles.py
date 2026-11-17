"""Webdev authentication must not depend on retired local credentials/profile spelling."""
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import external_auth, models
from app.api import router
from app.db import Base, get_db


@pytest.fixture
def profile_api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(router, prefix='/api')

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    external_auth._cache.clear()
    with TestClient(app) as client:
        yield client, engine
    external_auth._cache.clear()
    engine.dispose()


def webdev(monkeypatch, username, *, login_status=200, token_status=200):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == '/auth/login':
            assert json.loads(request.content) == {'username': username, 'pass': 'webdev-secret'}
            assert request.headers['Origin'] == 'https://ai-seo-content-panel.site'
            return httpx.Response(login_status, json={'token': 'verified-webdev-token'} if login_status == 200 else {'message': 'Invalid credentials'})
        assert request.url.path == '/auth/me'
        assert request.headers['Authorization'] == 'Bearer verified-webdev-token'
        return httpx.Response(token_status, json={'username': username})

    original = httpx.Client
    monkeypatch.setattr(external_auth.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    return requests


def seed(engine, username, *, active=False):
    with Session(engine) as db:
        user = models.User(username=username, password_hash='obsolete-local-hash',
                           is_admin=False, is_active=active, favorite_site_ids=['kept-favorite'])
        db.add(user)
        db.flush()
        db.add(models.GenerationTask(title='Historical task', geo='DE', language='de', created_by_user_id=user.id))
        db.commit()
        return user.id


@pytest.mark.parametrize('old_name,verified_name', [('Nina', 'nina'), ('Ekaterina', 'ekaterina'), (' Roman ', 'roman')])
def test_verified_login_reuses_retired_profile_and_preserves_history(profile_api, monkeypatch, old_name, verified_name):
    client, engine = profile_api
    old_id = seed(engine, old_name)
    requests = webdev(monkeypatch, verified_name)
    response = client.post('/api/auth/login', json={'username': verified_name, 'password': 'webdev-secret'})
    assert response.status_code == 200, response.text
    assert response.json()['user']['id'] == old_id
    client.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
    assert client.get('/api/auth/me').json()['username'] == verified_name
    assert client.get('/api/me/favorite-sites').json()['site_ids'] == ['kept-favorite']
    with Session(engine) as db:
        users = db.scalars(select(models.User)).all()
        assert len(users) == 1
        user = users[0]
        assert user.id == old_id and user.username == verified_name
        assert user.is_active and user.is_admin and user.password_hash == ''
        assert db.scalar(select(models.GenerationTask.created_by_user_id)) == old_id
    assert [r.url.path for r in requests[:2]] == ['/auth/login', '/auth/me']


def test_existing_exact_profile_takes_priority_over_legacy_case_variant(profile_api, monkeypatch):
    client, engine = profile_api
    legacy_id = seed(engine, 'Nina')
    current_id = seed(engine, 'nina', active=True)
    webdev(monkeypatch, 'nina')
    response = client.post('/api/auth/login', json={'username': 'nina', 'password': 'webdev-secret'})
    assert response.status_code == 200
    assert response.json()['user']['id'] == current_id
    with Session(engine) as db:
        assert db.get(models.User, legacy_id).username == 'Nina'
        assert not db.get(models.User, legacy_id).is_active


def test_distinct_active_profile_is_not_merged_by_case(profile_api, monkeypatch):
    client, engine = profile_api
    active_id = seed(engine, 'Nina', active=True)
    webdev(monkeypatch, 'nina')
    response = client.post('/api/auth/login', json={'username': 'nina', 'password': 'webdev-secret'})
    assert response.status_code == 200
    assert response.json()['user']['id'] != active_id
    with Session(engine) as db:
        assert db.get(models.User, active_id).username == 'Nina'


def test_ambiguous_retired_profiles_do_not_block_verified_login(profile_api, monkeypatch):
    client, engine = profile_api
    first = seed(engine, 'Nina')
    second = seed(engine, 'NINA')
    webdev(monkeypatch, 'nina')
    response = client.post('/api/auth/login', json={'username': 'nina', 'password': 'webdev-secret'})
    assert response.status_code == 200
    assert response.json()['user']['id'] not in {first, second}


def test_unrelated_local_login_does_not_block_new_webdev_user(profile_api, monkeypatch):
    client, engine = profile_api
    old_id = seed(engine, 'Unrelated local display name')
    webdev(monkeypatch, 'nina')
    response = client.post('/api/auth/login', json={'username': 'nina', 'password': 'webdev-secret'})
    assert response.status_code == 200
    assert response.json()['user']['id'] != old_id


def test_rejected_password_does_not_touch_legacy_profile_or_log_secrets(profile_api, monkeypatch, caplog):
    client, engine = profile_api
    old_id = seed(engine, 'Nina')
    requests = webdev(monkeypatch, 'nina', login_status=401)
    response = client.post('/api/auth/login', json={'username': 'nina', 'password': 'webdev-secret'})
    assert response.status_code == 401
    assert response.json() == {'message': 'Invalid credentials'}
    assert len(requests) == 1
    with Session(engine) as db:
        user = db.get(models.User, old_id)
        assert user.username == 'Nina' and not user.is_active
        assert user.password_hash == 'obsolete-local-hash'
    assert "Webdev login rejected username='nina' status=401" in caplog.text
    assert 'webdev-secret' not in caplog.text
    assert 'verified-webdev-token' not in caplog.text


def test_rejected_token_does_not_update_local_profile(profile_api, monkeypatch, caplog):
    client, engine = profile_api
    old_id = seed(engine, 'Nina')
    requests = webdev(monkeypatch, 'nina', token_status=401)
    response = client.post('/api/auth/login', json={'username': 'nina', 'password': 'webdev-secret'})
    assert response.status_code == 401
    assert len(requests) == 4
    with Session(engine) as db:
        assert db.get(models.User, old_id).username == 'Nina'
        assert not db.get(models.User, old_id).is_active
    assert "Webdev token verification failed username='nina' status=401 attempt=2" in caplog.text
    assert 'webdev-secret' not in caplog.text
    assert 'verified-webdev-token' not in caplog.text
