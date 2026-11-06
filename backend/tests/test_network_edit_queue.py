from copy import deepcopy
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest

from app import models, network_edit_queue as queue, project_network as network, background_jobs
from test_project_network import env


def prepare(env):
    db, site, remote = env
    remote.data['settings']['redirects'] = [{'url': 'old.test', 'value': 'main.test'}, {'url': 'older.test', 'value': 'main.test'}]
    remote.data['settings']['pageRedirects'] = [{'domain': 'main.test', 'redirects': [{'url': '/old/', 'value': 'https://main.test/start/'}]}]
    return network.read_network(db, site)


def add(env, action='domain_redirect', **settings):
    db, site, _ = env
    state = network.result(db, site, site.network_state)
    request = queue.Request(request_id=uuid4(), action=action, revision=state['revision'], **settings)
    request.expected = queue.fingerprint(state, request)
    queue.enqueue(db, site, request, 'anton')
    return str(request.request_id)


def test_enqueue_is_local_and_idempotent(env, monkeypatch):
    db, site, remote = env; prepare(env)
    monkeypatch.setattr(network, 'Remote', lambda *_: pytest.fail('Enqueue contacted Webdev'))
    ident = add(env, 'reserve', domain='next.test')
    request = queue.Request.model_validate(db.get(models.BackgroundJob, ident).payload['request'])
    queue.enqueue(db, site, request, 'anton')
    assert len(queue.active(db, site.id)) == 1
    assert queue.snapshot(db, site)['items'][0]['status'] == 'queued'
    assert not remote.calls


def test_independent_edits_run_fifo_and_preserve_other_rows(env):
    db, site, remote = env; prepare(env)
    first = add(env, redirect_source='old.test', redirect_original_source='old.test', redirect_target='first.test')
    second = add(env, redirect_source='older.test', redirect_original_source='older.test', redirect_target='second.test')
    assert background_jobs.run_job(db, second)['status'] == 'waiting'
    assert not remote.calls
    assert background_jobs.run_job(db, first)['status'] == 'completed'
    assert background_jobs.run_job(db, second)['status'] == 'completed'
    assert remote.data['settings']['redirects'] == [{'url': 'old.test', 'value': 'first.test'}, {'url': 'older.test', 'value': 'second.test'}]
    assert queue.execute_step(db, first)['status'] == 'skipped'
    assert len(remote.calls) == 2


def test_reserve_and_page_edit_share_queue(env):
    db, site, remote = env; prepare(env)
    first = add(env, 'reserve', domain='next.test')
    second = add(env, 'page_redirect', page_redirect_domain='main.test', page_redirect_source='/old/', page_redirect_target='https://main.test/new/', page_redirect_original_domain='main.test', page_redirect_original_source='/old/')
    assert queue.execute_step(db, second)['status'] == 'waiting'
    assert queue.execute_step(db, first)['status'] == 'completed'
    assert queue.execute_step(db, second)['status'] == 'completed'
    assert remote.data['settings']['reserve'] == 'next.test'
    assert remote.data['settings']['pageRedirects'][0]['redirects'][0]['value'] == 'https://main.test/new/'


def test_external_edit_is_not_overwritten_and_next_task_continues(env):
    db, site, remote = env; prepare(env)
    first = add(env, redirect_source='old.test', redirect_original_source='old.test', redirect_target='first.test')
    second = add(env, redirect_source='older.test', redirect_original_source='older.test', redirect_target='second.test')
    remote.data['settings']['redirects'][0]['value'] = 'external.test'
    assert queue.execute_step(db, first)['status'] == 'failed'
    assert not remote.calls
    assert queue.execute_step(db, second)['status'] == 'completed'
    assert remote.data['settings']['redirects'][0]['value'] == 'external.test'


def test_lost_remote_response_is_checked_without_resending(env):
    db, site, remote = env; prepare(env)
    ident = add(env, 'reserve', domain='next.test')
    remote.fail = httpx.ReadTimeout('lost response')
    assert queue.execute_step(db, ident)['status'] == 'waiting'
    assert db.get(models.NetworkOperation, ident)
    remote.fail = None
    assert queue.execute_step(db, ident)['status'] == 'waiting'
    assert len(remote.calls) == 1
    remote.data['settings'].update(reserve='next.test', reserveOption='next.test')
    assert queue.execute_step(db, ident)['status'] == 'completed'
    assert len(remote.calls) == 1


def test_busy_network_retains_job_without_write(env, monkeypatch):
    db, site, remote = env; prepare(env)
    ident = add(env, 'reserve', domain='next.test')
    @contextmanager
    def locked(*_):
        raise network.NetworkConflict('С сеткой уже выполняется операция')
        yield
    monkeypatch.setattr(network, 'network_lock', locked)
    assert queue.execute_step(db, ident)['status'] == 'waiting'
    assert db.get(models.BackgroundJob, ident).status == 'queued'
    assert not remote.calls


def test_dispatcher_delivers_edit_queue(env):
    db, site, _ = env; prepare(env)
    ident = add(env, 'reserve', domain='next.test'); sent = []
    background_jobs.dispatch_pending(db, lambda job, worker: sent.append((job, worker)))
    assert sent == [(ident, 'cache_sync')]


def test_request_id_cannot_be_reused_for_different_edit(env):
    db, site, _ = env; prepare(env)
    ident = add(env, 'reserve', domain='next.test')
    request = queue.Request.model_validate(db.get(models.BackgroundJob, ident).payload['request'])
    request.domain = 'reserve.test'
    with pytest.raises(network.NetworkConflict): queue.enqueue(db, site, request, 'anton')


def test_invalid_edit_fails_without_blocking_following_reserve(env):
    db, site, remote = env; prepare(env)
    first = add(env, redirect_source='old.test', redirect_original_source='old.test', redirect_target='main.test:invalid/path')
    second = add(env, 'reserve', domain='next.test')
    assert queue.execute_step(db, first)['status'] == 'failed'
    assert queue.execute_step(db, second)['status'] == 'completed'
    assert len(remote.calls) == 1


def test_all_to_main_queued_action(env):
    db, site, remote = env; prepare(env)
    remote.data['settings']['redirects'][0]['value'] = 'other.test'
    network.read_network(db, site)
    ident = add(env, 'domain_redirects_main')
    assert queue.execute_step(db, ident)['status'] == 'completed'
    assert all(row['value'] == 'main.test' for row in remote.data['settings']['redirects'])


def test_manual_reglue_runs_after_queued_redirect_without_blocking_ui(env):
    db, site, remote = env; prepare(env)
    first = add(env, redirect_source='old.test', redirect_original_source='old.test', redirect_target='first.test')
    second = add(env, 'reglue', domain='reserve.test')
    assert queue.execute_step(db, second)['status'] == 'waiting'
    assert queue.execute_step(db, first)['status'] == 'completed'
    assert queue.execute_step(db, second)['status'] == 'completed'
    assert remote.data['settings']['canon'] == 'reserve.test'
    assert queue.execute_step(db, second)['status'] == 'skipped'
    assert len([c for c in remote.calls if c[1].endswith('update-reglue')]) == 1


def test_pasted_url_with_path_is_confirmed_in_queue(env):
    db, site, remote = env; prepare(env)
    ident = add(env, redirect_source='old.test', redirect_original_source='old.test', redirect_target=' /https://MAIN.test/Dragonia-Casino/ ')
    assert queue.execute_step(db, ident)['status'] == 'completed'
    assert remote.data['settings']['redirects'][0]['value'] == 'main.test/Dragonia-Casino/'
    assert len(remote.calls) == 1


def test_delete_then_edit_another_row_and_recreate_deleted_redirect(env):
    db,site,remote=env; prepare(env)
    first=add(env,redirect_source='old.test',redirect_original_source='old.test',redirect_delete=True)
    second=add(env,redirect_source='older.test',redirect_original_source='older.test',redirect_target='main.test/other/')
    assert queue.execute_step(db,first)['status']=='completed'
    assert queue.execute_step(db,second)['status']=='completed'
    assert remote.data['settings']['redirects']==[{'url':'older.test','value':'main.test/other/'}]
    third=add(env,redirect_source='old.test',redirect_target='https://main.test/Returned/')
    assert queue.execute_step(db,third)['status']=='completed'
    assert remote.data['settings']['redirects'][-1]=={'url':'old.test','value':'main.test/Returned/'}
    assert len(remote.calls)==3


def test_delete_rejects_concurrent_row_change(env):
    db,site,remote=env; prepare(env)
    ident=add(env,redirect_source='old.test',redirect_original_source='old.test',redirect_delete=True)
    remote.data['settings']['redirects'][0]['value']='external.test/changed/'
    assert queue.execute_step(db,ident)['status']=='failed'
    assert len(remote.data['settings']['redirects'])==2
    assert remote.calls==[]


def test_retry_old_enqueue_without_new_optional_delete_flag_is_idempotent(env):
    db,site,_=env; prepare(env)
    ident=add(env,redirect_source='old.test',redirect_original_source='old.test',redirect_target='main.test/New/')
    job=db.get(models.BackgroundJob,ident)
    payload=dict(job.payload); request=dict(payload['request']); request.pop('redirect_delete',None)
    job.payload={**payload,'request':request}; db.commit()
    queue.enqueue(db,site,queue.Request.model_validate(request),'test')
    assert len(queue.active(db,site.id))==1
