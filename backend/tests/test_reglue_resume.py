from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
from app import models, project_network as network, auto_reglue as auto, cross_reglue as cross
from app.fake_main_head import receipt_id
from app.reglue_resume import reconcile
from test_project_network import env, change
from test_fake_main_head import prepare, parent
from test_cross_reglue import setup, launch


def attach_run(db, site, op):
    run = models.AutoReglueRun(id=str(uuid4()), site_id=site.id, status='partial', phase='cross_create_fake_main',
        initiator='test', plan={'old_main':'main.test', 'new_main':'next.test',
                              'list_launch_id':str(uuid4()), 'execution_mode':'cross_network'})
    db.add(run); db.flush()
    op.request_payload = {**op.request_payload, 'auto_run_id':run.id}
    db.commit()
    return run


def test_added_domain_waits_fifteen_seconds_before_reserve(setup, monkeypatch):
    from app import reglue_settle
    db, source, target, sr, tr = setup
    monkeypatch.setattr(reglue_settle, 'SECONDS', 15)
    run = launch(setup)
    auto.execute(db, run.id)
    assert run.status == 'waiting' and '15 секунд' in run.message
    assert tr.data['settings']['canon'] == 'target.test'
    assert not any('reserve' in payload for path, payload in tr.calls)
    op = db.get(models.NetworkOperation, cross.receipt_id(run, 'create_domains'))
    confirmed = datetime.fromisoformat(op.request_payload['provisioning_confirmed_at'])
    assert not reglue_settle.ready(db, run, op, {'domains':['next.test']}, now=confirmed+timedelta(seconds=14))
    op.request_payload = {**op.request_payload, 'provisioning_confirmed_at':(confirmed-timedelta(seconds=16)).isoformat()};db.commit()
    auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert len([p for p, _ in tr.calls if p == '/site-config/create']) == 1


def test_reserve_must_be_confirmed_before_reglue(setup):
    db, source, target, sr, tr = setup
    original = tr.request
    def delay_reserve(method, path, payload):
        if path.endswith('update-value') and 'reserveOption' in payload:
            tr.calls.append((path, deepcopy(payload)))
            return 200, {'ok':True}
        return original(method, path, payload)
    tr.request = delay_reserve
    run = launch(setup);auto.execute(db, run.id)
    assert run.status == 'waiting' and tr.data['settings']['canon'] == 'target.test'
    assert not db.get(models.NetworkOperation, cross.receipt_id(run, 'reglue'))
    tr.data['settings'].update(reserve='next.test', reserveOption='next.test')
    auto.execute(db, run.id)
    assert run.status == 'completed'
    assert len([p for p, d in tr.calls if 'reserveOption' in d]) == 1


def test_restart_error_after_saved_fake_path_finishes_head_without_recreating(env):
    db, site, remote = env
    state = prepare(env)
    remote.delayed = True
    change(env,'select_fake_main',state['revision'],fake_main_path='/lemons/')
    op=parent(db);run=attach_run(db,site,op)
    remote.data['settings']['alternate']=deepcopy(op.request_payload['alternate'])
    op.status='failed';op.message='[PM2][ERROR] Process not found';op.response_status=400;db.commit()
    remote.delayed=False
    network.read_network(db,site)
    assert op.status=='confirmed' and run.plan['read_retryable']
    assert op.request_payload['recovered_response']['status']==400
    assert len(remote.calls)==2
    network.read_network(db,site)
    assert len(remote.calls)==2


def test_failed_write_not_applied_or_cancelled_is_not_recovered(env):
    db,site,remote=env;state=prepare(env);remote.delayed=True
    change(env,'select_fake_main',state['revision'],fake_main_path='/lemons/')
    op=parent(db);run=attach_run(db,site,op);op.status='failed';db.commit()
    assert not reconcile(db,site,network.observe(db,site,remote.project()))
    remote.data['settings']['alternate']=deepcopy(op.request_payload['alternate'])
    run.status='cancelled';db.commit()
    assert not reconcile(db,site,network.observe(db,site,remote.project()))
    assert op.status=='failed' and len(remote.calls)==1


def test_idempotent_head_502_retry_is_bounded_and_preserves_external_edits(env):
    db,site,remote=env;state=prepare(env)
    original=remote.request
    def fail_head(method,path,payload):
        if path.endswith('update-head'):
            remote.calls.append((method,path,deepcopy(payload)))
            httpx.Response(502,request=httpx.Request(method,'https://test.test'+path)).raise_for_status()
        return original(method,path,payload)
    remote.request=fail_head
    change(env,'select_fake_main',state['revision'],fake_main_path='/lemons/')
    op=parent(db);attach_run(db,site,op);child=db.get(models.NetworkOperation,receipt_id(op))
    child.updated_at=datetime.now(timezone.utc)-timedelta(minutes=1);db.commit()
    network.read_network(db,site)
    assert len(child.request_payload['head_retries'])==1
    count=len(remote.calls)
    network.read_network(db,site)
    assert len(remote.calls)==count  # No immediate hot loop.
    child.request_payload={**child.request_payload,'head_retries':[{'at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}]};db.commit()
    remote.data['head']['alternateMarkup']='editor change'
    network.read_network(db,site)
    assert len(remote.calls)==count
