import copy
from uuid import uuid4
import httpx
import pytest
from test_project_network import env,change
from app import models,project_network as network
from app.domain_redirects import update_redirects,redirect_domain
from app.network_state import observe_network,state_revision

ROWS=[{'url':'old.test','value':'main.test','custom':'keep'}, {'url':'other.test','value':'main.test'}]

def setup(env):
 db,site,remote=env
 remote.data['settings']['redirects']=copy.deepcopy(ROWS)
 return network.read_network(db,site)

def test_cache_preserves_redirects_on_partial_events_and_clears_explicit_empty(env):
 first=setup(env)
 db,site,remote=env
 assert first['domain_redirects']==ROWS and first['has_domain_redirects']
 partial=observe_network(site,{'settings':{'canon':'main.test'}})
 assert partial['domain_redirects']==ROWS and partial['has_domain_redirects']
 before=state_revision(partial)
 empty=observe_network(site,{'settings':{'redirects':[]}})
 assert empty['domain_redirects']==[] and empty['has_domain_redirects']
 assert state_revision(empty)!=before

def test_redirect_add_and_edit_preserve_all_settings_and_log_before_after(env):
 first=setup(env)
 db,site,remote=env
 original=copy.deepcopy(remote.data)
 saved=change(env,'domain_redirect',first['revision'],redirect_source='NEW.test',redirect_target='main.test')
 wanted=ROWS+[{'url':'new.test','value':'main.test'}]
 assert remote.calls==[('POST','/projects/update-value',{'folder':site.name,'redirects':wanted})]
 assert {k:v for k,v in remote.data['settings'].items() if k!='redirects'}=={k:v for k,v in original['settings'].items() if k!='redirects'}
 assert remote.data['head']==original['head']
 assert saved['domain_redirects']==wanted and saved['operations'][0]['status']=='confirmed'
 assert saved['operations'][0]['redirects_before']==ROWS
 assert saved['operations'][0]['redirects_after']==wanted
 edited=change(env,'domain_redirect',saved['revision'],redirect_original_source='old.test',redirect_source='renamed.test',redirect_target='new.test')
 assert edited['domain_redirects'][0]=={'url':'renamed.test','value':'new.test','custom':'keep'}
 assert edited['domain_redirects'][1:]==wanted[1:]

def test_concurrent_redirect_edit_rejects_stale_snapshot(env):
 first=setup(env)
 env[2].data['settings']['redirects'].append({'url':'external.test','value':'main.test'})
 with pytest.raises(network.NetworkConflict):change(env,'domain_redirect',first['revision'],redirect_source='new.test',redirect_target='main.test')
 assert not env[2].calls

def test_redirect_receipt_blocks_duplicate_after_timeout_and_confirms_by_read(env):
 first=setup(env)
 db,site,remote=env
 request=network.NetworkChange(request_id=uuid4(),action='domain_redirect',revision=first['revision'],redirect_source='new.test',redirect_target='main.test')
 remote.fail=httpx.ReadTimeout('lost response')
 unknown=network.change_network(db,site,request,'anton')
 assert unknown['operations'][0]['status']=='unknown'
 remote.fail=None
 network.change_network(db,site,request,'anton')
 assert len(remote.calls)==1
 remote.data['settings']['redirects'].append({'url':'new.test','value':'main.test'})
 assert network.read_network(db,site)['operations'][0]['status']=='confirmed'

def test_missing_redirect_list_never_overwrites_unknown_settings(env):
 env[2].data['settings'].pop('redirects',None)
 first=network.read_network(env[0],env[1])
 assert not first['has_domain_redirects']
 with pytest.raises(ValueError,match='полный список'):change(env,'domain_redirect',first['revision'],redirect_source='new.test',redirect_target='main.test')
 assert not env[2].calls

@pytest.mark.parametrize('source,target,original,message',[
 ('main.test','main.test','','самого себя'),
 ('old.test','new.test','','уже существует'),
 ('new.test','old.test','main.test','отсутствует'),
 ('main.test','old.test','','замкнутую'),
 ('new.test/path','main.test','','без протокола'),
 ('new.test','https://main.test','','без протокола'),
])
def test_invalid_redirects_do_not_write(env,source,target,original,message):
 first=setup(env)
 with pytest.raises(ValueError,match=message):change(env,'domain_redirect',first['revision'],redirect_source=source,redirect_target=target,redirect_original_source=original)
 assert not env[2].calls

def test_domain_redirect_does_not_collapse_www_and_accepts_idn():
 assert redirect_domain('ПРИМЕР.РФ')=='xn--e1afmkfd.xn--p1ai'
 project={'settings':{'redirects':[{'url':'www.old.test','value':'main.test'}]}}
 result=update_redirects(project,'old.test','main.test')
 assert len(result)==2 and result[0]['url']=='www.old.test'


def test_all_redirects_to_current_main_preserves_extras_and_removes_self(env):
 db,site,remote=env
 rows=[{'url':'old.test','value':'external.test','custom':'keep'}, {'url':'other.test','value':'old.test'}, {'url':'www.main.test','value':'external.test'}]
 remote.data['settings']['redirects']=copy.deepcopy(rows)
 original=copy.deepcopy(remote.data)
 first=network.read_network(db,site)
 result=change(env,'domain_redirects_main',first['revision'])
 wanted=[{**r,'value':'main.test'} for r in rows[:2]]
 assert result['domain_redirects']==wanted
 assert remote.calls==[('POST','/projects/update-value',{'folder':site.name,'redirects':wanted})]
 assert result['operations'][0]['redirects_before']==rows
 assert result['operations'][0]['redirects_after']==wanted
 assert result['operations'][0]['status']=='confirmed'
 assert remote.data['head']==original['head']
 assert {k:v for k,v in remote.data['settings'].items() if k!='redirects'}=={k:v for k,v in original['settings'].items() if k!='redirects'}


def test_bulk_redirect_stale_main_never_writes(env):
 first=setup(env);env[2].data['settings']['canon']='changed.test'
 with pytest.raises(network.NetworkConflict):change(env,'domain_redirects_main',first['revision'])
 assert not env[2].calls


def test_bulk_redirect_requires_verified_list(env):
 env[2].data['settings'].pop('redirects',None)
 state=network.read_network(env[0],env[1])
 with pytest.raises(ValueError,match='REDIRECTS_NOT_VERIFIED'):change(env,'domain_redirects_main',state['revision'])
 assert not env[2].calls


def test_bulk_redirect_unknown_receipt_is_never_replayed(env):
 db,site,remote=env;first=setup(env)
 request=network.NetworkChange(request_id=uuid4(),action='domain_redirects_main',revision=first['revision'])
 remote.fail=httpx.ReadTimeout('lost')
 network.change_network(db,site,request,'anton');remote.fail=None
 network.change_network(db,site,request,'anton')
 assert len(remote.calls)==1
