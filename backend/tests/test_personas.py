import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models import AutoReglueConfig
from app.personas import PREFIX, SEED, PersonaInput, router, seed_catalog, word_count
from app.security import require_auth


@pytest.fixture
def setup():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_catalog(db)
        app = FastAPI(); app.include_router(router, prefix='/api')
        user = {'id': 'user', 'username': 'editor', 'is_admin': True, 'allowed_site_ids': []}
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_auth] = lambda: user
        with TestClient(app) as client:
            yield db, client, user
    engine.dispose()


def body():
    original = json.loads(SEED.read_text())[0]
    return {k: original[k] for k in PersonaInput.model_fields}


def test_seed_has_five_authors_per_geo_complete_bios_awards_and_local_portraits():
    rows = json.loads(SEED.read_text())
    assert len(rows) == len({r['id'] for r in rows}) == 25
    assert len({(r['first_name'], r['last_name']) for r in rows}) == 25
    assert Counter(r['geo'] for r in rows) == dict.fromkeys(['PL', 'CZ', 'DK', 'CA', 'AU'], 5)
    frontend = Path(__file__).resolve().parents[2] / 'frontend' / 'public'
    for record in rows:
        parsed = PersonaInput.model_validate({k: record[k] for k in PersonaInput.model_fields})
        assert word_count(parsed.biography) >= 400
        assert len(parsed.biography.split('\n\n')) >= 6
        assert record['fictional'] is True
        portrait = frontend / parsed.portrait_url.lstrip('/')
        assert portrait.is_file()
        assert portrait.read_bytes()[8:12] == b'WEBP'


def test_seed_is_idempotent_and_does_not_overwrite_edits(setup):
    db, client, user = setup
    row = db.get(AutoReglueConfig, PREFIX + 'ondrej-vacek')
    row.value = {**row.value, 'first_name': 'Edited name'}; db.commit()
    seed_catalog(db)
    assert client.get('/api/personas/ondrej-vacek').json()['first_name'] == 'Edited name'
    assert client.get('/api/personas').json()['total'] == 25


def test_authenticated_editor_can_read_summaries_and_full_profiles(setup):
    db, client, user = setup
    user['is_admin'] = False
    response = client.get('/api/personas')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    catalog = response.json()
    assert sum(c['count'] for c in catalog['countries']) == 25
    assert all(c['count'] == 5 and c['flag'] for c in catalog['countries'])
    assert 'biography' not in catalog['items'][0]
    detail = client.get('/api/personas/ondrej-vacek')
    assert detail.status_code == 200
    assert detail.json()['word_count'] >= 400
    assert detail.json()['revision'] == 1


@pytest.mark.parametrize('method,path,payload', [
    ('get', '/api/personas', None), ('get', '/api/personas/ondrej-vacek', None),
    ('post', '/api/personas', body()), ('put', '/api/personas/ondrej-vacek', {**body(), 'revision': 1}),
])
def test_unauthenticated_requests_are_rejected(setup, method, path, payload):
    db, client, user = setup
    del client.app.dependency_overrides[require_auth]
    kwargs = {'json': payload} if payload else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401


@pytest.mark.parametrize('method,path,payload', [
    ('post', '/api/personas', body()), ('put', '/api/personas/ondrej-vacek', {**body(), 'revision': 1}),
])
def test_regular_users_cannot_modify_catalog(setup, method, path, payload):
    db, client, user = setup; user['is_admin'] = False
    assert getattr(client, method)(path, json=payload).status_code == 403
    assert client.get('/api/personas').json()['total'] == 25


def test_new_author_and_edit_persist_in_another_database_session(setup):
    db, client, user = setup
    payload = {**body(), 'first_name': 'Anna', 'last_name': 'Nowak', 'geo': 'PL', 'portrait_url': ''}
    created = client.post('/api/personas', json=payload)
    assert created.status_code == 201
    persona = created.json()
    assert persona['id'].startswith('anna-nowak-') and persona['language'] == 'pl'
    response = client.put('/api/personas/' + persona['id'], json={**payload, 'revision': 1, 'specialization': 'Redaktorka poradników'})
    assert response.status_code == 200
    with Session(db.bind) as fresh:
        value = fresh.get(AutoReglueConfig, PREFIX + persona['id']).value
        assert value['revision'] == 2 and value['specialization'] == 'Redaktorka poradników'
    catalog = client.get('/api/personas').json()
    assert catalog['total'] == 26
    assert next(c['count'] for c in catalog['countries'] if c['code'] == 'PL') == 6


def test_concurrent_stale_edit_cannot_overwrite_newer_revision(setup):
    db, client, user = setup
    payload = {**body(), 'revision': 1}
    assert client.put('/api/personas/ondrej-vacek', json={**payload, 'first_name': 'New name'}).status_code == 200
    stale = client.put('/api/personas/ondrej-vacek', json={**payload, 'first_name': 'Stale name'})
    assert stale.status_code == 409
    assert client.get('/api/personas/ondrej-vacek').json()['first_name'] == 'New name'


@pytest.mark.parametrize('change', [
    {'biography': 'Only a short biography'}, {'geo': 'ZZ'}, {'specializations': ['one']},
    {'specializations': ['one', 'One', 'two', 'three']}, {'awards': []},
    {'portrait_url': 'https://example.test/photo.jpg'}, {'fictional': False},
])
def test_invalid_edits_are_rejected_without_mutating_record(setup, change):
    db, client, user = setup
    assert client.put('/api/personas/ondrej-vacek', json={**body(), 'revision': 1, **change}).status_code == 422
    assert client.get('/api/personas/ondrej-vacek').json()['revision'] == 1


def test_missing_profile_returns_not_found(setup):
    db, client, user = setup
    assert client.get('/api/personas/no-such-person').status_code == 404


def test_real_app_registers_routes_and_seeds_when_schema_init_is_skipped(monkeypatch):
    from app import main
    calls = []
    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *args): return None
    monkeypatch.setattr(main.settings, 'app_skip_db_init', True)
    monkeypatch.setattr(main, 'SessionLocal', FakeSession)
    monkeypatch.setattr(main, 'seed_catalog', lambda db: calls.append('seed'))
    monkeypatch.setattr(main, 'init_db', lambda: pytest.fail('Schema already initialized'))
    main.on_startup()
    assert calls == ['seed']
    paths = {route.path for route in main.app.routes}
    assert '/api/personas' in paths and '/api/personas/{persona_id}' in paths
