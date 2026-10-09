import copy
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models, project_pages as pages
from app.db import Base, get_db
from app.security import require_auth


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    site = models.Site(name='brand.test', base_url='https://brand.test', brand='Brand', is_active=True, publication_endpoint='/projects/update')
    db.add(site); db.commit()
    project = {'settings': {}, 'data': {'pages': [
        {'id': '8', 'slug': '/bonus/', 'title': 'Bonus', 'description': 'About bonus', 'head': ['keep'], 'content': {'blocks': []}},
        {'id': '4', 'slug': '/', 'title': 'Home', 'description': 'About brand', 'head': ['canonical'],
         'banners': {'desktop':'keep'}, 'publishedTime': 'old', 'content': {'version':'2.28', 'blocks': [
            {'id':'img', 'type':'image','data':{'file':{'url':'/uploads/brand.webp'},'caption':'Brand'}},
            {'type':'customWidget','data':{'settings':{'keep':True}}},
            {'id':'p', 'type':'paragraph','data':{'text':'Original paragraph'}}]}}
    ]}}
    state = {'project':project, 'requests':[], 'failure': None, 'apply':True}
    class Remote:
        def __init__(self,*args): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def project(self): return copy.deepcopy(state['project'])
        def request(self,method,path,payload):
            state['requests'].append(copy.deepcopy(payload))
            if state['failure']: raise state['failure']
            if state['apply']:
                state['project']['data']['pages'] = [copy.deepcopy(payload['page']) if p['id']==payload['page']['id'] else p for p in state['project']['data']['pages']]
            return 200, {'success':True}
    monkeypatch.setattr(pages,'Remote',Remote)
    monkeypatch.setattr(pages,'get_settings',lambda: type('Settings',(),{'project_cache_username':'service-account'})())
    app = FastAPI(); app.include_router(pages.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_auth]=lambda:{'id':'user','username':'anton'}
    with TestClient(app) as client:
        yield client,db,site,state
    db.close()


def draft(client,site):
    path=f'/sites/{site.id}/pages'
    home=client.get(path).json()['pages'][0]
    path+=f'/{home["key"]}'
    page=client.get(path).json()
    return path, {'request_id':str(uuid4()),'revision':page['revision'],'title':'Updated home',
                  'description':'Updated description','content':page['content']}


def test_home_first_and_preserve_whole_page_on_edit(setup):
    client,db,site,state=setup
    path,payload=draft(client,site)
    assert client.get(path).json()['is_home']
    before=copy.deepcopy(state['project']['data']['pages'][1])
    payload['content']['blocks'][2]['data']['text']='New paragraph'
    response=client.put(path,json=payload)
    assert response.status_code==200 and response.json()['status']=='confirmed'
    sent=state['requests'][0]
    assert sent['id']==4 and sent['page']['id']=='4' and sent['initiator']=='service-account'
    for field in ['head','banners','publishedTime']:
        assert sent['page'][field]==before[field]
    assert sent['page']['content']['blocks'][:2]==before['content']['blocks'][:2]
    audit=db.scalar(select(models.ProjectPageEdit))
    assert audit.requested_by=='anton' and audit.before_page==before
    assert client.put(path,json=payload).json()['status']=='confirmed'
    assert len(state['requests'])==1


def test_conflict_and_wrong_identity_never_write(setup):
    client,db,site,state=setup
    path,payload=draft(client,site)
    state['project']['data']['pages'][1]['head']=['someone changed canonical']
    assert client.put(path,json=payload).status_code==409
    assert client.put(path+'unknown',json=payload).status_code==404
    assert not state['requests']


def test_timeout_is_not_retried_and_can_be_confirmed(setup):
    client,db,site,state=setup
    path,payload=draft(client,site)
    state['failure']=httpx.ReadTimeout('private connection details')
    result=client.put(path,json=payload).json()
    assert result['status']=='unknown' and 'private' not in result['error']
    assert client.put(path,json=payload).json()['status']=='unknown'
    assert len(state['requests'])==1
    state['project']['data']['pages'][1]=state['requests'][0]['page']
    assert client.get(path+'/edits/'+payload['request_id']).json()['status']=='confirmed'


def test_pending_verification_and_archived_project(setup):
    client,db,site,state=setup
    path,payload=draft(client,site)
    state['apply']=False
    assert client.put(path,json=payload).json()['status']=='unknown'
    site.is_active=False;db.commit()
    assert client.get(path).status_code==404
    assert client.get(f'/sites/{site.id}/pages').status_code==404
    assert client.put(path,json=payload).status_code==404


def test_rejects_overwrites_of_noneditable_fields_and_duplicate_ids(setup):
    client,db,site,state=setup
    path,payload=draft(client,site)
    assert client.put(path,json={**payload,'slug':'/moved/'}).status_code==422
    state['project']['data']['pages'].append(copy.deepcopy(state['project']['data']['pages'][1]))
    assert client.put(path,json=payload).status_code==409
    assert not state['requests']


def test_history_has_before_after_and_does_not_mutate_remote(setup):
    client,db,site,state=setup
    path,payload=draft(client,site)
    client.put(path,json=payload)
    versions=client.get(path+'/history').json()
    assert len(versions)==1 and versions[0]['requested_by']=='anton'
    assert client.get(path+'/history/'+versions[0]['id']).json()['title']=='Updated home'
    assert client.get(path+'/history/'+versions[0]['id']+'?before=true').json()['title']=='Home'
    assert len(state['requests'])==1


def test_interlink_only_returns_draft_for_internal_page(setup):
    client,db,site,state=setup
    home,payload=draft(client,site)
    content={'blocks':[{'type':'paragraph','data':{'text':'Brand overview. Read Brand here.'}}]}
    assert client.post(home+'/interlink',json={'content':content}).status_code==422
    key=pages.page_key(state['project']['data']['pages'][0])
    result=client.post(f'/sites/{site.id}/pages/{key}/interlink',json={'content':content})
    assert result.status_code==200
    assert result.json()['content']['blocks'][0]['data']['text']=='Brand overview. Read <a href="/">Brand</a> here.'
    assert not state['requests']


def test_ai_jobs_are_durable_and_never_publish(setup,monkeypatch):
    import json
    from app import services, background_jobs
    client,db,site,state=setup
    path,payload=draft(client,site)
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://ai.test',api_key='test')
    db.add(provider);db.commit()
    async def generate(*args,**kwargs):
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'items':[{'id':0,'text':'Rewritten paragraph'}]})}]}}]}
    monkeypatch.setattr(services,'call_gemini',generate)
    response=client.post(path+'/ai',json={'action':'paragraphs','provider_id':provider.id,'content':payload['content']})
    assert response.status_code==202 and response.json()['status']=='queued'
    job=db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.kind=='project_page_ai'))
    assert job and not state['requests']
    assert background_jobs.run_job(db,job.id)['status']=='completed'
    result=client.get(path+'/ai/'+response.json()['id']).json()
    assert result['input_content']==payload['content']
    assert result['result_content']['blocks'][2]['data']['text']=='Rewritten paragraph'
    assert not state['requests']
    assert len(client.get(path+'/ai').json())==1


def test_brand_inventory_excludes_archived_and_generic_projects(setup):
    from app.auto_reglue_api import router
    client,db,site,state=setup
    client.app.include_router(router)
    site.domains_count=4
    for name,brand,active,count in [('same','B-r-a-n-d',True,3),('excluded','Brand',False,90),('generic','Общие ключи',True,10)]:
        db.add(models.Site(name=name,base_url='https://'+name,publication_endpoint='/',brand=brand,is_active=active,domains_count=count))
    db.commit()
    result=client.get('/auto-reglue/brands').json()
    assert not result['transfers_enabled']
    assert len(result['brands'])==1
    assert result['brands'][0]['project_count']==2 and result['brands'][0]['domain_count']==7
    assert not state['requests']


def test_fibery_name_keeps_value_when_snapshot_omits_field_and_clears_explicit_empty(setup):
    from app.project_cache import _apply_fibery_name
    client,db,site,state=setup
    _apply_fibery_name(site,{'webdevDuty':{'fibery':'  #640_fontan casino_PL  '}})
    assert site.fibery_name=='#640_fontan casino_PL'
    _apply_fibery_name(site,{})
    assert site.fibery_name=='#640_fontan casino_PL'
    _apply_fibery_name(site,{'webdevDuty':{'fibery':''}})
    assert site.fibery_name is None


def test_page_dates_from_webdev_with_publication_fallback():
    row = pages.page_summary({'id': '1', 'slug': '/', 'createdTime': '2025-01-01', 'publishedTime': '2025-01-02', 'updatedTime': '2026-10-09'})
    assert row['created_at'] == '2025-01-01' and row['created_at_source'] == 'createdTime'
    assert row['updated_at'] == '2026-10-09'
    assert pages.page_summary({'publishedTime': '2025-01-02'})['created_at'] == '2025-01-02'
    assert pages.page_summary({})['created_at'] is None
