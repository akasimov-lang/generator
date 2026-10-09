import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models
from app.db import Base
spec=importlib.util.spec_from_file_location('one_time',Path(__file__).parents[1]/'scripts/one_time_reglue.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture
def context(monkeypatch):
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    db=Session(engine)
    site=models.Site(id='00000000-0000-4000-8000-000000000001',name='site.test',base_url='https://site.test',publication_endpoint='https://site.test/publish',project_status='mass_actions',cache_server_ip='bear',domain_types={})
    db.add(site);db.commit()
    p={'settings':{'canon':'old.test','prev':'older.test','reserve':'new.test','alternate':{},'redirects':{},'domains':['old.test','new.test']},'head':{k:False if k.startswith('enable') else '' for k in m.HEAD}}
    plan={'site_id':site.id,'source_ids':'1','project':site.name,'server':'bear','excluded':False,'old_main':'old.test','new_main':'new.test','alternate_domain':'old.test','fake_path':'/brand/','canonical_main_and_fake':'https://new.test/brand/','canonical_template':'<link rel="canonical" href="https://{{settings.canon}}/brand/" />','canonical_other_pages':'<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}" />','alternate_markup':'<link rel="alternate" hreflang="en-US" href="https://old.test/brand/" />\n<link rel="alternate" hreflang="en" href="https://old.test/" />\n<link rel="alternate" hreflang="x-default" href="https://new.test/" />'}
    class Remote:
        def __init__(self):self.p=copy.deepcopy(p);self.calls=[]
        def project(self):return copy.deepcopy(self.p)
        def request(self,method,path,payload):
            self.calls.append(path)
            if path.endswith('check-domain'):return {'reachable':True}
            payload=copy.deepcopy(payload);payload.pop('folder',None)
            if path.endswith('update-value'):self.p['settings'].update(payload)
            elif path.endswith('update-head'):self.p['head'].update(payload)
            elif path.endswith('update-reglue'):
                self.p['settings'].update(prev=self.p['settings']['canon'],canon=payload['reserve'],redirects={'changed':True})
    monkeypatch.setattr(m.time,'sleep',lambda _:None)
    yield db,site,Remote(),plan,p
    db.close()

def test_apply_and_exact_rollback(context):
    db,site,r,plan,before=context
    op=m.prepare(db,site,r,plan,'00000000-0000-4000-8000-000000000002')
    assert r.p==before and op.status=='prepared'
    m.apply(db,site,r,op)
    assert op.status=='confirmed' and m.matches(r.p,plan)
    assert op.request_payload['before']==before
    assert op.request_payload['indexing_operation_id']
    calls=list(r.calls);m.apply(db,site,r,op);assert r.calls==calls
    m.rollback(db,site,r,op)
    assert r.p==before and op.request_payload['rolled_back_by']

def test_rollback_refuses_concurrent_changes(context):
    db,site,r,plan,_=context
    op=m.prepare(db,site,r,plan,'00000000-0000-4000-8000-000000000002');m.apply(db,site,r,op)
    r.p['settings']['geo']='changed';calls=list(r.calls)
    with pytest.raises(AssertionError,match='changed after'):m.rollback(db,site,r,op)
    assert r.calls==calls

def test_ambiguous_write_is_not_repeated(context):
    db,site,r,plan,_=context
    op=m.prepare(db,site,r,plan,'00000000-0000-4000-8000-000000000002')
    def fail(*args):r.calls.append('failed');raise TimeoutError()
    r.request=fail
    with pytest.raises(RuntimeError):m.step(db,op,r,'fake','POST','/projects/update-value',{},lambda _:False)
    with pytest.raises(RuntimeError,match='repeat blocked'):m.step(db,op,r,'fake','POST','/projects/update-value',{},lambda _:False)
    assert r.calls.count('failed')==1

def test_excluded_and_occupied_are_rejected(context):
    db,site,r,plan,_=context
    plan['source_ids']='2367'
    with pytest.raises(AssertionError,match='Excluded'):m.validate(r.p,plan,site)
    plan['source_ids']='1';r.p['settings']['alternate']={'fakeMain':['/brand/']}
    with pytest.raises(AssertionError,match='occupied'):m.validate(r.p,plan,site)

def test_main_unchanged_skips_reglue(context):
    db,site,r,plan,_=context
    plan.update(new_main='old.test',canonical_main_and_fake='https://old.test/brand/')
    plan['alternate_markup']=plan['alternate_markup'].replace('new.test','old.test')
    op=m.prepare(db,site,r,plan,'00000000-0000-4000-8000-000000000002');m.apply(db,site,r,op)
    assert not any(x.endswith('update-reglue') for x in r.calls)
    assert m.matches(r.p,plan)

def test_folder_metadata_does_not_prevent_rollback(context):
    db,site,r,plan,before=context
    original_request=r.request
    def persist_folder(method,path,payload):
        result=original_request(method,path,payload)
        if path.endswith('update-value'):r.p['settings']['folder']=site.name
        return result
    r.request=persist_folder
    op=m.prepare(db,site,r,plan,'00000000-0000-4000-8000-000000000002');m.apply(db,site,r,op)
    m.rollback(db,site,r,op)
    assert m.settings_equal(r.p['settings'],before['settings']) and r.p['head']==before['head']

def test_timeout_after_success_is_reconciled(context):
    db,site,r,plan,_=context
    op=m.prepare(db,site,r,plan,'00000000-0000-4000-8000-000000000002')
    original_request=r.request
    def timeout(method,path,payload):original_request(method,path,payload);raise TimeoutError()
    r.request=timeout
    m.step(db,op,r,'x','POST','/projects/update-value',{'reserve':'new.test'},lambda q:q['settings']['reserve']=='new.test')
    assert op.request_payload['steps']['x']['status']=='confirmed'
    assert 'TimeoutError' in op.request_payload['steps']['x']['transport_warning']

def test_lock_conflict_does_not_modify_other_workers_receipt(context,monkeypatch):
    from contextlib import contextmanager
    db,site,r,plan,_=context
    opid=str(m.uuid5(m.UUID(m.BATCH),site.id))
    op=m.prepare(db,site,r,plan,opid);op.status='running';db.commit()
    @contextmanager
    def unavailable(*args):
        raise RuntimeError('locked elsewhere')
        yield
    monkeypatch.setattr(m,'network_lock',unavailable)
    monkeypatch.setattr(m,'SessionLocal',lambda:Session(db.bind))
    monkeypatch.setattr(m,'Remote',lambda *args:r)
    r.close=lambda:None
    result=m.worker(plan,'apply','unused')
    assert result['error']=='RuntimeError: locked elsewhere'
    db.expire_all();assert db.get(models.NetworkOperation,opid).status=='running'
