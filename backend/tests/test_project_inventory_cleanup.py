from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select, text
from app import models, project_inventory_cleanup as cleanup
from test_site_templates import db


def configure(monkeypatch, status):
    client = httpx.Client
    monkeypatch.setattr(cleanup, 'get_settings', lambda: SimpleNamespace(project_cache_url='https://cache.test',
        project_cache_username='test', project_cache_password='test', alfan_url='test'))
    monkeypatch.setattr(cleanup, 'webdev_origin_headers', lambda settings: {})
    def respond(request):
        if request.url.path == '/auth/login':
            return httpx.Response(200, json={'token': 'test'})
        return httpx.Response(status, json={'message': 'not found'})
    monkeypatch.setattr(cleanup.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(respond)))


def site(db, active=False):
    row = models.Site(name='old.test', base_url='https://old.test', publication_endpoint='',
                      external_project_id='old', cache_server_ip='bear', is_active=active)
    db.add(row); db.commit()
    return row


@pytest.mark.parametrize('status', [404, 403])
def test_confirmed_deleted_project_removed_and_related_history_archived(db, monkeypatch, status):
    configure(monkeypatch, status)
    db.execute(text('PRAGMA foreign_keys=ON'))
    row = site(db); sid = row.id
    parent = models.Section(id='parent', site_id=sid, external_id='parent', name='Parent', path='/parent/')
    child = models.Section(id='child', site_id=sid, external_id='child', name='Child', path='/child/', parent_id='parent')
    db.add(parent); db.flush(); db.add(child)
    db.add(models.NetworkOperation(site_id=sid, action='alternates', status='confirmed', initiator='test',
                                   request_payload={'alternates_before': {'markup': 'original'}}, id='operation'))
    db.commit()
    result = cleanup.prune_deleted_projects(db, [], {'bear': set()}, {})
    assert result['removed_projects'] == ['old.test']
    assert db.scalar(select(models.Site)) is None
    archive = db.get(models.AutoReglueConfig, 'removed-project:' + sid)
    assert archive.value['tables']['network_operations'][0]['request_payload']['alternates_before']['markup'] == 'original'
    assert len(archive.value['tables']['sections']) == 2


@pytest.mark.parametrize('status,active,in_inventory', [(403, True, False), (403, False, True), (500, False, False), (401, False, False), (200, False, False)])
def test_access_errors_and_uncertain_absence_do_not_remove(db, monkeypatch, status, active, in_inventory):
    configure(monkeypatch, status)
    site(db, active)
    result = cleanup.prune_deleted_projects(db, [], {'bear': {'old.test'} if in_inventory else set()}, {})
    assert result['removed_projects'] == []
    assert db.scalar(select(models.Site)) is not None


def test_partial_inventory_and_present_cache_never_remove(db, monkeypatch):
    configure(monkeypatch, 404)
    site(db)
    assert not cleanup.prune_deleted_projects(db, [], {}, {'bear': 'timeout'})['removed_projects']
    assert not cleanup.prune_deleted_projects(db, [{'name': 'old.test'}], {'bear': set()}, {})['removed_projects']
