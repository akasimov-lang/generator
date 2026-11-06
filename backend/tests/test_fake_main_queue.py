from copy import deepcopy
from uuid import uuid4

import httpx
import pytest

from app import background_jobs, models, fake_main_queue as queue, project_network as network
from test_project_network import env


def prepare(env, count=12):
    db,site,remote=env
    paths=['/old-'+chr(97+i)+'/' for i in range(count)]
    remote.data['settings']['alternate'].update(fakeMain=['/cz/',*paths], enableDynamicRoutes=True)
    network.read_network(db,site)
    return paths


def add(db,site,path,action='delete',request_id=None):
    request=queue.Request(request_id=request_id or uuid4(),action=action,path=path)
    queue.enqueue(db,site,request,'anton')
    return str(request.request_id)


def test_enqueue_ten_paths_is_fast_local_idempotent_and_limits_eleventh(env,monkeypatch):
    db,site,remote=env;paths=prepare(env)
    monkeypatch.setattr(network,'Remote',lambda *_:pytest.fail('Enqueue must not contact Webdev'))
    ids=[add(db,site,path) for path in paths[:10]]
    assert len(queue.active(db,site.id))==10
    queue.enqueue(db,site,queue.Request(request_id=ids[0],action='delete',path=paths[0]),'anton')
    add(db,site,paths[0])
    assert len(queue.active(db,site.id))==10
    with pytest.raises(network.NetworkConflict,match='10 страниц'):add(db,site,paths[10])
    db.rollback()
    assert remote.calls==[]


def test_deletions_run_fifo_with_fresh_lists_and_duplicate_delivery_does_not_write(env):
    db,site,remote=env;paths=prepare(env,3)
    first=add(db,site,paths[0]);second=add(db,site,paths[1])
    assert background_jobs.run_job(db,second)['status']=='waiting' and not remote.calls
    assert background_jobs.run_job(db,first)['status']=='completed'
    assert background_jobs.run_job(db,second)['status']=='completed'
    assert len(remote.calls)==2
    assert remote.data['settings']['alternate']['fakeMain']==['/cz/',paths[2]]
    assert remote.data['settings']['alternate']['currentFakeMain']=='/cz/'
    assert background_jobs.run_job(db,first)['status']=='skipped' and len(remote.calls)==2


def test_timeout_checks_receipt_without_resending_and_keeps_later_delete_queued(env):
    db,site,remote=env;paths=prepare(env,2)
    first=add(db,site,paths[0]);second=add(db,site,paths[1]);remote.delayed=True
    assert queue.execute_step(db,first)['status']=='waiting'
    sent=deepcopy(remote.calls[0][2])
    assert queue.execute_step(db,first)['status']=='waiting'
    assert queue.execute_step(db,second)['status']=='waiting'
    assert len(remote.calls)==1
    remote.data['settings']['alternate']=sent['alternate'];remote.delayed=False
    assert queue.execute_step(db,first)['status']=='completed'
    assert queue.execute_step(db,second)['status']=='completed'
    assert len(remote.calls)==2


def test_path_that_becomes_current_while_queued_is_not_deleted_and_next_can_finish(env):
    db,site,remote=env;paths=prepare(env,2)
    first=add(db,site,paths[0]);second=add(db,site,paths[1])
    remote.data['settings']['alternate']['currentFakeMain']=paths[0]
    assert queue.execute_step(db,first)['status']=='failed'
    assert not remote.calls and paths[0] in remote.data['settings']['alternate']['fakeMain']
    assert queue.execute_step(db,second)['status']=='completed'


@pytest.mark.parametrize('path', ['/resources/', '/resources', '/index.php'])
def test_create_and_activate_first_request_finishes_without_second_click(env, path):
    db,site,remote=env;prepare(env,1)
    ident=add(db,site,path,'create')
    assert not remote.calls
    assert queue.execute_step(db,ident)['status']=='completed'
    assert path in remote.data['settings']['alternate']['fakeMain']
    assert remote.data['settings']['alternate']['currentFakeMain']==path
    assert queue.snapshot(db,site)['items'][0]['message']=='Создано и назначено.'
    calls=len(remote.calls)
    assert queue.execute_step(db,ident)['status']=='skipped' and len(remote.calls)==calls


def test_create_delayed_confirmation_continues_after_browser_closed(env):
    db,site,remote=env;prepare(env,1);remote.delayed=True
    ident=add(db,site,'/resources/','create')
    assert queue.execute_step(db,ident)['status']=='waiting'
    request=deepcopy(remote.calls[0][2]);remote.data['settings']['alternate']=request['alternate'];remote.delayed=False
    assert background_jobs.run_job(db,ident)['status']=='completed'
    assert remote.data['settings']['alternate']['currentFakeMain']=='/resources/'
    assert len([c for c in remote.calls if c[1].endswith('update-value')])==1


def test_queue_get_is_read_only_and_request_id_cannot_target_another_path(env,monkeypatch):
    db,site,remote=env;paths=prepare(env,2);ident=add(db,site,paths[0])
    monkeypatch.setattr(network,'Remote',lambda *_:pytest.fail('GET must not contact Webdev'))
    assert queue.snapshot(db,site)['active_count']==1
    with pytest.raises(network.NetworkConflict):add(db,site,paths[1],request_id=ident)
    assert remote.calls==[]


def test_other_site_queue_is_not_exposed_and_request_id_cannot_be_reused(env):
    db,site,remote=env;paths=prepare(env,1);ident=add(db,site,paths[0])
    other=models.Site(name='other.test',base_url='https://other.test',publication_endpoint='/publish');db.add(other);db.commit()
    assert queue.snapshot(db,other)['items']==[]
    with pytest.raises(network.NetworkConflict):add(db,other,paths[0],request_id=ident)


def test_current_path_rejected_before_job_is_created(env):
    db,site,remote=env;prepare(env,1)
    with pytest.raises(ValueError,match='текущей'):add(db,site,'/cz/')
    assert queue.active(db,site.id)==[] and remote.calls==[]


def test_worker_recovers_after_receipt_commit_without_repeating_write(env):
    db,site,remote=env;paths=prepare(env,1);ident=add(db,site,paths[0])
    remote.fail=httpx.ReadTimeout('lost response')
    assert queue.execute_step(db,ident)['status']=='waiting'
    assert db.get(models.NetworkOperation,ident) is not None
    remote.fail=None
    assert queue.execute_step(db,ident)['status']=='waiting' and len(remote.calls)==1


def test_dispatcher_delivers_queued_fake_page_tasks(env):
    db,site,remote=env;paths=prepare(env,1);ident=add(db,site,paths[0]);sent=[]
    background_jobs.dispatch_pending(db,lambda job,worker_queue:sent.append((job,worker_queue)))
    assert sent==[(ident,'cache_sync')]


def test_create_updates_old_path_in_head_before_queue_reports_success(env):
    db,site,remote=env;prepare(env,1)
    remote.data['head']['alternateMarkup']='<link rel="alternate" hreflang="cs-CZ" href="https://main.test/cz/" />'
    remote.data['head']['canonicalFakeMainMarkup']='<link rel="canonical" href="https://{{settings.canon}}/cz/" />'
    network.read_network(db,site)
    ident=add(db,site,'/resources/','create')
    assert queue.execute_step(db,ident)['status']=='completed'
    assert remote.data['settings']['alternate']['currentFakeMain']=='/resources/'
    assert '/resources/' in remote.data['head']['alternateMarkup']
    assert '/resources/' in remote.data['head']['canonicalFakeMainMarkup']
    assert len(remote.calls)==2
    queue.execute_step(db,ident)
    assert len(remote.calls)==2


def test_missing_fake_page_list_is_not_treated_as_confirmed_deletion(env):
    db,site,remote=env;paths=prepare(env,1);ident=add(db,site,paths[0])
    remote.data['settings']['alternate']['fakeMain']=None
    assert queue.execute_step(db,ident)['status']=='waiting'
    assert not remote.calls and db.get(models.BackgroundJob,ident).status=='queued'


def test_cancel_unconfirmed_enqueue_prevents_late_delivery(env):
    db,site,remote=env;prepare(env,1)
    request=queue.Request(request_id=uuid4(),action='create',path='/late/')
    result=queue.cancel(db,site,request,'anton')
    assert result['active_count']==0 and result['items'][0]['status']=='cancelled'
    queue.enqueue(db,site,request,'anton')
    assert queue.execute_step(db,str(request.request_id))['status']=='skipped'
    assert not remote.calls


def test_cancel_waiting_request_preserves_receipt_until_remote_outcome_is_known(env):
    db,site,remote=env;paths=prepare(env,2)
    first=add(db,site,paths[0]);second=add(db,site,paths[1]);remote.delayed=True
    assert queue.execute_step(db,first)['status']=='waiting'
    receipt=db.get(models.NetworkOperation,first)
    queue.cancel(db,site,queue.Request(request_id=first,action='delete',path=paths[0]),'anton')
    assert receipt.status=='pending' or receipt.status=='unknown'
    assert receipt.request_payload['queue_cancelled_at']
    assert queue.execute_step(db,first)['status']=='skipped'
    remote.delayed=False
    assert queue.execute_step(db,second)['status']=='waiting'
    remote.data['settings']['alternate']=deepcopy(remote.calls[0][2]['alternate'])
    assert queue.execute_step(db,second)['status']=='completed'
    assert len(remote.calls)==2


def test_select_existing_path_updates_canonical_and_alternates_with_slash_variants(env):
    db,site,remote=env;paths=prepare(env,1)
    remote.data['settings']['alternate']['currentFakeMain']='/cz'
    remote.data['head'].update(
        alternateMarkup='<link rel="alternate" hreflang="cs" href="https://main.test/cz/" />',
        canonicalDefaultMarkup='<link rel="canonical" href="https://{{settings.canon}}/cz" />',
        canonicalFakeMainMarkup='<link rel="canonical" href="https://{{settings.canon}}/cz/" />')
    network.read_network(db,site)
    ident=add(db,site,paths[0],'select')
    assert queue.execute_step(db,ident)['status']=='completed'
    assert remote.data['settings']['alternate']['currentFakeMain']==paths[0]
    assert all(paths[0] in remote.data['head'][k] for k in ('alternateMarkup','canonicalDefaultMarkup','canonicalFakeMainMarkup'))
    assert '{{settings.canon}}' in remote.data['head']['canonicalFakeMainMarkup']
    assert len(remote.calls)==2


def test_cancel_cannot_target_another_projects_request(env):
    db,site,remote=env;paths=prepare(env,1);ident=add(db,site,paths[0])
    other=models.Site(name='other.test',base_url='https://other.test',publication_endpoint='/')
    db.add(other);db.commit()
    with pytest.raises(network.NetworkConflict,match='другому запросу'):
        queue.cancel(db,other,queue.Request(request_id=ident,action='delete',path=paths[0]),'anton')
    assert db.get(models.BackgroundJob,ident).status=='queued' and not remote.calls
