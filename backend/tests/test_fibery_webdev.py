import json
from copy import deepcopy

import httpx
import pytest

from app.fibery_client import FiberyConflict, FiberyError
from app.fibery_webdev import WebdevClient, TASK_TYPE


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr('app.fibery_client.time.sleep',lambda _:None)
    state={'task':None,'content':'','creates':0,'timeout':False,'updates':0}
    def handle(request):
        if request.url.path.startswith('/api/documents/'):
            if request.method=='PUT':state['content']=json.loads(request.content)['content']
            return httpx.Response(200,json={'content':state['content']})
        command=json.loads(request.content)[0];args=command['args'];kind=command['command']
        if kind=='fibery.entity/query':
            type_=args['query']['q/from']
            if type_=='Alfasearch Config/SEO Projects':result=[{'fibery/id':'project','fibery/public-id':'1715'}]
            elif type_.startswith('workflow/'):result=[{'fibery/id':'new','enum/name':'New'}]
            else:result=[deepcopy(state['task'])] if state['task'] else []
        elif kind=='fibery.entity/create':
            assert args['type']==TASK_TYPE and args['entity']['workflow/state']['fibery/id']=='new'
            assert state['task'] is None
            state['creates']+=1;state['task']={**args['entity'],'fibery/public-id':'20274',
                'workflow/state':{'enum/name':'New'},'Alfasearch Config/Description':{'Collaboration~Documents/secret':'secret'}}
            result=state['task']
            if state['timeout']:
                state['timeout']=False;raise httpx.ReadTimeout('PRIVATE')
        else:
            state['updates']+=1;pytest.fail('Webdev requests must not be closed or reassigned')
        return httpx.Response(200,json=[{'success':True,'result':result}])
    client=WebdevClient('token');client.http.close()
    client.http=httpx.Client(base_url='https://hzhz.fibery.io',transport=httpx.MockTransport(handle))
    yield client,state
    client.close()


def create(client):
    return client.ensure_webdev_task(task_id='fixed',project_number='1715',title='project.test — исправить /contacts',
        description='- Проект: https://project.test/\n- HTTP 301: https://project.test/contacts/ → https://project.test/contacts',
        page_url='https://project.test/contacts')


def test_webdev_request_is_new_has_exact_page_url_and_verified_description(remote):
    client,state=remote;result=create(client)
    assert result['state']=='New' and result['url'].endswith('/Webdev_Tasks/20274')
    assert result['description_verified'] and result['page_url']=='https://project.test/contacts'
    assert not state['updates']


def test_uncertain_create_recovers_same_webdev_task(remote):
    client,state=remote;state['timeout']=True
    with pytest.raises(FiberyError):create(client)
    assert create(client)['description_verified'] and state['creates']==1


def test_human_description_is_preserved_for_webdev_request(remote):
    client,state=remote;create(client);state['content']='Engineering notes'
    with pytest.raises(FiberyConflict):create(client)
    assert state['content']=='Engineering notes'


def test_wrong_url_or_project_cannot_be_overwritten(remote):
    client,state=remote;create(client)
    state['task']['Alfasearch Config/Page URL']='https://other.test/'
    with pytest.raises(FiberyConflict):create(client)
    assert not state['updates']
