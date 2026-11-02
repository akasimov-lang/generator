from uuid import uuid4
from collections import Counter
import copy
import pytest
from sqlalchemy import select
from app import models,auto_reglue as auto,project_network as network,domain_redistribution as move
from app import domain_transfer_queue as queue,transfer_report_check as check,mass_action_reports as reports,background_jobs
from app.mass_action_scope import MassActionFilter
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_domain_redistribution import prepare


def check_job(db,run):
    reports.save(db,run.id,MassActionFilter(brand=run.plan['brand'],geo=run.plan['geo']).model_dump(),[{'site_id':run.site_id,'run_id':run.id}],'test')
    job=models.BackgroundJob(id=str(uuid4()),kind=check.KIND,status='running',payload={'brand':run.plan['brand'],'geo':run.plan['geo'],'actor':'test','run_ids':[run.id]})
    db.add(job);db.commit();return job


def test_destination_membership_clears_historic_dns_error_without_polling_old_job(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);auto.execute(db,run.id)
    run.status='partial';run.message='Original native failure';db.commit()
    remote=remotes[target.id]
    def should_not_poll(id):raise AssertionError('Destination presence needs no DNS/job check')
    remote.job_state=should_not_poll
    from app import move_batch
    old_error={'domain':run.plan['domains'][0]['domain'],'code':'DNS','message':'old DNS error','job_id':'old'}
    run.plan={**run.plan,'domain_errors':[old_error]}
    db.add(models.AutoReglueConfig(key=move_batch.failure_key(source.brand,'AZ'),value={'domains':{old_error['domain']:old_error,'unrelated.test':{'job_id':'another'}}}));db.commit()
    job=check_job(db,run);before=sum(len(r.calls) for r in remotes.values())
    result=check.check_run(db,job,run)
    assert run.status=='completed'
    assert all(e['status']=='confirmed' for e in result['domains'])
    assert all('warning' not in e for e in result['domains'])
    assert run.plan['domain_errors']==[]
    assert reports.entry(run)['domain_errors']==[]
    assert move_batch.blocked_domains(db,source.brand,'AZ')=={'unrelated.test'}
    assert sum(len(r.calls) for r in remotes.values())==before
    assert reports.list_reports(db,source.brand,'AZ')[0]['entries'][0]['verification']==result
    assert not queue.listing(db,source.brand,'AZ')['entries']
    assert run.plan['execution_before_report_check']['message']=='Original native failure'


def test_missing_domain_retries_only_that_domain_once_with_receipt_and_queue_history(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);auto.execute(db,run.id)
    missing=run.plan['domains'][0]['domain'];remote=remotes[target.id]
    remote.data['settings']['domains'].remove(missing)
    job=check_job(db,run);before=len(remote.calls)
    result=check.check_run(db,job,run)
    assert all(e['status']=='confirmed' for e in result['domains'])
    creates=remote.calls[before:]
    assert len(creates)==1 and [d['domain'] for d in creates[0][1]['domains']]==[missing]
    assert check.check_run(db,job,run)['domains'][0]['status']=='confirmed'
    assert len(remote.calls)==before+1
    record=db.get(models.AutoReglueConfig,queue.key(run,missing)).value
    assert record['status']=='delivered' and len(record['history'])>=6
    assert not queue.listing(db,source.brand,'AZ')['entries']


def test_failed_retry_keeps_each_domain_with_http_code_in_queue_and_report(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);auto.execute(db,run.id)
    names=[d['domain'] for d in run.plan['domains']]
    remote=remotes[target.id]
    remote.data['settings']['domains']=[d for d in remote.data['settings']['domains'] if d not in names]
    before=len(remote.calls)
    def denied(method,path,payload):remote.calls.append((path,copy.deepcopy(payload)));return 403,{'error':'Permission denied'}
    remote.request=denied
    job=check_job(db,run)
    result=check.check_run(db,job,run)
    assert {e['code'] for e in result['domains']}=={'HTTP_403'}
    assert {e['domain'] for e in result['domains']}==set(names)
    assert len(remote.calls)==before+1
    assert all(v['error_code']=='HTTP_403' for v in queue.listing(db,source.brand,'AZ')['entries'])


def test_partial_batch_deletion_adds_successfully_extracted_domain_only(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);sr=remotes[source.id];tr=remotes[target.id]
    first,second=[d['domain'] for d in run.plan['domains']]
    original=sr.request
    def partial(method,path,payload):
        result=original(method,path,payload)
        if path=='/site-config/delete':sr.data['settings']['domains'].append(first)
        return result
    sr.request=partial
    sr.job_state=lambda id:{'state':'completed','result':{'errorCount':1,'domains':[{'domain':first,'status':'error','errorMessage':'Cannot remove configuration'},{'domain':second,'status':'success'}]}}
    auto.execute(db,run.id)
    assert run.status=='partial' and not tr.calls
    result=check.check_run(db,check_job(db,run),run)
    assert next(e for e in result['domains'] if e['domain']==first)['code']=='SOURCE_NOT_DELETED'
    assert next(e for e in result['domains'] if e['domain']==second)['status']=='confirmed'
    assert [d['domain'] for d in tr.calls[0][1]['domains']]==[second]
    assert first in sr.data['settings']['domains']


def test_queue_capacity_precedes_delete_and_is_independent_per_geo(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    ghost=models.AutoReglueRun(id=str(uuid4()),site_id=target.id,initiator='test',status='failed',plan=copy.deepcopy(run.plan))
    db.add(ghost);db.commit()
    queue.reserve(db,ghost,['g1.test','g2.test','g3.test','g4.test'],str(uuid4()))
    auto.execute(db,run.id)
    assert run.status=='waiting' and 'TRANSFER_QUEUE_FULL' in run.message
    assert all(not r.calls for r in remotes.values())
    other=models.AutoReglueRun(id=str(uuid4()),site_id=target.id,initiator='test',status='failed',plan={**run.plan,'geo':'PL'})
    db.add(other);db.commit()
    queue.reserve(db,other,['pl1.test','pl2.test','pl3.test','pl4.test','pl5.test'],str(uuid4()))
    assert len(queue.listing(db,source.brand,'PL')['entries'])==5
    queue.observe(db,source,{'domains':[]});queue.observe(db,target,{'domains':['g1.test','g2.test','g3.test','g4.test']});db.commit()
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert not queue.listing(db,source.brand,'AZ')['entries']
    assert len(queue.listing(db,source.brand,'PL')['entries'])==5


def test_report_job_idempotency_scope_and_automation_queue(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);auto.execute(db,run.id)
    reports.save(db,run.id,MassActionFilter(brand=source.brand,geo='AZ').model_dump(),[{'site_id':target.id,'run_id':run.id}],'test')
    id=uuid4();filters=MassActionFilter(brand=source.brand,geo='AZ')
    job,fresh=check.prepare(db,id,filters,'test',{source.id,target.id})
    assert fresh and job.payload['run_ids']==[run.id]
    assert check.prepare(db,id,filters,'test',{source.id,target.id})[0].id==job.id
    assert not check.visible(db,job,{target.id})
    sent=[];background_jobs.dispatch_pending(db,lambda *args:sent.append(args))
    assert sent==[(job.id,'automation')]
    assert background_jobs.run_job(db,job.id)['status']=='completed'
    assert background_jobs.run_job(db,job.id)['status']=='skipped'


def test_six_project_cycle_drains_queue_before_main_promotion_without_exceeding_five(pool):
    from test_cross_reglue_batch import reserve,finish
    from app import cross_reglue_batch as batch
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    sites=[add(f'cycle-{n}.test',4,2) for n in range(6)]
    preview=batch.build(db,sites,'test');runs=reserve(db,preview)
    for site in sites:remotes[site.id].job_ready=False
    for run in runs:
        auto.execute(db,run.id)
        assert len(queue.listing(db,'Pin-Up','AZ')['entries'])<=5
    assert len(queue.listing(db,'Pin-Up','AZ')['entries'])==5
    assert sum(len(r.calls) for r in remotes.values())==5
    for site in sites:remotes[site.id].job_ready=True
    finish(db,runs)
    assert all(r.status=='completed' for r in runs)
    assert not queue.listing(db,'Pin-Up','AZ')['entries']
