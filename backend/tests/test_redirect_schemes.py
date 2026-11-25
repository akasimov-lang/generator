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
    return {'kind':kind,'name':name,'rows':[{'id':'one','original':'drop.test','url':'drop.test','value':'','expected':{'rows':[{'url':'drop.test','value':'new.test'}]}}], 'board':{'sizes':{},'positions':{'main:main.test':{'x':44,'y':55}},'placed':['drop.test'],'zoom':.7,'min_height':2400}}

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


def test_resized_cards_round_trip_through_saved_scheme_and_draft(env):
    db,site,user,client=env
    payload=doc('draft')
    payload['board']['sizes']={'drop.test':{'width':420,'height':160},'main.test':{'width':500,'height':180}}
    saved=client.post(path(site),json=payload)
    assert saved.status_code==200
    assert client.get(path(site)).json()['draft']['board']['sizes']==payload['board']['sizes']
    payload['kind']='scheme'
    named=client.post(path(site),json=payload).json()
    assert client.get(path(site)+'/'+named['id']).json()['board']['sizes']==payload['board']['sizes']


def test_old_saved_boards_without_card_sizes_remain_compatible(env):
    db,site,user,client=env
    payload=doc();payload['board'].pop('sizes')
    assert client.post(path(site),json=payload).json()['board']['sizes']=={}


def test_saved_card_dimensions_are_bounded(env):
    db,site,user,client=env
    payload=doc();payload['board']['sizes']={'drop.test':{'width':20,'height':100}}
    assert client.post(path(site),json=payload).status_code==422


def test_draft_save_discards_completed_deletion_without_changing_live_routes(env):
    db,site,user,client=env
    site.network_state={'has_domain_redirects':True,'domain_redirects':[]}
    db.commit()
    payload=doc('draft');payload['rows'][0]['removed']=True
    saved=client.post(path(site),json=payload).json()
    assert saved['rows']==[]
    assert saved['board']==payload['board']
    db.refresh(site);assert site.network_state['domain_redirects']==[]
    assert not db.scalars(select(models.NetworkOperation)).all()


def test_read_old_draft_prunes_completed_deletion_but_keeps_other_edits(env):
    db,site,user,client=env
    payload=doc('draft');payload['rows'][0]['removed']=True
    edit={'id':'two','url':'edit.test','original':'edit.test','value':'desired.test','expected':{'rows':[{'url':'edit.test','value':'before.test'}]}}
    payload['rows'].append(edit)
    client.post(path(site),json=payload)
    site.network_state={'has_domain_redirects':True,'domain_redirects':[{'url':'edit.test','value':'before.test'}]}
    db.commit()
    assert client.get(path(site)).json()['draft']['rows']==[{**edit,'removed':False}]
    assert client.get(path(site)+'/draft').json()['rows']==[{**edit,'removed':False}]


def test_unknown_redirect_snapshot_does_not_discard_pending_deletion(env):
    db,site,user,client=env
    site.network_state={'has_domain_redirects':False,'domain_redirects':[]}
    db.commit()
    payload=doc('draft');payload['rows'][0]['removed']=True
    assert client.post(path(site),json=payload).json()['rows'][0]['removed'] is True


def test_still_existing_redirect_keeps_its_deletion_marker(env):
    db,site,user,client=env
    site.network_state={**site.network_state,'has_domain_redirects':True}
    db.commit()
    payload=doc('draft');payload['rows'][0]['removed']=True
    assert client.post(path(site),json=payload).json()['rows'][0]['removed'] is True


def test_named_and_backup_snapshots_keep_historical_deletions(env):
    db,site,user,client=env
    site.network_state={'has_domain_redirects':True,'domain_redirects':[]}
    db.commit()
    named=doc('scheme');named['rows'][0]['removed']=True
    backup=doc('backup');backup['rows'][0]['removed']=True
    saved_named=client.post(path(site),json=named).json()
    saved_backup=client.post(path(site),json=backup).json()
    assert saved_named['rows'][0]['removed'] is True
    assert saved_backup['rows'][0]['removed'] is True
    assert client.get(path(site)+'/'+saved_named['id']).json()['rows'][0]['removed'] is True
    assert client.get(path(site)+'/'+saved_backup['id']).json()['rows'][0]['removed'] is True


def test_deleted_unchanged_baseline_does_not_reappear_as_a_new_draft_route(env):
    db,site,user,client=env
    site.network_state={'has_domain_redirects':True,'domain_redirects':[]}
    db.commit()
    payload=doc('draft');payload['rows'][0]['value']='new.test'
    assert client.post(path(site),json=payload).json()['rows']==[]


def test_user_edited_route_is_preserved_if_the_original_was_deleted_elsewhere(env):
    db,site,user,client=env
    site.network_state={'has_domain_redirects':True,'domain_redirects':[]}
    db.commit()
    payload=doc('draft');payload['rows'][0]['value']='edited.test'
    assert client.post(path(site),json=payload).json()['rows'][0]['value']=='edited.test'
