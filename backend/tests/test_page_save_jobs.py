from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from sqlalchemy import select

from app import models, background_jobs, page_save_jobs, page_editor_drafts
from app.security import require_auth
from test_project_pages import setup, draft


def test_background_save_returns_before_remote_io_and_duplicate_worker_does_not_write_twice(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    response = client.put(path+'?background=true', json=payload)
    assert response.status_code == 200 and response.json()['status'] == 'pending'
    assert response.json()['background'] and not state['events']
    assert client.get(path+'/edits/'+payload['request_id']).json()['status'] == 'pending'
    assert client.put(path+'?background=true', json=payload).json()['id'] == payload['request_id']
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'confirmed'
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'skipped'
    assert len(state['requests']) == 1
    assert client.get(path+'/edits/'+payload['request_id']).json()['page']['title'] == 'Updated home'
    assert db.get(models.BackgroundJob, payload['request_id']).status == 'completed'


def test_worker_restart_after_write_only_confirms_receipt_and_resolves_project_note(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    client.put(path+'?background=true', json=payload)
    state['failure'] = httpx.ReadTimeout('private service credentials')
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'pending'
    note = db.scalar(select(models.ProjectNotification))
    assert note.active and note.code == 'PAGE_SAVE' and 'private' not in note.message
    assert len(state['requests']) == 1
    state['failure'] = None
    state['project']['data']['pages'][1] = deepcopy(state['requests'][0]['page'])
    # Dispatcher may deliver this again after the worker disappears.
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'confirmed'
    assert len(state['requests']) == 1
    db.refresh(note)
    assert not note.active and note.resolved_at


def test_external_page_revision_conflict_preserves_page_and_records_project_note(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    client.put(path+'?background=true', json=payload)
    state['project']['data']['pages'][1]['title'] = 'External edit'
    outcome = background_jobs.run_job(db, payload['request_id'])
    assert outcome['status'] == 'failed' and 'изменилась' in outcome['error']
    assert not state['requests']
    assert db.scalar(select(models.ProjectNotification)).active
    assert client.get(path+'/edits/'+payload['request_id']).json()['status'] == 'failed'


def test_request_id_reuse_cannot_replace_another_save_or_job(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    client.put(path+'?background=true', json=payload)
    assert client.put(path+'?background=true', json={**payload,'title':'Different'}).status_code == 409
    assert client.put(path+'different?background=true', json=payload).status_code == 409
    payload['request_id'] = str(uuid4())
    db.add(models.BackgroundJob(id=payload['request_id'], kind='other', payload={}))
    db.commit()
    assert client.put(path+'?background=true', json=payload).status_code == 409
    assert not state['requests']


def test_background_save_and_status_obey_site_permissions(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    client.put(path+'?background=true', json=payload)
    client.app.dependency_overrides[require_auth] = lambda: {'username':'other','allowed_site_ids':[]}
    assert client.put(path+'?background=true', json=payload).status_code == 404
    assert client.get(path+'/edits/'+payload['request_id']).status_code == 404
    assert not state['requests']


def test_editor_reopen_restores_queued_save_and_hides_confirmed_draft(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    key = path.rsplit('/', 1)[-1]
    page_editor_drafts.save_editor_draft(site.id, key,
        page_editor_drafts.EditorDraft.model_validate(payload), {'username':'anton'}, db)
    client.put(path+'?background=true', json=payload)
    snapshot = page_editor_drafts.read_editor_draft(site.id, key, {'username':'anton'}, db)
    assert snapshot['operation']['background'] and snapshot['operation']['status'] == 'pending'
    background_jobs.run_job(db, payload['request_id'])
    assert page_editor_drafts.read_editor_draft(site.id, key, {'username':'anton'}, db) is None


def test_uncertain_write_stops_checks_without_resending_and_keeps_note(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    client.put(path+'?background=true', json=payload)
    state['apply'] = False
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'pending'
    job = db.get(models.BackgroundJob, payload['request_id'])
    job.result = {**job.result,'checks':page_save_jobs.MAX_CHECKS-1}
    db.commit()
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'unknown'
    assert len(state['requests']) == 1 and db.scalar(select(models.ProjectNotification)).active
    state['project']['data']['pages'][1] = deepcopy(state['requests'][0]['page'])
    assert client.get(path+'/edits/'+payload['request_id']).json()['status'] == 'confirmed'
    assert not db.scalar(select(models.ProjectNotification)).active


def test_busy_network_waits_without_becoming_a_failed_save(setup, monkeypatch):
    from contextlib import contextmanager
    from app import project_pages
    client, db, site, state = setup
    path, payload = draft(client, site)
    client.put(path+'?background=true', json=payload)
    @contextmanager
    def busy(*args):
        raise project_pages.NetworkConflict('busy')
        yield
    monkeypatch.setattr(project_pages, 'network_lock', busy)
    assert background_jobs.run_job(db, payload['request_id'])['status'] == 'pending'
    assert not state['requests'] and not db.scalar(select(models.ProjectNotification))
