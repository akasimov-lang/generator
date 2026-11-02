from sqlalchemy import select
import pytest

from app import models
from app.project_cache import sync_project_cache
from app.security import require_auth
from test_api_serialization import make_client


@pytest.mark.parametrize('status', ['mass_actions', 'vitalina', 'hands_only', 'geo_ru', 'geo_kz', 'inactive'])
def test_mass_actions_status_persists_and_survives_canonical_sync(status):
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site_id = site.id
        site.external_project_id = 'bulk-project'
        db.commit()
    response = client.patch(f'/api/sites/{site_id}/status', json={'project_status': status})
    assert response.status_code == 200
    assert response.json()['project_status'] == status
    assert response.json()['is_test_project'] is False
    with sessions() as db:
        for canon in ['first.test', 'second.test']:
            sync_project_cache(db, [{'id': 'bulk-project', 'name': 'DE обзорник', 'settings': {'canon': canon, 'domains': [canon]}}])
            db.commit()
            assert db.get(models.Site, site_id).project_status == status
        assert db.scalar(select(models.NetworkOperation)) is None
    sites = client.get('/api/sites').json()
    assert next(site for site in sites if site['id'] == site_id)['project_status'] == status
    assert client.patch(f'/api/sites/{site_id}/status', json={'project_status': 'working'}).status_code == 200


def test_mass_actions_requires_admin_and_rejects_unknown_status():
    client, sessions = make_client()
    with sessions() as db:
        site_id = db.scalar(select(models.Site.id))
    assert client.patch(f'/api/sites/{site_id}/status', json={'project_status': 'automatic_reglue'}).status_code == 422
    client.app.dependency_overrides[require_auth] = lambda: {'id': 'regular-id', 'username': 'reader', 'is_admin': False}
    assert client.patch(f'/api/sites/{site_id}/status', json={'project_status': 'mass_actions'}).status_code == 403
    with sessions() as db:
        assert db.get(models.Site, site_id).project_status == 'working'


def test_sites_panel_can_include_grouped_inactive_without_activating_them():
    client, sessions = make_client()
    with sessions() as db:
        for status in ['mass_actions', 'vitalina', 'hands_only', 'geo_ru', 'geo_kz', 'inactive', 'not_in_focus']:
            db.add(models.Site(name=f'inactive-{status}', base_url='https://example.test',
                               publication_endpoint='/', is_active=False, project_status=status))
        db.commit()
    assert len(client.get('/api/sites').json()) == 1
    rows = client.get('/api/sites?include_grouped_inactive=true').json()
    inactive = [s for s in rows if not s['is_active']]
    assert {s['project_status'] for s in inactive} == {'mass_actions', 'vitalina', 'hands_only', 'geo_ru', 'geo_kz', 'inactive'}
    assert len(rows) == 7
    with sessions() as db:
        assert all(not s.is_active for s in db.scalars(select(models.Site).where(models.Site.name.like('inactive-%'))))
    assert len(client.get('/api/sites').json()) == 1


def test_lookup_reads_inactive_project_from_cache_without_activating():
    client, sessions = make_client()
    with sessions() as db:
        site = models.Site(name='inactive-cached.test', base_url='https://cached.test',
                           publication_endpoint='/', is_active=False, project_status='vitalina',
                           cache_canon='cached.test', domains_count=4)
        db.add(site)
        db.commit()
        site_id = site.id
    for query in [f'name=inactive-cached.test', f'site_id={site_id}']:
        response = client.get('/api/sites/lookup?' + query)
        assert response.status_code == 200
        assert response.json()['cache_canon'] == 'cached.test'
        assert response.json()['is_active'] is False
        assert response.json()['domains_count'] == 4
    assert client.get('/api/sites/lookup?name=does-not-exist.test').status_code == 404


def test_hidden_project_stays_out_of_lists_after_sync():
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site_id = site.id
        site.external_project_id = 'hidden-project'
        site.hidden_from_projects = True
        site.project_status = 'mass_actions'
        db.commit()
        sync_project_cache(db, [{'id': 'hidden-project', 'name': 'Hidden project', 'settings': {'canon': 'hidden.test', 'domains': ['hidden.test']}}])
        db.commit()
        assert db.get(models.Site, site_id).hidden_from_projects is True
    for endpoint in ['/api/sites', '/api/sites?include_grouped_inactive=true', '/api/sites/cache/projects']:
        assert all(row['id'] != site_id for row in client.get(endpoint).json())
    with sessions() as db:
        assert db.get(models.Site, site_id) is not None


@pytest.mark.parametrize('site_type', ['monobrand', 'general'])
def test_manual_site_type_survives_sync_without_changing_brand(site_type):
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site_id = site.id
        site.external_project_id = 'type-project'
        site.brand = 'Pin-Up'
        site.brand_source = 'manual'
        db.commit()
    response = client.patch(f'/api/sites/{site_id}/type', json={'site_type':site_type})
    assert response.status_code == 200
    assert response.json()['site_type'] == site_type
    assert response.json()['brand'] == 'Pin-Up'
    with sessions() as db:
        sync_project_cache(db, [{'id':'type-project','name':'Type project','settings':{'canon':'type.test','domains':['type.test']}}])
        db.commit()
        assert db.get(models.Site, site_id).site_type == site_type
    assert client.get(f'/api/sites/lookup?site_id={site_id}').json()['site_type'] == site_type
    assert client.patch(f'/api/sites/{site_id}/type', json={'site_type':'unknown'}).status_code == 422


@pytest.mark.parametrize('team', ['', ' Rankomen ', 'Kalendula', None])
def test_team_and_fibery_cache_update_even_with_manual_flag(team):
    from app.project_cache import _apply_fibery_name
    site = models.Site(name='team.test', fibery_name='#1_Manual', fibery_name_manual=True)
    _apply_fibery_name(site, {'webdevDuty':{'team':team,'fibery':'overwrite'}})
    assert site.project_team == (team or '').strip()
    assert site.fibery_name == 'overwrite'
    assert site.fibery_name_manual is True
    _apply_fibery_name(site, {'webdevDuty':{'fibery':'still no team'}})
    assert site.project_team == (team or '').strip()
