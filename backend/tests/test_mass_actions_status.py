from sqlalchemy import select
import pytest

from app import models
from app.project_cache import sync_project_cache
from app.security import require_auth
from test_api_serialization import make_client


@pytest.mark.parametrize('status', ['mass_actions', 'vitalina', 'hands_only'])
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
        for status in ['mass_actions', 'vitalina', 'hands_only', 'not_in_focus']:
            db.add(models.Site(name=f'inactive-{status}', base_url='https://example.test',
                               publication_endpoint='/', is_active=False, project_status=status))
        db.commit()
    assert len(client.get('/api/sites').json()) == 1
    rows = client.get('/api/sites?include_grouped_inactive=true').json()
    inactive = [s for s in rows if not s['is_active']]
    assert {s['project_status'] for s in inactive} == {'mass_actions', 'vitalina', 'hands_only'}
    assert len(rows) == 4
    with sessions() as db:
        assert all(not s.is_active for s in db.scalars(select(models.Site).where(models.Site.name.like('inactive-%'))))
    assert len(client.get('/api/sites').json()) == 1
