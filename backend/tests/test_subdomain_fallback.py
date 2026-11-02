from copy import deepcopy
from uuid import uuid4
import pytest
from app import models, auto_reglue as auto, cross_reglue as cross, cross_reglue_batch as batch, project_network as network, subdomain_fallback as fallback
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool


def failed_child(pool):
    db, source, target, remotes, add = pool
    state = network.read_network(db, source)
    cfg = auto.config(db); cfg.scheme_mode='clean'; auto.save_config(db,cfg)
    plan = cross.make_plan(cfg,source,state,source,state,'child.main.test',db=db)
    bid=str(uuid4());jid=str(uuid4());rid=str(uuid4())
    plan.update(local_target=True,create_subdomain='child.main.test',parent_domain='main.test',batch_id=bid,domain_type='drop',main_target_kind='sub_drop',mass_filter={'brand':'Pin-Up','geo':'AZ'})
    run=models.AutoReglueRun(id=rid,site_id=source.id,initiator='test',status='partial',phase='cross_create_subdomains',plan={**plan,'list_launch_id':jid})
    other=add('untouched.test',geo='HU');otherplan={'site_id':other.id,'source_site_id':other.id,'new_main':'untouched-next.test','local_target':True,'domain_type':'newreg'}
    job=models.BackgroundJob(id=jid,kind='mass_reglue_list',status='queued',payload={'actor':'test','site_ids':[source.id,other.id],'allowed':None},result={'groups':[{'site_ids':[source.id],'plans':[plan],'batch_id':bid,'status':'waiting'},{'site_ids':[other.id],'plans':[otherplan],'status':'waiting'}],'items':{source.id:{'run_id':rid,'status':'partial'},other.id:{'status':'queued'}},'sent':{}})
    manifest=models.AutoReglueConfig(key=batch.key(bid),value={'plans':[plan],'run_ids':{source.id:rid}})
    result={'state':'completed','result':{'errorCount':1,'successCount':0,'domains':[{'domain':'child.main.test','status':'error','logs':['ОШИБКА: Request failed with status code 502']}]}}
    remotes[source.id].job_state=lambda _:deepcopy(result)
    op=models.NetworkOperation(id=cross.receipt_id(run,'create_subdomains'),site_id=source.id,action='create_subdomains',status='failed',initiator='test',request_payload={'job_id':'child-job','auto_run_id':rid})
    db.add_all([run,job,manifest,op]);db.commit()
    return db,source,remotes,run,job,manifest,result


def test_failed_child_changes_only_own_scheme_without_extra_subdomain(pool):
    db,site,remotes,run,job,manifest,result=failed_child(pool)
    before=deepcopy(job.result['groups'][1]);old=deepcopy(run.plan)
    assert fallback.replace_failed(db,run.id)
    assert run.status=='queued' and run.phase=='prepared'
    assert run.plan['new_main']=='next.test'
    assert 'create_subdomain' not in run.plan and 'parent_domain' not in run.plan
    assert run.plan['subdomain_fallback']['old_plan']==old
    assert job.result['groups'][1]==before
    assert manifest.value['plans'][0]['new_main']=='next.test'
    batch.authorize(db,run)
    assert not fallback.replace_failed(db,run.id)
    assert all(not r.calls for r in remotes.values())


@pytest.mark.parametrize('case',['pending','missing','different_domain','main_changed','already_reserved','later_phase','cancelled'])
def test_no_fallback_for_uncertain_or_advanced_operation(pool,case):
    db,site,remotes,run,job,manifest,result=failed_child(pool)
    if case=='pending':result['state']='running'
    if case=='missing':result.clear();result['state']='not_found'
    if case=='different_domain':result['result']['domains'][0]['domain']='other.test'
    if case=='main_changed':remotes[site.id].data['settings']['canon']='other.test'
    if case=='already_reserved':remotes[site.id].data['settings']['reserve']=run.plan['new_main']
    if case=='later_phase':run.phase='cross_reglue'
    if case=='cancelled':run.status='cancelled'
    db.commit();before=deepcopy(run.plan)
    assert not fallback.replace_failed(db,run.id)
    assert run.plan==before
    assert all(not r.calls for r in remotes.values())
