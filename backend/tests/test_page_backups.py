"""Native universal-admin backups must exist before any destructive processing."""
import copy
import json
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app import models, background_jobs, project_pages as pages, services
from app.page_backups import ensure_backup, PageBackupError
from test_project_pages import setup, draft


def queue(client, db, site, path, content, action='paragraphs', **fields):
    provider = models.AiProvider(name='Gemini', provider_type='gemini', endpoint_url='https://ai.test', api_key='test')
    db.add(provider); db.commit()
    response = client.post(path + '/ai', json={'action': action, 'provider_id': provider.id,
                                              'content': content, **fields})
    assert response.status_code == 202, response.text
    return db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.payload['draft_id'].as_string() == response.json()['id']))


def test_rewrite_backs_up_exact_unsaved_source_and_shortcodes_before_gemini(setup, monkeypatch):
    client, db, site, state = setup
    path, payload = draft(client, site)
    original = copy.deepcopy(state['project'])
    payload['content']['blocks'][2]['data']['text'] = 'Unsaved editor paragraph'
    def verify_backup():
        assert len(state['backup_requests']) == 1
        saved = state['backups'][0]['data']
        assert saved == {**original['data']['pages'][1], 'content': payload['content'],
                         'title': 'Unsaved title', '_shortcodes': original['shortcodes']}
        assert state['events'] == ['backupList', 'backup', 'backupList']
    reviews=[]
    async def generate(_provider, prompt, **kwargs):
        verify_backup()
        if '\nPAIRS=' in prompt:
            pairs=json.loads(prompt.rsplit('\nPAIRS=',1)[1]); reviews.append(pairs)
            assert pairs==[{'id':0,'original':'Unsaved editor paragraph','revised':'Revised editor paragraph'}]
            output={'approved':True,'language_preserved':True,'issues':[]}
        else:
            data=json.loads(prompt.rsplit('\nSOURCE_DATA=',1)[1])
            assert data['items']==[{'id':0,'text':'Unsaved editor paragraph'}]
            output={'items':[{'id':0,'text':'Revised editor paragraph'}]}
        return {'candidates': [{'content': {'parts': [{'text': json.dumps(output)}]}}]}
    monkeypatch.setattr(services, 'call_gemini', generate)
    job = queue(client, db, site, path, payload['content'], title='Unsaved title')
    assert background_jobs.run_job(db, job.id)['status'] == 'completed', job.error
    assert len(reviews)==1
    row=db.get(models.ProjectPageDraft,job.payload['draft_id'])
    assert row.result_metadata['meaning_reviewed'] is True
    verify_backup()
    assert state['project'] == original and not state['requests']
    assert job.result['backup']['name'] == state['backups'][0]['name']
    ledger = db.scalar(select(models.AutoReglueConfig))
    assert len(ledger.key) <= 80 and ledger.value['status'] == 'confirmed'
    assert background_jobs.run_job(db, job.id)['status'] == 'skipped'
    assert len(state['backup_requests']) == 1


@pytest.mark.parametrize('action', ['paragraphs', 'headings', 'meta_headings', 'trim_50', 'trim_99'])
def test_unconfirmed_backup_blocks_all_processing_and_survives_retries(setup, monkeypatch, action):
    client, db, site, state = setup
    path, payload = draft(client, site)
    payload['content']['blocks'].insert(0, {'type': 'header', 'data': {'text': 'Heading', 'level': 1}})
    async def forbidden(*args, **kwargs):
        pytest.fail('Gemini must not run without a verified backup')
    monkeypatch.setattr(services, 'call_gemini', forbidden)
    state['backup_apply'] = False
    job = queue(client, db, site, path, payload['content'], action)
    assert background_jobs.run_job(db, job.id)['status'] == 'failed'
    row = db.get(models.ProjectPageDraft, job.payload['draft_id'])
    assert row.status == 'failed' and 'бекап' in row.error
    assert row.result_content is None and not state['requests']
    # A new job with the same source must check the list, never repeat an uncertain POST.
    retry = queue(client, db, site, path, payload['content'], action)
    assert background_jobs.run_job(db, retry.id)['status'] == 'failed'
    assert len(state['backup_requests']) == 1


def test_timeout_after_persisted_backup_is_confirmed_without_duplicate(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    state['backup_failure'] = httpx.ReadTimeout('secret server address')
    job = queue(client, db, site, path, payload['content'], 'trim_99')
    assert background_jobs.run_job(db, job.id)['status'] == 'completed'
    assert job.result['backup']['name'] == state['backups'][0]['name']
    second = queue(client, db, site, path, payload['content'], 'trim_50')
    assert background_jobs.run_job(db, second.id)['status'] == 'completed'
    assert len(state['backup_requests']) == 1 and not state['requests']


def test_matching_backup_must_include_all_fields_and_shortcodes(setup):
    client, db, site, state = setup
    home = state['project']['data']['pages'][1]
    state['backups'] = [{'name': 'old.json', 'data': {**copy.deepcopy(home), '_shortcodes': []}}]
    with pages.Remote(db, site) as remote:
        receipt = ensure_backup(db, remote, site, state['project'], home, actor='anton', operation='test')
    assert receipt['name'] != 'old.json' and len(state['backup_requests']) == 1
    with pages.Remote(db, site) as remote:
        assert ensure_backup(db, remote, site, state['project'], home, actor='anton', operation='test2') == receipt
    assert len(state['backup_requests']) == 1


def test_backup_list_failure_blocks_publication_without_leaking_details(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    state['backup_list_failure'] = httpx.ConnectError('secret credentials and server')
    response = client.put(path, json=payload)
    assert response.status_code == 502
    assert 'бекап' in response.json()['detail'] and 'secret' not in response.text
    assert not state['requests'] and not state['backup_requests']
    assert not db.scalar(select(models.ProjectPageEdit))


def test_publication_backs_up_current_live_content_and_confirms_before_update(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    original = copy.deepcopy(state['project']['data']['pages'][1])
    payload['content']['blocks'][2]['data']['text'] = 'Changed for publication'
    result = client.put(path, json=payload)
    assert result.json()['status'] == 'confirmed', result.text
    assert state['backups'][0]['data'] == {**original, '_shortcodes': state['project']['shortcodes']}
    assert state['events'] == ['backupList', 'backup', 'backupList', 'update']
    assert client.put(path, json=payload).json()['status'] == 'confirmed'
    assert len(state['requests']) == len(state['backup_requests']) == 1


def test_concurrent_external_edit_during_backup_is_not_overwritten(setup, monkeypatch):
    client, db, site, state = setup
    path, payload = draft(client, site)
    original = pages.Remote.request
    def request(self, method, route, body):
        result = original(self, method, route, body)
        if route == '/projects/backup':
            state['project']['data']['pages'][1]['title'] = 'Someone else changed it'
        return result
    monkeypatch.setattr(pages.Remote, 'request', request)
    response = client.put(path, json=payload)
    assert response.status_code == 409 and not state['requests']


def test_native_plaintext_backup_response_and_json_errors(monkeypatch):
    from app import project_network as network
    monkeypatch.setattr(network, 'project_server_url', lambda site, path: 'https://server.test' + path)
    remote = network.Remote(None, None)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(201, text='/backups/original.json'))) as client:
        remote.client = client
        assert remote.request('POST', '/projects/backup', {}) == (201, {'message': '/backups/original.json'})
        with pytest.raises(ValueError): remote.request('POST', '/projects/update', {})
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'success': False}))) as client:
        remote.client = client
        assert remote.request('POST', '/projects/backup', {})[1] == {'success': False}


def test_publication_does_not_continue_after_unconfirmed_backup(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    state['backup_apply'] = False
    response = client.put(path, json=payload)
    assert response.status_code == 502 and not state['requests']
    assert client.put(path, json=payload).status_code == 502
    assert len(state['backup_requests']) == 1
    # A later list confirmation unlocks the original save without a duplicate.
    state['backups'].append({'name': 'late.json', 'data': state['backup_requests'][0]['page']})
    assert client.put(path, json=payload).json()['status'] == 'confirmed'
    assert len(state['backup_requests']) == len(state['requests']) == 1


def test_explicit_backup_rejection_and_corrupt_list_fail_closed(setup, monkeypatch):
    client, db, site, state = setup
    path, payload = draft(client, site)
    original = pages.Remote.request
    def rejected(self, method, route, body):
        if route == '/projects/backup': return 200, {'success': False}
        return original(self, method, route, body)
    monkeypatch.setattr(pages.Remote, 'request', rejected)
    assert client.put(path, json=payload).status_code == 502
    assert not state['requests']
    state['backups'] = {'success': True}
    assert client.put(path, json=payload).status_code == 502
    assert not state['requests']


def test_pilot_backup_checks_after_write_and_keeps_local_source(setup):
    client, db, site, state = setup
    path, payload = draft(client, site)
    state['backup_list_failure'] = httpx.ConnectError('Unavailable backup list')
    db.info['pilot_defer_backup'] = True
    result = pages.save_page(site.id,path.rsplit('/',1)[-1],pages.PageEdit.model_validate(payload),{'username':'anton'},db)
    assert result['status']=='confirmed'
    assert state['events'][0]=='backup' and 'backupList' not in state['events']
    assert len(state['backup_requests'])==1
    ledger=db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.like('page-backup:%')))
    assert ledger.value['snapshot']['content']
    assert state['requests']
