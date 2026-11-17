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
from app.models import AutoReglueConfig, Site
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
        assert 'fictional' not in record
        assert parsed.age is None
        assert parsed.project_ids == []
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
    ('get', '/api/personas/projects', None),
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
    {'age': -1}, {'age': 121}, {'age': 30.5}, {'age': True}, {'age': '40'},
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


def add_project(db, name):
    project = Site(name=name, base_url='https://' + name, publication_endpoint='/publish')
    db.add(project); db.commit()
    return project


def test_metadata_migration_preserves_manually_added_profiles_and_edits(setup):
    db, client, user = setup
    original = db.get(AutoReglueConfig, PREFIX + 'ondrej-vacek').value
    value = {**original, 'id': 'manual-author', 'first_name': 'Edited', 'fictional': True,
             'age': 45, 'project_ids': ['kept-id'], 'revision': 7}
    db.add(AutoReglueConfig(key=PREFIX + 'manual-author', value=value)); db.commit()
    seed_catalog(db)
    stored = db.get(AutoReglueConfig, PREFIX + 'manual-author').value
    assert stored == {key: item for key, item in value.items() if key != 'fictional'}
    seed_catalog(db)
    assert db.get(AutoReglueConfig, PREFIX + 'manual-author').value == stored


def test_legacy_metadata_migration_defaults_age_and_projects_to_empty(setup):
    db, client, user = setup
    row = db.get(AutoReglueConfig, PREFIX + 'ondrej-vacek')
    value = {key: item for key, item in row.value.items() if key not in ('age', 'project_ids')}
    row.value = {**value, 'fictional': True}; db.commit()
    seed_catalog(db)
    assert row.value == {**value, 'age': None, 'project_ids': []}


def test_age_is_optional_and_can_be_saved_and_cleared(setup):
    db, client, user = setup
    assert client.get('/api/personas/ondrej-vacek').json()['age'] is None
    changed = client.put('/api/personas/ondrej-vacek', json={**body(), 'revision': 1, 'age': 39})
    assert changed.status_code == 200
    with Session(db.bind) as fresh:
        assert fresh.get(AutoReglueConfig, PREFIX + 'ondrej-vacek').value['age'] == 39
    cleared = client.put('/api/personas/ondrej-vacek', json={**body(), 'revision': 2, 'age': None})
    assert cleared.status_code == 200 and cleared.json()['age'] is None


def test_author_project_links_persist_deduplicate_and_follow_current_project_data(setup):
    db, client, user = setup
    project = add_project(db, 'project.test')
    project.cache_canon = 'main.test'; project.fibery_name = '#254 Example'; db.commit()
    payload = {**body(), 'project_ids': [project.id, project.id]}
    created = client.post('/api/personas', json=payload)
    assert created.status_code == 201
    author = created.json()
    assert author['project_ids'] == [project.id]
    assert author['projects'] == [{'id': project.id, 'name': 'project.test', 'main_domain': 'main.test', 'fibery_name': '#254 Example'}]
    with Session(db.bind) as fresh:
        assert fresh.get(AutoReglueConfig, PREFIX + author['id']).value['project_ids'] == [project.id]
    project.cache_canon = 'new-main.test'; db.commit()
    listed = next(p for p in client.get('/api/personas').json()['items'] if p['id'] == author['id'])
    assert listed['projects'][0]['main_domain'] == 'new-main.test'
    assert 'biography' not in listed and 'biography_excerpt' not in listed
    detail = client.get('/api/personas/' + author['id']).json()
    assert detail['projects'] == listed['projects'] and detail['word_count'] >= 400
    removed = client.put('/api/personas/' + author['id'], json={**body(), 'revision': 1, 'project_ids': []})
    assert removed.status_code == 200 and removed.json()['projects'] == []


def test_unknown_project_rejected_without_changing_author(setup):
    db, client, user = setup
    before = client.get('/api/personas/ondrej-vacek').json()
    result = client.put('/api/personas/ondrej-vacek', json={**body(), 'revision': 1, 'project_ids': ['missing']})
    assert result.status_code == 422
    assert client.get('/api/personas/ondrej-vacek').json() == before


def test_project_choices_and_author_links_respect_user_access(setup):
    db, client, user = setup
    allowed = add_project(db, 'allowed.test')
    hidden = add_project(db, 'hidden.test')
    changed = client.put('/api/personas/ondrej-vacek', json={**body(), 'revision': 1, 'project_ids': [hidden.id, allowed.id]})
    assert changed.status_code == 200
    assert len(client.get('/api/personas/projects').json()['items']) == 2
    user.update(is_admin=False, allowed_site_ids=[allowed.id])
    choices = client.get('/api/personas/projects')
    assert choices.headers['cache-control'] == 'no-store'
    assert [p['id'] for p in choices.json()['items']] == [allowed.id]
    detail = client.get('/api/personas/ondrej-vacek').json()
    assert detail['project_ids'] == [allowed.id]
    assert hidden.id not in json.dumps(detail) and hidden.name not in json.dumps(detail)
    listed = next(p for p in client.get('/api/personas').json()['items'] if p['id'] == 'ondrej-vacek')
    assert listed['projects'] == detail['projects']
    user['allowed_site_ids'] = []
    assert client.get('/api/personas/ondrej-vacek').json()['projects'] == []
    assert client.get('/api/personas/projects').json()['items'] == []


def test_old_editor_payload_preserves_new_metadata(setup):
    db, client, user = setup
    project = add_project(db, 'kept.test')
    payload = {**body(), 'revision': 1, 'age': 38, 'project_ids': [project.id]}
    assert client.put('/api/personas/ondrej-vacek', json=payload).status_code == 200
    old_payload = {key: value for key, value in body().items() if key not in ('age', 'project_ids')}
    changed = client.put('/api/personas/ondrej-vacek', json={**old_payload, 'revision': 2, 'first_name': 'Updated'})
    assert changed.status_code == 200
    assert changed.json()['age'] == 38 and changed.json()['project_ids'] == [project.id]


def test_hidden_project_is_omitted_and_cannot_be_assigned(setup):
    db, client, user = setup
    project = add_project(db, 'removed.test')
    assert client.put('/api/personas/ondrej-vacek', json={**body(), 'revision': 1, 'project_ids': [project.id]}).status_code == 200
    project.hidden_from_projects = True; db.commit()
    assert client.get('/api/personas/projects').json()['items'] == []
    assert client.get('/api/personas/ondrej-vacek').json()['projects'] == []
    listed = next(p for p in client.get('/api/personas').json()['items'] if p['id'] == 'ondrej-vacek')
    assert listed['project_ids'] == []
    result = client.post('/api/personas', json={**body(), 'project_ids': [project.id]})
    assert result.status_code == 422
