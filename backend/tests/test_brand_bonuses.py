import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.brand_bonuses import dataset, router
from app.db import get_db
from app.security import require_auth


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[require_auth] = lambda: {'id': 'editor', 'is_admin': False}
    with TestClient(app) as client:
        yield client


def test_catalog_requires_authentication():
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as client:
        assert client.get('/api/brand-bonuses').status_code == 401
        assert client.get('/api/brand-bonuses/pl/lemon-casino').status_code == 401


def test_editor_can_read_catalog_and_country_counts(client):
    response = client.get('/api/brand-bonuses')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    data = response.json()
    assert data['total'] == len(data['items']) == sum(c['brands'] for c in data['countries'])
    assert data['offers_total'] == sum(len(b['offers']) for b in data['items'])
    assert data['offers_total'] == sum(c['offers'] for c in data['countries'])
    assert {c['code'] for c in data['countries']} == {'PL', 'CZ'}


@pytest.mark.parametrize('geo', ['pl', 'CZ'])
def test_country_filter_and_brand_details_remain_scoped(client, geo):
    response = client.get('/api/brand-bonuses', params={'geo': geo})
    assert response.status_code == 200
    data = response.json()
    assert data['items'] and all(b['geo'] == geo.upper() for b in data['items'])
    brand = data['items'][0]
    detail = client.get(f'/api/brand-bonuses/{geo}/{brand["id"]}')
    assert detail.json() == brand
    assert detail.headers['cache-control'] == 'private, no-store'


def test_wrong_country_cannot_fall_back_to_another_country(client):
    assert client.get('/api/brand-bonuses/cz/total-casino').status_code == 404
    assert client.get('/api/brand-bonuses/de/total-casino').status_code == 404
    assert client.get('/api/brand-bonuses?geo=DE').status_code == 422


def test_provenance_is_internal_on_list_and_detail(client):
    for path in ['/api/brand-bonuses', '/api/brand-bonuses/pl/total-casino']:
        response = client.get(path)
        assert response.status_code == 200
        assert '_sources' not in response.text
        assert '_logo_source' not in response.text
        assert 'https://' not in response.text
        assert 'http://' not in response.text


def test_dataset_has_distinct_offers_country_specific_evidence_and_local_logos():
    data = dataset()
    public = Path(__file__).resolve().parents[2] / 'frontend/public'
    keys = [(b['geo'], b['id']) for b in data['items']]
    assert len(keys) == len(set(keys))
    for brand in data['items']:
        assert brand['geo'] in {'PL', 'CZ'}
        assert re.fullmatch('[a-z0-9-]+', brand['id'])
        assert brand['logo_url'].startswith('/brand-bonuses/logos/')
        assert '..' not in brand['logo_url']
        assert (public / brand['logo_url'].lstrip('/')).stat().st_size > 100
        ids = [o['id'] for o in brand['offers']]
        assert ids and len(ids) == len(set(ids))
        for offer in brand['offers']:
            assert offer['title'].strip() and offer['observed_at']
            assert offer['status'] in {'saved', 'verified', 'expired'}
            assert offer['_sources']
            assert all(s['kind'] == 'official' for s in offer['_sources']) if offer['status'] == 'verified' else True
            assert all(f['label'] and f['value'].strip() for f in offer['facts'])
    pl = next(b for b in data['items'] if b['id'] == '22bet' and b['geo'] == 'PL')
    cz = next(b for b in data['items'] if b['id'] == '22bet' and b['geo'] == 'CZ')
    assert 'PLN' in json.dumps(pl) and 'Kč' not in json.dumps(pl, ensure_ascii=False)
    assert 'Kč' in json.dumps(cz, ensure_ascii=False) and 'PLN' not in json.dumps(cz)
