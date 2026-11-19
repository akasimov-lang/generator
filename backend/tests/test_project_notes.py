from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app import models
from app.db import Base, get_db
from app.project_notes import router
from app.security import require_auth

@pytest.fixture
def setup():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        a=models.Site(name='notes.test',base_url='https://notes.test',publication_endpoint='/')
        b=models.Site(name='other.test',base_url='https://other.test',publication_endpoint='/')
        db.add_all([a,b]);db.commit()
        user={'id':'user','username':'anton','is_admin':True,'allowed_site_ids':None}
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_db]=lambda:db
        app.dependency_overrides[require_auth]=lambda:user
        yield TestClient(app),a.id,b.id,user

def test_note_persists_exact_text_and_isolated_by_project(setup):
    c,a,b,_=setup
    text='  Первая строка\n\nŻółć 📝 <script>text</script>  '
    saved=c.put(f'/sites/{a}/note',json={'text':text,'revision':''})
    assert saved.status_code==200
    assert c.get(f'/sites/{a}/note').json()['text']==text
    assert c.get(f'/sites/{b}/note').json()['text']==''
    assert c.get('/project-notes').json()['site_ids']==[a]

def test_stale_write_does_not_overwrite_newer_note(setup):
    c,a,_,_=setup
    first=c.put(f'/sites/{a}/note',json={'text':'first'}).json()
    second=c.put(f'/sites/{a}/note',json={'text':'second','revision':first['revision']}).json()
    assert c.put(f'/sites/{a}/note',json={'text':'stale','revision':first['revision']}).status_code==409
    assert c.get(f'/sites/{a}/note').json()==second

def test_lost_response_retry_is_idempotent(setup):
    c,a,_,_=setup
    first=c.put(f'/sites/{a}/note',json={'text':'saved'}).json()
    assert c.put(f'/sites/{a}/note',json={'text':'saved'}).json()==first

def test_blank_note_is_not_prioritized(setup):
    c,a,_,_=setup
    first=c.put(f'/sites/{a}/note',json={'text':'saved'}).json()
    assert c.put(f'/sites/{a}/note',json={'text':' \n\t ','revision':first['revision']}).status_code==200
    assert c.get('/project-notes').json()['site_ids']==[]

def test_clear_note_persists_and_can_be_reopened(setup):
    c,a,_,_=setup
    first=c.put(f'/sites/{a}/note',json={'text':'saved'}).json()
    assert c.put(f'/sites/{a}/note',json={'text':'','revision':first['revision']}).status_code==200
    assert c.get(f'/sites/{a}/note').json()['text']==''

def test_access_checks_protect_text_and_index(setup):
    c,a,b,user=setup
    c.put(f'/sites/{b}/note',json={'text':'private'})
    user['allowed_site_ids']=[a]
    assert c.get(f'/sites/{b}/note').status_code==404
    assert c.put(f'/sites/{b}/note',json={'text':'overwrite'}).status_code==404
    assert c.get('/project-notes').json()['site_ids']==[]

def test_unknown_project_and_oversized_note_rejected(setup):
    c,a,_,_=setup
    assert c.get('/sites/missing/note').status_code==404
    assert c.put(f'/sites/{a}/note',json={'text':'x'*20001}).status_code==422
    assert c.get(f'/sites/{a}/note').json()['text']==''
