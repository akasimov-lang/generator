from sqlalchemy import select

from app import models
from app.project_cache import sync_project_cache
from app.security import require_auth
from test_api_serialization import make_client


def test_mass_actions_status_persists_and_survives_canonical_sync():
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site_id = site.id
        site.external_project_id = 'bulk-project'
        db.commit()
    response = client.patch(f'/api/sites/{site_id}/status', json={'project_status': 'mass_actions'})
    assert response.status_code == 200
    assert response.json()['project_status'] == 'mass_actions'
    assert response.json()['is_test_project'] is False
    with sessions() as db:
        for canon in ['first.test', 'second.test']:
            sync_project_cache(db, [{'id': 'bulk-project', 'name': 'DE обзорник', 'settings': {'canon': canon, 'domains': [canon]}}])
            db.commit()
            assert db.get(models.Site, site_id).project_status == 'mass_actions'
        assert db.scalar(select(models.NetworkOperation)) is None
    sites = client.get('/api/sites').json()
    assert next(site for site in sites if site['id'] == site_id)['project_status'] == 'mass_actions'
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
