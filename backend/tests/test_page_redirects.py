import copy
from uuid import uuid4
import pytest
import httpx
from app import project_network as network
from app.page_redirects import update
from app.network_state import observe_network
from test_project_network import env,change

ROWS=[{'domain':'main.test','custom':'group','redirects':[{'url':'/play/','value':'https://main.test/','keep':'row'}]},
      {'domain':'reserve.test','redirects':[{'url':'/old/','value':'https://elsewhere.test/new/'}]}]

def setup(env):
    env[2].data['settings']['pageRedirects']=copy.deepcopy(ROWS)
    return network.read_network(env[0],env[1])

def test_crud_changes_only_page_rules_and_confirms_native_read(env):
    db,site,remote=env;first=setup(env);before=copy.deepcopy(remote.data)
    added=change(env,'page_redirect',first['revision'],page_redirect_domain='main.test',page_redirect_source='/new/',page_redirect_target='https://target.test/path/?x=1')
    assert remote.calls[-1][1]=='/projects/update-value'
    assert set(remote.calls[-1][2])=={'folder','pageRedirects'}
    assert added['operations'][0]['status']=='confirmed'
    assert added['operations'][0]['page_redirects_before']==ROWS
    assert added['page_redirects'][1]==ROWS[1]
    edited=change(env,'page_redirect',added['revision'],page_redirect_domain='reserve.test',page_redirect_source='/changed/',page_redirect_target='https://target.test/',page_redirect_original_domain='main.test',page_redirect_original_source='/play/')
    assert edited['page_redirects'][1]['redirects'][-1]=={'url':'/changed/','value':'https://target.test/','keep':'row'}
    deleted=change(env,'page_redirect',edited['revision'],page_redirect_domain='reserve.test',page_redirect_source='/changed/',page_redirect_original_domain='reserve.test',page_redirect_original_source='/changed/',page_redirect_delete=True)
    assert deleted['page_redirects'][1]==ROWS[1]
    assert remote.data['head']==before['head']
    assert {k:v for k,v in remote.data['settings'].items() if k!='pageRedirects'}=={k:v for k,v in before['settings'].items() if k!='pageRedirects'}

@pytest.mark.parametrize('source,target',[('https://main.test/play/','https://main.test/'),('//evil.test/','https://main.test/'),('/a/#fragment','https://main.test/'),('/a/','javascript:alert(1)'),('/a/','https://user:password@target.test/'),('/a/','https://main.test/a/')])
def test_invalid_or_looping_rule_never_writes(env,source,target):
    first=setup(env)
    with pytest.raises(ValueError):change(env,'page_redirect',first['revision'],page_redirect_domain='main.test',page_redirect_source=source,page_redirect_target=target)
    assert not env[2].calls

def test_duplicate_source_and_cross_domain_loop_rejected(env):
    first=setup(env)
    with pytest.raises(ValueError,match='уже существует'):change(env,'page_redirect',first['revision'],page_redirect_domain='main.test',page_redirect_source='/play/',page_redirect_target='https://target.test/')
    project={'settings':{'pageRedirects':[{'domain':'a.test','redirects':[{'url':'/one/','value':'https://b.test/two/'}]}]}}
    with pytest.raises(ValueError,match='цикл'):update(project,'b.test','/two/','https://a.test/one/')

def test_stale_revision_and_lost_reply_do_not_overwrite_or_resend(env):
    db,site,remote=env;first=setup(env)
    payload=network.NetworkChange(request_id=uuid4(),action='page_redirect',revision=first['revision'],page_redirect_domain='main.test',page_redirect_source='/new/',page_redirect_target='https://target.test/')
    remote.fail=httpx.ReadTimeout('lost')
    result=network.change_network(db,site,payload,'test');assert result['operations'][0]['status']=='unknown'
    remote.fail=None
    network.change_network(db,site,payload,'test');assert len(remote.calls)==1
    remote.data['settings']['pageRedirects'][0]['redirects'].append({'url':'/new/','value':'https://target.test/'})
    assert network.read_network(db,site)['operations'][0]['status']=='confirmed'
    with pytest.raises(network.NetworkConflict):change(env,'page_redirect',first['revision'],page_redirect_domain='main.test',page_redirect_source='/other/',page_redirect_target='https://target.test/')
    assert len(remote.calls)==1

def test_missing_optional_native_list_can_be_created_but_partial_cache_retains_it(env):
    first=network.read_network(env[0],env[1]);assert first['has_page_redirects'] and first['page_redirects']==[]
    result=change(env,'page_redirect',first['revision'],page_redirect_domain='main.test',page_redirect_source='/old/',page_redirect_target='https://target.test/')
    state=observe_network(env[1],{'settings':{'canon':'main.test'}})
    assert state['page_redirects']==result['page_redirects']
