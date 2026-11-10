import copy
import json

import httpx
import pytest

from app.fibery_client import FiberyClient, FiberyConflict, FiberyError, normalized_document


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr('app.fibery_client.time.sleep', lambda _:None)
    state={'task':None,'content':'','creates':0,'timeout_create':False,'timeout_put':False,'writes':[]}
    def handle(request):
        if request.url.path.startswith('/api/documents/'):
            if request.method=='PUT':
                state['content']=json.loads(request.content)['content'];state['writes'].append('document')
                if state['timeout_put']:
                    state['timeout_put']=False
                    raise httpx.ReadTimeout('SENSITIVE_REMOTE_SECRET')
            return httpx.Response(200,json={'content':state['content']})
        command=json.loads(request.content)[0];args=command['args'];kind=command['command']
        if kind=='fibery.entity/query':
            type_=args['query']['q/from']
            if type_=='Alfasearch Config/SEO Projects':
                result=[{'fibery/id':'project-626','fibery/public-id':'626','Alfasearch Config/Name':'Project'}]
            elif type_.startswith('workflow/state_'):
                result=[{'fibery/id':'closed','enum/name':'Closed'},{'fibery/id':'progress','enum/name':'In Progress'}]
            else:result=[copy.deepcopy(state['task'])] if state['task'] else []
        elif kind=='fibery.entity/create':
            assert not state['task'],'duplicate remote creation'
            state['creates']+=1;state['writes'].append('create')
            state['task']={**args['entity'],'fibery/public-id':'33303','workflow/state':{'enum/name':'In Progress'},
                           'Alfasearch Config/ТЗ':{'Collaboration~Documents/secret':'DOCUMENT_SECRET'}}
            result=state['task']
            if state['timeout_create']:
                state['timeout_create']=False
                raise httpx.ReadTimeout('SENSITIVE_REMOTE_SECRET')
        else:
            state['writes'].append('close');state['task']['workflow/state']={'enum/name':'Closed'};result=state['task']
        return httpx.Response(200,json=[{'success':True,'result':result}])
    client=FiberyClient('PRIVATE_TOKEN')
    client.http.close();client.http=httpx.Client(base_url='https://hzhz.fibery.io',transport=httpx.MockTransport(handle))
    yield client,state
    client.close()


def create(client):
    return client.ensure_task(task_id='deterministic-id',project_number='626',title='Переклей: a.test → b.test',description='Работы:\n\n- Main a.test → b.test\n')


def test_timeout_after_create_is_recovered_without_duplicate(remote):
    client,state=remote;state['timeout_create']=True
    with pytest.raises(FiberyError) as error:create(client)
    assert 'SENSITIVE_REMOTE_SECRET' not in str(error.value)
    result=create(client)
    assert state['creates']==1 and result['description_verified']
    assert result['url'].endswith('/33303')
    assert 'DOCUMENT_SECRET' not in str(result)


def test_timeout_after_description_write_is_reconciled_by_readback(remote):
    client,state=remote;state['timeout_put']=True
    with pytest.raises(FiberyError):create(client)
    assert create(client)['description_verified']
    assert state['creates']==1 and state['writes'].count('document')==1


def test_successful_retry_does_not_rewrite_a_verified_task(remote):
    client,state=remote;create(client);writes=list(state['writes'])
    state['content']=state['content'].replace('- ','* ')
    assert create(client)['description_verified']
    assert state['writes']==writes


def test_human_description_is_preserved(remote):
    client,state=remote;create(client);state['content']='Human edited report'
    writes=list(state['writes'])
    with pytest.raises(FiberyConflict):create(client)
    assert state['content']=='Human edited report' and state['writes']==writes


def test_wrong_project_relation_stops_all_writes(remote):
    client,state=remote;create(client);state['task']['Alfasearch Config/SEO Project']={'fibery/id':'other'}
    writes=list(state['writes'])
    with pytest.raises(FiberyConflict):create(client)
    assert state['writes']==writes


def test_fibery_soft_breaks_and_literal_markdown_are_read_back(remote):
    client,state=remote
    description='Проект Fibery: #626_bet on red _CZ\nДата: 10.11.2026\n\n- Main: old.test → new.test.'
    args=dict(task_id='deterministic-id',project_number='626',title='Переклей',description=description)
    client.ensure_task(**args)
    writes=list(state['writes'])
    state['content']='Проект Fibery: #626_bet on red \\_CZ<br>Дата: 10.11.2026\n\n* Main: old.test → new.test.'
    assert client.ensure_task(**args)['description_verified']
    assert state['writes']==writes


def test_document_normalization_preserves_alternate_source():
    before='Разметка:\n```html\n<link href="https://a.test/_path/" />\n<br>\n\n\n```'
    after=before.replace('<br>', '\n')
    assert normalized_document(before)!=normalized_document(after)


def test_document_normalization_keeps_actual_report_changes():
    before='Main: old.test → new.test.<br>Внутренняя страница: /old/ → /new/'
    after='Main: old.test → other.test.\nВнутренняя страница: /old/ → /new/'
    assert normalized_document(before)!=normalized_document(after)
