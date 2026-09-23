from datetime import datetime, timezone
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app import models, external_auth
from app.api import router
from app.auto_reglue_api import router as auto_router
from app.db import Base, get_db
from app.security import require_admin

@pytest.fixture
def api(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for sid,name,server in [('own','own.test','one'),('other','other.test','two'),('duplicate','own.test','two')]:
            db.add(models.Site(id=sid,name=name,cache_server_ip=server,base_url='https://'+name,publication_endpoint='https://'+name+'/api'))
            db.add(models.GenerationTask(id='task-'+sid,title=sid,site_id=sid,geo='DE',language='de'))
            db.add(models.ContentItem(id='content-'+sid,task_id='task-'+sid,site_id=sid,topic=sid,slug=sid,generated_json={},idempotency_key=sid))
            db.add(models.Section(id='section-'+sid,site_id=sid,name=sid,path="/"+sid+"/",external_id=sid))
            db.add(models.PublicationCampaign(id='campaign-'+sid,site_id=sid,name=sid,start_at=datetime.now(timezone.utc)))
        db.add(models.User(username='editor',password_hash='old-secret-hash',is_admin=True,is_active=True))
        db.commit()
    grants={'projects':frozenset({('own.test','one')})}
    def identity(token,fresh=False):
        if token not in ('external-editor','external-anton'): raise HTTPException(401,'Invalid token')
        return {'username':'anton' if token=='external-anton' else 'editor','is_admin':token=='external-anton','projects':None if token=='external-anton' else grants['projects']}
    monkeypatch.setattr(external_auth,'identity',identity)
    monkeypatch.setattr(external_auth,'login_external',lambda username,password:'external-'+username)
    app=FastAPI();app.include_router(router,prefix='/api');app.include_router(auto_router,prefix='/api')
    def database():
        with Session(engine) as db: yield db
    app.dependency_overrides[get_db]=database
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer external-editor'
        yield client,engine,grants

def test_roles_and_local_credentials(api):
    c,engine,_=api
    r=c.post('/api/auth/login',json={'username':'editor','password':'remote-password'})
    assert r.status_code==200,r.text
    assert r.json()['access_token']=='external-editor' and not r.json()['user']['is_admin']
    assert c.get('/api/auth/me').json()['allowed_site_ids']==['own']
    with Session(engine) as db:
        user=db.scalar(select(models.User).where(models.User.username=='editor'))
        assert user.password_hash=='' and not user.is_admin
    c.headers['Authorization']='Bearer external-anton'
    assert c.get('/api/auth/me').json()['is_admin']
    assert len(c.get('/api/sites').json())==3
    c.headers['Authorization']='Bearer old-local-token'
    assert c.get('/api/sites').status_code==401

@pytest.mark.parametrize('path,key',[('/sites','id'),('/sites/cache/projects','id'),('/tasks','site_id'),('/content','site_id'),('/publication-campaigns','site_id')])
def test_filtered_lists(api,path,key):
    r=api[0].get('/api'+path);assert r.status_code==200,r.text
    assert {row[key] for row in r.json()}=={'own'}

@pytest.mark.parametrize('path',['/sites/other/overview','/sites/duplicate/network','/sites/lookup?site_id=other','/sites/lookup?name=other.test','/tasks/task-other','/content/content-other','/content/content-other/revisions','/publication-campaigns/campaign-other/queue','/sites/other/network/operations'])
def test_direct_link_denied(api,path):
    r=api[0].get('/api'+path);assert r.status_code==404,r.text

@pytest.mark.parametrize('path,body',[('/content/content-other/approve',{}),('/sites/other/network/operations',{'action':'reglue'}),('/publication-campaigns',{'site_id':'other','content_item_ids':['content-other']}),('/sites/own/content/delete-published',{'content_item_ids':['content-other']}),('/sites/own/tasks',{'name':'test','site_id':'other'}),('/me/favorite-sites/other',{})])
def test_foreign_mutations_denied(api,path,body):
    r=api[0].request('PUT' if '/favorite-sites/' in path else 'POST','/api'+path,json=body)
    assert r.status_code==404,r.text

def test_removed_internal_access_and_admin_endpoints(api):
    c,_,_=api
    assert c.post('/api/publication/run-due').status_code==403
    assert c.post('/api/sites/cache/sync-jobs',json={}).status_code==403
    for path in ['/users','/users/any/reset-password','/me/password']:
        assert c.post('/api'+path,json={}).status_code==404

def test_revocation(api):
    c,_,grants=api
    assert len(c.get('/api/sites').json())==1
    grants['projects']=frozenset()
    assert c.get('/api/sites').json()==[]
    assert c.get('/api/content/content-own').status_code==404
    assert c.get('/api/auth/me').json()['allowed_site_ids']==[]

def test_own_writes(api):
    c,_,_=api
    r=c.patch('/api/sites/own/brand',json={'brand':'Example'});assert r.status_code==200,r.text
    r=c.put('/api/me/favorite-sites/own');assert r.status_code==200,r.text
    assert r.json()['site_ids']==['own']

def test_logs_filtered(api):
    c,engine,_=api
    with Session(engine) as db:
        for sid in ['own','other']:db.add(models.PublicationLog(content_item_id='content-'+sid,endpoint_url='https://'+sid+'.test'))
        db.commit()
    r=c.get('/api/publication-logs');assert r.status_code==200,r.text
    assert [row['content_item_id'] for row in r.json()]==['content-own']

def test_external_contract(monkeypatch):
    external_auth._cache.clear();calls=[]
    def respond(request):
        calls.append(request)
        if request.url.path=='/auth/login':
            assert __import__('json').loads(request.content)=={'username':'editor','pass':'secret'}
            return httpx.Response(200,json={'token':'remote-token'})
        assert request.headers['Authorization']=='Bearer remote-token'
        if request.url.path=='/auth/me':return httpx.Response(200,json={'username':'editor','role':'admin','restricted':False,'foreign':'Editor','name':'Редактор'})
        return httpx.Response(201,json=[{'name':name,'serverIp':'one','settings':settings} for name,settings in [('own.test',{'duty':'Editor'}),('second.test',{'secondDuty':'Editor'}),('dev.test',{'webdevDuty':{'developer':'Редактор'}}),('no.test',{'duty':'Other'})]])
    original=httpx.Client
    monkeypatch.setattr(external_auth.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    token=external_auth.login_external('editor','secret');result=external_auth.identity(token,fresh=True)
    assert not result['is_admin'] and result['projects']==frozenset({('own.test','one'),('second.test','one'),('dev.test','one')})
    count=len(calls);assert external_auth.identity(token)==result and len(calls)==count
    external_auth.identity(token,fresh=True);assert len(calls)==count+2

@pytest.mark.parametrize('status',[401,403,500])
def test_external_failure_closed(monkeypatch,status):
    external_auth._cache.clear();original=httpx.Client
    monkeypatch.setattr(external_auth.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={})),**kwargs))
    with pytest.raises(HTTPException) as err:external_auth.identity('invalid',fresh=True)
    assert err.value.status_code==(401 if status in (401,403) else 503)

def test_own_draft_creation_and_unauthorized_detached_task(api):
    c,_,_=api
    payload={'geo':'DE','language':'de','topics':['Example topic'],'save_as_draft':True,'section_id':'section-own'}
    r=c.post('/api/sites/own/tasks',json=payload)
    assert r.status_code==200,r.text
    assert r.json()['site_id']=='own'
    r=c.post('/api/tasks',json={'geo':'DE','language':'de','topics':['Detached'],'save_as_draft':True})
    assert r.status_code in (400,403),r.text

def test_external_session_failure_does_not_fall_back_to_local_admin(api,monkeypatch):
    c,_,_=api
    monkeypatch.setattr(external_auth,'identity',lambda *a,**kw:(_ for _ in ()).throw(HTTPException(503,'Unavailable')))
    assert c.get('/api/sites').status_code==503

def test_background_job_other_project_is_not_visible(api):
    c,engine,_=api
    with Session(engine) as db:
        db.add(models.BackgroundJob(id='other-job',kind='publication',payload={'content_id':'content-other'}))
        db.add(models.BackgroundJob(id='sync-job',kind='cache_sync',payload={}))
        db.commit()
    for id in ['other-job','sync-job']:
        assert c.get('/api/background-jobs/'+id).status_code==404

def test_cleanup_preserves_user_ids_and_removes_credentials(api,monkeypatch):
    from app import db as database
    c,engine,_=api
    with Session(engine) as session:
        before=session.scalar(select(models.User.id))
    monkeypatch.setattr(database,'engine',engine)
    database.disable_local_credentials()
    with Session(engine) as session:
        user=session.get(models.User,before)
        assert user and user.password_hash=='' and not user.is_admin and not user.is_active
    assert c.get('/api/auth/me').status_code==200

def test_external_project_reads_preserve_server_scope(api,monkeypatch):
    from app import api as endpoints
    c,_,_=api
    rows=[{'name':'own.test','serverIp':server,'data':{'pages':[{'slug':'page','title':title,'content':[]}]}} for server,title in [('two','PRIVATE'),('one','ALLOWED')]]
    monkeypatch.setattr(endpoints,'fetch_project_cache',lambda names:rows)
    r=c.get('/api/sites/own/pages/preview?slug=page')
    assert r.status_code==200,r.text
    assert r.json()['title']=='ALLOWED' and 'PRIVATE' not in r.text

def test_user_refresh_imports_only_authorized_projects(api, monkeypatch):
    from app import api as endpoints
    c, engine, grants = api
    grants['projects'] = frozenset({('own.test', 'one'), ('new.test', 'one')})
    with Session(engine) as db:
        db.get(models.Site, 'own').external_project_id = 'remote-own'
        db.commit()
    calls = []
    rows = [dict(id=id, name=name, serverIp=server,
                 settings={'canon':name, 'lang':'en'}, head={}, data={})
            for id,name,server in [('remote-own','own.test','one'),
                                    ('remote-new','new.test','one'),
                                    ('private-duplicate','own.test','two'),
                                    ('private-other','other.test','two')]]
    monkeypatch.setattr(endpoints, 'fetch_project_cache', lambda names: calls.append(names) or rows)
    for created in [1, 0]:
        r = c.post('/api/sites/cache/sync', json={})
        assert r.status_code == 200, r.text
        assert r.json()['created_count'] == created
        assert r.json()['cache_count'] == 2
        assert {p['external_project_id'] for p in r.json()['projects']} == {'remote-own','remote-new'}
    assert calls == [['new.test','own.test']] * 2
    assert {s['name'] for s in c.get('/api/sites').json()} == {'own.test','new.test'}
    with Session(engine) as db:
        assert db.get(models.Site, 'own').cache_language == 'en'
        assert db.get(models.Site, 'duplicate').cache_language is None
        assert db.get(models.Site, 'other').cache_language is None
        assert len(db.scalars(select(models.Site)).all()) == 4
    assert c.post('/api/sites/cache/sync', json={'names':['other.test']}).status_code == 404
    grants['projects'] = frozenset()
    r = c.post('/api/sites/cache/sync', json={})
    assert r.status_code == 200, r.text
    assert r.json()['cache_count'] == 0
    assert len(calls) == 2
    assert c.get('/api/sites').json() == []
