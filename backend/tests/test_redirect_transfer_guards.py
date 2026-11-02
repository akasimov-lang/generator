import copy
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select
from app import models,project_network as network,auto_reglue as auto,move_plus2 as plus,cross_reglue as cross,domain_redistribution as move
from app.domain_redirects import require_transfer_free,retarget_redirects
from app.reglue_redirects import receipt_id
from test_project_network import env,change
from test_cross_reglue import setup,launch
from test_cross_reglue_batch import pool
from test_move_plus2 import init


def state(rows):return {'domain_redirects':rows,'has_domain_redirects':True,'redirects_verified':True}

@pytest.mark.parametrize('domain',['old.test','main.test','www.old.test','www.main.test'])
def test_both_redirect_endpoints_and_www_variants_are_protected(domain):
 with pytest.raises(ValueError,match='DOMAIN_REDIRECT'):require_transfer_free(state([{'url':'old.test','value':'main.test'}]),[domain])
 require_transfer_free(state([{'url':'old.test','value':'main.test'}]),['free.test'])


def test_missing_fresh_redirect_data_blocks_despite_cached_snapshot():
 cached={**state([]),'redirects_verified':False}
 with pytest.raises(ValueError,match='REDIRECTS_NOT_VERIFIED'):require_transfer_free(cached,['free.test'])


def test_move_filters_redirected_newregs_and_uses_other_candidates(pool):
 db,sites,remotes,filters,roots=init(pool)
 donor=sites[0];names=list(donor.domain_types)
 remotes[donor.id].data['settings']['redirects']=[{'url':names[0],'value':remotes[donor.id].data['settings']['canon']}]
 run,_=plus.prepare(db,uuid4(),filters,[s.id for s in sites],'test')
 assert run.plan['source_site_id']==donor.id
 assert names[0] not in [d['domain'] for d in run.plan['domains']]
 auto.execute(db,run.id)
 assert run.status=='completed',run.message
 assert names[0] in remotes[donor.id].data['settings']['domains']


def test_new_redirect_after_plan_blocks_batch_before_any_delete(pool):
 db,sites,remotes,filters,roots=init(pool)
 run,_=plus.prepare(db,uuid4(),filters,[s.id for s in sites],'test')
 donor=remotes[run.plan['source_site_id']];blocked=run.plan['domains'][0]['domain']
 donor.data['settings']['redirects']=[{'url':blocked,'value':donor.data['settings']['canon']}]
 auto.execute(db,run.id)
 assert run.status=='failed' and 'DOMAIN_REDIRECT' in run.message
 assert all(not r.calls for r in remotes.values())
 assert db.get(models.NetworkOperation,move.receipt(run,'delete_batch')) is None


def test_redirect_added_between_read_and_deletion_is_blocked_at_write(pool):
 db,sites,remotes,filters,roots=init(pool)
 run,_=plus.prepare(db,uuid4(),filters,[s.id for s in sites],'test')
 source=db.get(models.Site,run.plan['source_site_id']);fresh=network.read_network(db,source)
 domain=run.plan['domains'][0]['domain']
 remotes[source.id].data['settings']['redirects']=[{'url':domain,'value':fresh['canon']}]
 with pytest.raises(ValueError,match='DOMAIN_REDIRECT'):
  network.change_network(db,source,network.NetworkChange(request_id=move.receipt(run,'delete_batch'),action='delete_domain',revision=fresh['revision'],domains=[d['domain'] for d in run.plan['domains']]),'test',auto_run_id=run.id)
 assert not remotes[source.id].calls


def test_cross_reglue_skips_redirect_domains_and_rechecks_before_extract(setup):
 db,source,target,sr,tr=setup
 sr.data['settings']['redirects']=[{'url':'next.test','value':'main.test'}]
 with pytest.raises(ValueError):launch(setup)
 sr.data['settings']['redirects']=[]
 run=launch(setup)
 sr.data['settings']['redirects']=[{'url':'next.test','value':'main.test'}]
 auto.execute(db,run.id)
 assert run.status=='failed' and 'DOMAIN_REDIRECT' in run.message
 assert not sr.calls and not tr.calls


def reglue(env,rows):
 db,site,remote=env
 remote.data['settings']['redirects']=copy.deepcopy(rows)
 before=network.read_network(db,site)
 request=network.NetworkChange(request_id=uuid4(),action='reglue',revision=before['revision'],domain='reserve.test')
 return network.change_network(db,site,request,'anton'),request


def test_reglue_retargets_terminal_endpoints_preserves_chain_and_custom_destination(env):
 rows=[{'url':'a.test','value':'b.test','extra':'keep'},{'url':'b.test','value':'main.test'},{'url':'reserve.test','value':'b.test'},{'url':'www.reserve.test','value':'main.test'},{'url':'custom.test','value':'external.test'}]
 result,request=reglue(env,rows)
 wanted=[rows[0],{'url':'b.test','value':'reserve.test'},{'url':'www.reserve.test','value':'reserve.test'},rows[4]]
 assert result['canon']=='reserve.test' and result['domain_redirects']==wanted
 parent=next(op for op in result['operations'] if op['id']==str(request.request_id))
 assert parent['status']=='confirmed' and parent['redirects_before']==rows and parent['redirects_after']==wanted
 assert [path for _,path,_ in env[2].calls]==['/projects/update-reglue','/projects/update-value']
 assert env[2].calls[-1][2]=={'folder':env[1].name,'redirects':wanted}
 count=len(env[2].calls)
 network.change_network(env[0],env[1],request,'anton');network.read_network(env[0],env[1])
 assert len(env[2].calls)==count


def test_native_reglue_already_updates_redirects_without_extra_write(env):
 remote=env[2];native=remote.request
 def request(method,path,payload):
  result=native(method,path,payload)
  if path.endswith('update-reglue'):remote.data['settings']['redirects']=[{'url':'old.test','value':payload['reserve']}]
  return result
 remote.request=request
 result,_=reglue(env,[{'url':'old.test','value':'main.test'}])
 assert all(path!='/projects/update-value' for _,path,_ in remote.calls)
 assert next(o for o in result['operations'] if o['action']=='reglue')['status']=='confirmed'


def test_redirect_timeout_never_replays_reglue_or_redirect_write_and_no_early_indexing(env):
 db,site,remote=env;native=remote.request
 def request(method,path,payload):
  if path.endswith('update-value') and 'redirects' in payload:
   remote.calls.append((method,path,payload));raise httpx.ReadTimeout('unknown write result')
  return native(method,path,payload)
 remote.request=request
 result,payload=reglue(env,[{'url':'old.test','value':'main.test'}])
 parent=db.get(models.NetworkOperation,str(payload.request_id))
 assert parent.status=='unknown' and result['canon']=='reserve.test'
 assert not list(db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.action=='indexing')))
 count=len(remote.calls)
 network.read_network(db,site);network.read_network(db,site)
 assert len(remote.calls)==count
 remote.data['settings']['redirects']=[{'url':'old.test','value':'reserve.test'},{'url':'extra.test','value':'other.test'}]
 done=network.read_network(db,site)
 assert db.get(models.NetworkOperation,parent.id).status=='confirmed'
 assert db.get(models.NetworkOperation,receipt_id(parent)).status=='confirmed'
 assert len(remote.calls)==count
 assert any(o['action']=='indexing' for o in done['operations'])


def test_crash_after_main_change_resumes_only_redirect_step(env):
 db,site,remote=env
 remote.data['settings']['canon']='reserve.test'
 remote.data['settings']['redirects']=[{'url':'old.test','value':'main.test'}]
 parent=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='reglue',status='pending',initiator='anton',request_payload={'reserve':'reserve.test','source_domain':'main.test','redirect_sync':True})
 db.add(parent);db.commit()
 done=network.read_network(db,site)
 assert done['domain_redirects']==[{'url':'old.test','value':'reserve.test'}]
 assert [path for _,path,_ in remote.calls]==['/projects/update-value']
 assert db.get(models.NetworkOperation,parent.id).status=='confirmed'


def test_redirect_failure_leaves_main_changed_but_operation_not_success(env):
 remote=env[2];native=remote.request
 def request(method,path,payload):
  if path.endswith('update-value') and 'redirects' in payload:
   remote.calls.append((method,path,payload));return 200,{'success':False,'message':'Denied'}
  return native(method,path,payload)
 remote.request=request
 result,payload=reglue(env,[{'url':'old.test','value':'main.test'}])
 assert result['canon']=='reserve.test'
 parent=env[0].get(models.NetworkOperation,str(payload.request_id))
 assert parent.status=='failed' and 'Main изменён' in parent.message
 assert result['domain_redirects']==[{'url':'old.test','value':'main.test'}]


def test_automatic_same_network_reglue_updates_redirects(env,monkeypatch):
 db,site,remote=env
 site.brand='Pin-Up';site.cache_geo='AZ';site.cache_language='az';site.project_status='mass_actions'
 site.domain_types={'reserve.test':'newreg','next.test':'newreg'};db.commit()
 auto.save_config(db,auto.GlobalConfig(enabled=True,scheme_mode='clean'))
 auto.save_config(db,auto.ProjectConfig(enabled=True,domain_layout='root_main',parent_kind='newreg',language='az'),site.id)
 remote.data['settings']['redirects']=[{'url':'old-redirect.test','value':'main.test'}]
 monkeypatch.setattr(auto,'verify_pages',lambda urls:None)
 plan=auto.preview(db,site)
 run,_=auto.prepare_run(db,site,uuid4(),plan['preview_token'],'test','mass')
 auto.execute(db,run.id)
 assert run.status=='completed',run.message
 assert remote.data['settings']['redirects']==[{'url':'old-redirect.test','value':run.plan['new_main']}]


def test_cross_reglue_updates_target_redirects_after_promotion(setup):
 db,source,target,sr,tr=setup
 tr.data['settings']['redirects']=[{'url':'old-redirect.test','value':'target.test'}]
 run=launch(setup);auto.execute(db,run.id)
 assert run.status=='completed',run.message
 assert tr.data['settings']['redirects']==[{'url':'old-redirect.test','value':run.plan['new_main']}]


def test_partial_cache_cannot_confirm_redirect_continuation(env):
 db,site,remote=env
 remote.data['settings']['canon']='reserve.test'
 parent=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='reglue',status='unknown',initiator='anton',request_payload={'reserve':'reserve.test','source_domain':'main.test','redirect_sync':True})
 db.add(parent);site.network_state={**(site.network_state or {}),'domain_redirects':[],'has_domain_redirects':True};db.commit()
 remote.data['settings'].pop('redirects')
 result=network.read_network(db,site)
 assert not result['redirects_verified'] and db.get(models.NetworkOperation,parent.id).status=='unknown'
 assert not remote.calls


def test_reglue_without_full_redirect_snapshot_fails_before_changing_main(env):
 db,site,remote=env
 remote.data['settings'].pop('redirects')
 before=network.read_network(db,site)
 with pytest.raises(ValueError,match='REDIRECTS_NOT_VERIFIED'):
  change(env,'reglue',before['revision'],domain='reserve.test')
 assert remote.data['settings']['canon']=='main.test' and not remote.calls
