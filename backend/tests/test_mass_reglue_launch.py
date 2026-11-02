from datetime import datetime, timezone, timedelta
from uuid import uuid4, uuid5, UUID
import pytest
from sqlalchemy import select
from app import models, auto_reglue as auto, mass_reglue_launch as launch, reglue_history as history
from app.project_network import NetworkConflict
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, finish


def start(db, ids, allowed=None):
    return launch.enqueue(db, uuid4(), ids, 'test', allowed)


def test_week_uses_monday_moscow_and_boundaries():
    now=datetime(2026,10,25,20,59,tzinfo=timezone.utc)
    assert history.week_start(now)==datetime(2026,10,18,21,tzinfo=timezone.utc)
    site=models.Site(last_reglue_at=datetime(2026,10,18,20,59,tzinfo=timezone.utc))
    assert not history.changed_this_week(site,now)
    site.last_reglue_at=datetime(2026,10,18,21,tzinfo=timezone.utc)
    assert history.changed_this_week(site,now)
    assert not history.changed_this_week(site,now+timedelta(minutes=1))


def test_list_keeps_every_project_and_splits_at_configured_limit(pool):
    db,source,target,remotes,add=pool
    cfg=auto.config(db);cfg.max_projects=2;auto.save_config(db,cfg)
    projects=[add(f'project-{i}.test',geo='HU') for i in range(5)]
    excluded=add('off.test');excluded.reglue_participation=False
    done=add('done.test');done.last_reglue_at=datetime.now(timezone.utc)
    other=add('not-mass.test',status='working');db.commit()
    job=start(db,[p.id for p in projects]+[excluded.id,done.id,other.id])
    assert len(job.result['items'])==8
    assert [len(g['site_ids']) for g in job.result['groups']]==[2,2,1]
    assert launch.view(db,job)['counts']['skipped']==3
    assert not any(r.calls for r in remotes.values())


def test_idempotent_and_overlapping_launch_and_grants(pool):
    db,source,target,remotes,add=pool
    rid=uuid4();job=launch.enqueue(db,rid,[target.id],'test')
    assert launch.enqueue(db,rid,[target.id],'test').id==job.id
    with pytest.raises(ValueError):launch.enqueue(db,rid,[source.id],'test')
    with pytest.raises(NetworkConflict):start(db,[target.id])
    with pytest.raises(ValueError):start(db,[source.id],{target.id})


def test_cross_list_executes_once_and_sets_confirmation_date(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);sent=[]
    launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1
    run=db.get(models.AutoReglueRun,sent[0])
    assert run.plan['list_launch_id']==job.id
    launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1
    finish(db,[run])
    assert target.last_reglue_at
    original=history.utc(target.last_reglue_at)
    ops=list(db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id==target.id,models.NetworkOperation.action=='reglue')))
    assert len(ops)==1 and ops[0].request_payload['auto_run_id']==run.id
    launch.require_run(db,run)  # Own confirmed Main must not block its remaining steps.
    history.confirm(target,ops[0]);assert history.utc(target.last_reglue_at)==original
    launch.execute_step(db,job.id,sent.append)
    assert job.status=='completed' and launch.view(db,job)['counts']['completed']==1
    new=start(db,[target.id]);assert new.status=='completed' and launch.view(db,new)['counts']['skipped']==1


def test_participation_and_week_are_rechecked_after_enqueue(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);target.reglue_participation=False;db.commit()
    launch.execute_step(db,job.id,lambda _:pytest.fail('Must not dispatch'))
    assert job.status=='completed'
    assert launch.view(db,job)['counts']['skipped']==1
    assert not any(r.calls for r in remotes.values())


def test_off_target_never_mutates_and_off_donor_not_selected(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);sent=[];launch.execute_step(db,job.id,sent.append)
    target.reglue_participation=False;db.commit()
    auto.execute(db,sent[0])
    assert not any(r.calls for r in remotes.values())
    assert db.get(models.AutoReglueRun,sent[0]).status=='failed'


def test_weekly_guard_before_remote_changes(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);sent=[];launch.execute_step(db,job.id,sent.append)
    target.last_reglue_at=datetime.now(timezone.utc);db.commit()
    auto.execute(db,sent[0])
    assert not any(r.calls for r in remotes.values())
    assert db.get(models.AutoReglueRun,sent[0]).status=='failed'


def test_broker_failure_retries_same_run(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id])
    def fail(_):raise RuntimeError('broker down')
    launch.execute_step(db,job.id,fail)
    assert job.status=='queued' and job.error
    sent=[];launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1
    assert len(list(db.scalars(select(models.AutoReglueRun))))==1


def test_changed_settings_do_not_silently_change_intent(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);cfg=auto.config(db);cfg.scheme_mode='clean';auto.save_config(db,cfg)
    launch.execute_step(db,job.id,lambda _:pytest.fail('Changed settings'))
    assert launch.view(db,job)['counts']['skipped']==1
    assert not any(r.calls for r in remotes.values())


def test_backfill_only_confirmed_reglue_receipts(pool):
    db,source,target,remotes,add=pool
    at=datetime(2026,9,1,12,tzinfo=timezone.utc)
    db.add(models.NetworkOperation(id=str(uuid4()),site_id=target.id,action='reglue',status='confirmed',initiator='test',request_payload={'source_domain':'a.test','reserve':'b.test','confirmed_at':at.isoformat()}))
    db.add(models.NetworkOperation(id=str(uuid4()),site_id=target.id,action='reglue',status='failed',initiator='test',request_payload={}))
    db.commit();history.backfill(db)
    assert history.utc(target.last_reglue_at)==at


def test_restart_after_claiming_batch_recovers_same_runs(pool, monkeypatch):
    from app import cross_reglue_batch as batch
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);original=batch.reserve
    def crash(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('worker stopped after committing claims')
    monkeypatch.setattr(batch,'reserve',crash)
    with pytest.raises(RuntimeError):launch.execute_step(db,job.id,lambda _:pytest.fail('Not dispatched yet'))
    db.rollback()
    monkeypatch.setattr(batch,'reserve',original)
    sent=[];launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1
    assert len(list(db.scalars(select(models.AutoReglueRun))))==1
    finish(db,[db.get(models.AutoReglueRun,sent[0])])
    launch.execute_step(db,job.id,sent.append)
    assert launch.view(db,job)['counts']['completed']==1


def test_within_network_list(pool):
    db,source,target,remotes,add=pool
    source.cache_geo='AZ';source.cache_language='az';db.commit()
    cfg=auto.config(db);cfg.execution_mode='within_network';cfg.scheme_mode='clean';cfg.apply_domain_settings=True;cfg.domain_settings=auto.DomainOptions(domain_layout='root_main',parent_kind='newreg');auto.save_config(db,cfg)
    job=start(db,[source.id]);sent=[]
    launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1, str(launch.view(db,job)["items"])
    run=db.get(models.AutoReglueRun,sent[0]);finish(db,[run])
    launch.execute_step(db,job.id,sent.append)
    assert job.status=='completed' and source.last_reglue_at


def test_disabled_donor_is_excluded_before_planning(pool):
    db,source,target,remotes,add=pool
    source.reglue_participation=False;db.commit()
    job=start(db,[target.id]);sent=[]
    launch.execute_step(db,job.id,sent.append)
    assert not sent
    assert not any(r.calls for r in remotes.values())
    assert launch.view(db,job)['counts']['skipped']==1


def test_participation_api_persists_and_checks_access():
    from test_auto_reglue import make_client
    from app.auto_reglue_api import router
    from app.security import require_auth
    client,sessions=make_client();client.app.include_router(router,prefix='/api')
    with sessions() as db:site_id=db.scalar(select(models.Site.id))
    response=client.patch(f'/api/auto-reglue/projects/{site_id}/participation',json={'enabled':False})
    assert response.status_code==200 and response.json()['reglue_participation'] is False
    assert client.get('/api/sites').json()[0]['reglue_participation'] is False
    client.app.dependency_overrides[require_auth]=lambda:{'id':'limited','username':'limited','allowed_site_ids':[]}
    assert client.patch(f'/api/auto-reglue/projects/{site_id}/participation',json={'enabled':True}).status_code==404
    with sessions() as db:assert db.get(models.Site,site_id).reglue_participation is False
    assert client.get('/api/auto-reglue/list-launch').json() is None


@pytest.mark.parametrize('blocked_status', ['waiting', 'failed', 'partial'])
def test_independent_groups_are_dispatched_while_previous_group_waits(pool, blocked_status):
    from app import auto_pilot
    db,source,target,remotes,add=pool
    cfg=auto.config(db);cfg.execution_mode='within_network';cfg.scheme_mode='clean';cfg.apply_domain_settings=True
    cfg.domain_settings=auto.DomainOptions(domain_layout='root_main',parent_kind='newreg');auto.save_config(db,cfg)
    second=add('parallel.test',geo='HU')
    source.cache_language='az';source.cache_geo='AZ'
    second.cache_language='hu'
    # Give the second project its own unused root, independent of the first GEO.
    remote=remotes[second.id]
    remote.data['settings']['domains']=['parallel.test','parallel-next.test']
    second.domain_types={'parallel.test':'newreg','parallel-next.test':'newreg'}
    db.commit()
    job=start(db,[source.id,second.id]);sent=[]
    def send(rid):
        sent.append(rid)
        if len(sent)==1:
            run=db.get(models.AutoReglueRun,rid)
            run.status=blocked_status;run.message='DNS не подтверждён';db.commit()
    launch.execute_step(db,job.id,send)
    assert len(sent)==2, launch.view(db,job)
    assert job.status=='queued'
    assert {db.get(models.AutoReglueRun,rid).site_id for rid in sent}=={source.id,second.id}
    launch.execute_step(db,job.id,sent.append)
    assert len(sent)==2  # No duplicate task dispatch on the next poll.


def test_mass_preview_creates_new_path_instead_of_current(pool):
    from app import auto_pilot
    db,source,target,remotes,add=pool
    source.cache_geo='AZ';source.cache_language='az';target.project_status='working';db.commit()
    cfg=auto.config(db);cfg.execution_mode='within_network';cfg.scheme_mode='preserve';cfg.apply_domain_settings=True
    cfg.domain_settings=auto.DomainOptions(domain_layout='root_main',parent_kind='newreg',x_default_use_newreg=True,create_subdomains=True,use_current_fake_main=True)
    auto.save_config(db,cfg)
    remotes[source.id].data['alternate']={'fakeMain':['/old/'],'currentFakeMain':'/old/','enableFakeMain':True}
    job=auto_pilot.create(db,uuid4(),{'username':'test','allowed_site_ids':None})
    launch.execute_step(db,job.id,lambda _:pytest.fail('Preview must not execute'))
    plans=[p for g in job.result['groups'] for p in g.get('plans',[])]
    assert len(plans)==1,job.result
    assert plans[0]['create_fake_main_path'] not in (None,'','/old/')
    assert not any(r.calls for r in remotes.values())


def test_resumed_run_is_dispatched_from_saved_phase_once(pool):
    db,source,target,remotes,add=pool
    job=start(db,[target.id]);sent=[]
    launch.execute_step(db,job.id,sent.append)
    run=db.get(models.AutoReglueRun,sent[0]);run.status='queued';run.phase='cross_create_fake_main'
    result=dict(job.result);result['sent']={};job.result=result;db.commit()
    launch.execute_step(db,job.id,sent.append)
    assert sent==[run.id,run.id]
    launch.execute_step(db,job.id,sent.append)
    assert len(sent)==2 and run.phase=='cross_create_fake_main'
