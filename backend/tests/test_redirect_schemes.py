from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app import models
from app.db import Base,get_db
from app.security import require_auth
from app.redirect_schemes import router, redirect_dates, prefix

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site=models.Site(name='project.test',base_url='https://main.test',publication_endpoint='https://main.test/api/content',network_state={'domain_redirects':[{'url':'drop.test','value':'new.test'}]})
        db.add(site);db.commit()
        user={'username':'anton','role':'admin','allowed_site_ids':None}
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_db]=lambda:db
        app.dependency_overrides[require_auth]=lambda:user
        yield db,site,user,TestClient(app)

def doc(kind='scheme',name='Test'):
    return {'kind':kind,'name':name,'rows':[{'id':'one','original':'drop.test','url':'drop.test','value':'','expected':{'rows':[{'url':'drop.test','value':'new.test'}]}}], 'board':{'positions':{'main:main.test':{'x':44,'y':55}},'placed':['drop.test'],'zoom':.7,'min_height':2400}}

def path(site):return f'/sites/{site.id}/network/schemes'

def test_incomplete_draft_and_layout_persist_without_changing_live_routes(env):
    db,site,user,client=env;before=site.network_state.copy()
    result=client.post(path(site),json=doc('draft')).json()
    assert result['id']=='draft' and result['rows'][0]['value']==''
    assert client.get(path(site)).json()['draft']['board']['zoom']==.7
    assert client.get(path(site)).json()['draft']['board']['min_height']==2400
    db.refresh(site);assert site.network_state==before
    assert not db.scalars(select(models.NetworkOperation)).all()

def test_named_schemes_and_backups_are_immutable_new_versions(env):
    db,site,user,client=env
    first=client.post(path(site),json=doc()).json()
    second=client.post(path(site),json=doc()).json()
    backup=client.post(path(site),json=doc('backup','')).json()
    assert len({first['id'],second['id'],backup['id']})==3
    assert len(client.get(path(site)).json()['items'])==3
    assert client.get(path(site)+'/'+first['id']).json()['rows']==first['rows']
    assert backup['saved_at'] and backup['kind']=='backup'

def test_owner_and_project_access_are_enforced(env):
    db,site,user,client=env
    identity=client.post(path(site),json=doc()).json()['id']
    user['username']='other'
    assert client.get(path(site)).json()['items']==[]
    assert client.get(path(site)+'/'+identity).status_code==404
    user['allowed_site_ids']=[]
    assert client.post(path(site),json=doc()).status_code==404

def test_blank_name_and_nonfinite_layout_are_rejected(env):
    db,site,user,client=env
    assert client.post(path(site),json=doc(name='  ')).status_code==422
    payload=doc();payload['board']['positions']['main:main.test']['x']=-1
    assert client.post(path(site),json=payload).status_code==422

def test_route_dates_only_come_from_confirmed_change_not_later_unrelated_edit(env):
    db,site,user,client=env
    before=[{'url':'drop.test','value':'old.test'}];after=site.network_state['domain_redirects']
    for at,old,new,status in [('2026-11-20T12:00:00+00:00',before,after,'confirmed'),('2026-11-21T12:00:00+00:00',after,after,'confirmed'),('2026-11-22T12:00:00+00:00',before,after,'unknown')]:
        db.add(models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='domain_redirect',status=status,initiator='anton',request_payload={'redirects_before':old,'redirects':new,'confirmed_at':at}))
    db.commit()
    assert redirect_dates(db,site)=={'drop.test':'2026-11-20T12:00:00+00:00'}

def test_imported_live_route_has_no_invented_date(env):
    db,site,user,client=env
    assert client.get(path(site)).json()['redirect_dates']=={}


def test_snapshot_keys_fit_production_database_limit():
    assert len(prefix(str(uuid4()), "anton") + uuid4().hex) <= 80


def test_older_scheme_documents_default_to_unextended_board(env):
    db,site,user,client=env
    payload=doc();payload["board"].pop("min_height")
    assert client.post(path(site),json=payload).json()["board"]["min_height"]==0
