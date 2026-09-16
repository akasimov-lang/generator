import pytest
from sqlalchemy import select

from app import models, worker
from app.project_cache import sync_project_cache
from test_api_serialization import make_client


@pytest.mark.parametrize('rendered', [True, False])
def test_legacy_menu_results_are_read_without_timestamp_or_checks(rendered):
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site_id = site.id
        site.header_menu_rendered = rendered
        site.footer_menu_rendered = rendered
        site.menu_capabilities_checked_at = None
        db.commit()
    for _ in range(2):
        result = client.get(f'/api/sites/{site_id}/menu-capabilities').json()
        assert result['header_menu_rendered'] is rendered
        assert result['footer_menu_rendered'] is rendered
        assert result['checked_at'] is None  # Never invent the old check's date.
        assert result['check_status'] == 'completed'
    with sessions() as db:
        assert db.scalar(select(models.MenuVisibilityCheck)) is None


def test_template_check_cannot_overwrite_saved_live_nesting(monkeypatch):
    client, sessions = make_client()
    monkeypatch.setattr('app.api.refresh_project_server_id', lambda *args: None)
    monkeypatch.setattr('app.api.fetch_project_template_capabilities_resilient', lambda site: {
        'header_menu_rendered': True, 'footer_menu_rendered': True,
        'header_menu_nested': True, 'footer_menu_nested': True,
    })
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site_id = site.id
        site.header_menu_rendered = True
        site.footer_menu_rendered = False
        site.header_menu_nested = False
        site.footer_menu_nested = False
        db.commit()
    response = client.post(f'/api/sites/{site_id}/menu-capabilities/template-check')
    assert response.status_code == 200
    assert response.json()['header_menu_nested'] is False
    assert response.json()['footer_menu_rendered'] is False
    assert response.json()['footer_menu_nested'] is False


def test_worker_commits_result_and_failed_retry_keeps_it(monkeypatch):
    client, sessions = make_client()
    monkeypatch.setattr(worker, 'SessionLocal', sessions)
    monkeypatch.setattr(worker, 'refresh_project_server_id', lambda *args: None)
    monkeypatch.setattr(worker, 'fetch_project_menu_capabilities', lambda *args, **kwargs: {
        'header_menu_template_rendered': True, 'header_menu_rendered': True, 'header_menu_nested': True,
        'footer_menu_template_rendered': True, 'footer_menu_rendered': False, 'footer_menu_nested': False,
    })
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.external_project_id = 'persist-check'
        site_id = site.id
        check = models.MenuVisibilityCheck(site_id=site_id, status='queued')
        db.add(check)
        db.commit()
        check_id = check.id
    assert worker.check_site_menu_visibility_job(check_id)['status'] == 'completed'
    with sessions() as db:
        site = db.get(models.Site, site_id)
        assert site.menu_capabilities_checked_at is not None
        assert site.header_menu_rendered is True
        checked_at = site.menu_capabilities_checked_at
        sync_project_cache(db, [{'id': 'persist-check', 'name': site.name, 'settings': {'canon': 'new.test', 'domains': ['new.test']}}])
        db.commit()
        retry = models.MenuVisibilityCheck(site_id=site_id, status='queued')
        db.add(retry)
        db.commit()
        retry_id = retry.id
    def fail(*args, **kwargs):
        raise RuntimeError('Temporary browser failure')
    monkeypatch.setattr(worker, 'fetch_project_menu_capabilities', fail)
    assert worker.check_site_menu_visibility_job(retry_id)['status'] == 'failed'
    result = client.get(f'/api/sites/{site_id}/menu-capabilities').json()
    assert result['check_status'] == 'failed'
    assert result['header_menu_rendered'] is True
    assert result['footer_menu_rendered'] is False
    with sessions() as db:
        assert db.get(models.Site, site_id).menu_capabilities_checked_at == checked_at
