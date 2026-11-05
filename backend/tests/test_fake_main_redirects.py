from copy import deepcopy
from uuid import uuid4

import pytest
from app import project_network as network, fake_main_queue as queue
from app.fake_main_redirects import retarget
from test_project_network import env


def test_retargets_all_old_fake_destinations_preserving_other_rules_and_metadata():
    project={'settings':{'redirects':[
        {'url':'a.test','value':'www.main.test/old/','status':301},
        {'url':'b.test','value':'https://main.test/old/?ref=a#section'},
        {'url':'c.test','value':'https://external.test/old/'},
        {'url':'d.test','value':'main.test/other/'}],
        'pageRedirects':[{'domain':'old.test','custom':True,'redirects':[
            {'url':'/source/','value':'https://main.test/old/'},
            {'url':'/other/','value':'https://main.test/other/'}]}]}}
    before=deepcopy(project)
    result=retarget(project,'/old/','/Psychoterapia','main.test')
    assert [r['value'] for r in result['redirects']]==['www.main.test/Psychoterapia','https://main.test/Psychoterapia?ref=a#section','https://external.test/old/','main.test/other/']
    assert result['redirects'][0]['status']==301
    assert result['pageRedirects'][0]['redirects'][0]['value']=='https://main.test/Psychoterapia'
    assert result['pageRedirects'][0]['custom'] is True
    assert project==before


def test_new_page_source_redirect_is_removed_to_prevent_self_loop():
    project={'settings':{'pageRedirects':[{'domain':'main.test','redirects':[
        {'url':'/new','value':'https://main.test/old/'},
        {'url':'/source','value':'https://main.test/old/'}]}]}}
    assert retarget(project,'/old/','/new','main.test')['pageRedirects'][0]['redirects']==[{'url':'/source','value':'https://main.test/new'}]


@pytest.mark.parametrize('action',['create_fake_main','select_fake_main'])
def test_assignment_saves_path_and_redirects_together_and_confirms(env,action):
    db,site,remote=env
    remote.data['settings']['redirects']=[{'url':'old.test','value':'main.test/cz/'}]
    if action == 'select_fake_main':
        remote.data['settings']['alternate']['fakeMain'].append('/new')
    state=network.read_network(db,site)
    request=network.NetworkChange(request_id=uuid4(),action=action,revision=state['revision'],fake_main_path='/new',activate_fake_main=True)
    result=network.change_network(db,site,request,'anton')
    assert result['operations'][0]['status']=='confirmed'
    assert remote.calls[0][2]['alternate']['currentFakeMain']=='/new'
    assert remote.calls[0][2]['redirects']==[{'url':'old.test','value':'main.test/new'}]
    network.change_network(db,site,request,'anton')
    assert len(remote.calls)==1


def test_creation_without_assignment_does_not_change_redirects(env):
    db,site,remote=env
    remote.data['settings']['redirects']=[{'url':'old.test','value':'main.test/cz/'}]
    state=network.read_network(db,site)
    network.change_network(db,site,network.NetworkChange(request_id=uuid4(),action='create_fake_main',revision=state['revision'],fake_main_path='/new'), 'anton')
    assert 'redirects' not in remote.calls[0][2]


def test_queue_waits_for_redirect_confirmation_without_repeating_write(env,monkeypatch):
    db,site,remote=env
    original=[{'url':'old.test','value':'main.test/cz/'}]
    remote.data['settings']['redirects']=deepcopy(original)
    network.read_network(db,site)
    request=queue.Request(request_id=uuid4(),action='create',path='/new')
    queue.enqueue(db,site,request,'anton')
    write=remote.request
    def ignore_redirects(*args):
        response=write(*args)
        remote.data['settings']['redirects']=deepcopy(original)
        return response
    monkeypatch.setattr(remote,'request',ignore_redirects)
    assert queue.execute_step(db,str(request.request_id))['status']=='waiting'
    assert queue.execute_step(db,str(request.request_id))['status']=='waiting'
    assert len(remote.calls)==1
    remote.data['settings']['redirects']=[{'url':'old.test','value':'main.test/new'}]
    assert queue.execute_step(db,str(request.request_id))['status']=='completed'
    assert len(remote.calls)==1


def test_malformed_redirects_block_assignment_before_any_write(env):
    db,site,remote=env
    remote.data['settings']['pageRedirects']=None
    state=network.read_network(db,site)
    with pytest.raises(ValueError,match='список редиректов'):
        network.change_network(db,site,network.NetworkChange(request_id=uuid4(),action='create_fake_main',revision=state['revision'],fake_main_path='/new',activate_fake_main=True),'anton')
    assert not remote.calls
