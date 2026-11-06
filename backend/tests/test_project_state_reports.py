from copy import deepcopy
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app import models,project_state_reports as reports
from test_project_network import env

AT=datetime(2026,11,5,12,tzinfo=timezone.utc)
START=datetime(2026,11,1,21,tzinfo=timezone.utc)
END=datetime(2026,11,6,21,tzinfo=timezone.utc)

def page(text):return {'slug':'/test/','content':{'blocks':[{'id':'p','type':'paragraph','data':{'text':text}}]}}

def test_current_drop_scheme_resolves_template_without_modifying_it(env):
    _,site,_=env;site.domain_types={'main.test':'drop'}
    state={'canon':'www.main.test','fake_main_current':'/pl/','fake_main_enabled':True,'enableCanonical':True,'canonicalDefaultMarkup':'<link rel="canonical" href="https://{{settings.canon}}/pl/">','enableAlternates':True,'alternateMarkup':'<link rel="alternate" hreflang="pl" href="https://{{settings.canon}}/">'}
    original=deepcopy(state);result=reports.scheme(site,state)
    assert result['main_type']=='drop' and 'Canonical на внутряк' in result['scheme']
    assert 'www.main.test' in result['alternate'] and state==original

def test_only_confirmed_changed_main_and_selected_path_are_events():
    def op(action,status,payload):return SimpleNamespace(id=str(uuid4()),action=action,status=status,request_payload=payload,updated_at=AT)
    values=[op('reglue','confirmed',{'source_domain':'old.test','reserve':'new.test'}),op('reglue','pending',{'reserve':'unconfirmed.test'}),op('reglue','confirmed',{'source_domain':'same.test','reserve':'same.test'}),op('create_fake_main','confirmed',{'alternate':{'fakeMain':['/spare/']}}),op('select_fake_main','confirmed',{'journal_before':{'fake_path':'/old/'},'alternate':{'currentFakeMain':'/new/'}})]
    events=reports.network_events(values)
    assert [x['kind'] for x in events]==['reglue','fake_path']
    assert events[1]['before']=='/old/' and events[1]['after']=='/new/'

def test_edit_metrics_distinguish_metadata_and_real_text():
    old=page('Pelican one two three');new=page('Pelican one two four five six')
    edit=SimpleNamespace(id='e',before_page=old,after_page=new,updated_at=AT)
    event=reports.text_event(edit,'Pelican Casino')
    assert event['words_before']==4 and event['words_after']==6
    assert event['before_counts']['brand_mentions']==1
    assert event['paragraphs_added']==0 and event['paragraphs_removed']==0
    edit.after_page={**old,'title':'New title'}
    assert reports.text_event(edit,'Pelican')['text_changed'] is False

def test_new_pages_count_unique_creates_not_updates_pending_or_retries(env):
    db,site,_=env
    task=models.GenerationTask(id=str(uuid4()),title='test',site_id=site.id,geo='PL',language='pl',prompt_template='test')
    db.add(task);db.flush()
    def item(slug,published=True):
        row=models.ContentItem(id=str(uuid4()),task_id=task.id,site_id=site.id,topic='t',slug=slug,generated_json=page('one two'),idempotency_key=str(uuid4()),status='published' if published else 'publication_pending_confirmation',published_at=AT if published else None)
        db.add(row);db.flush();return row
    def log(i,path,at=AT):
        db.add(models.PublicationLog(content_item_id=i.id,endpoint_url='https://webdev.test/projects/'+path,request_payload={'page':page('one two')|{'slug':i.slug}},response_status=201,created_at=at))
    new=item('/new/');log(new,'create');log(new,'create');log(new,'update')
    updated=item('/existing/');log(updated,'update',START-timedelta(days=1));log(updated,'create')
    pending=item('/pending/',False);log(pending,'create')
    deleted=item('/removed/');deleted.published_at=None;deleted.deletion_confirmed_at=AT;log(deleted,'create')
    old=item('/old/');log(old,'create',START-timedelta(days=2));log(old,'create')
    db.commit();events=reports.publication_events(db,site.id,START,END)
    assert {e['path'] for e in events}=={'/new/','/removed/'}
    assert all(e['words']==2 for e in events)

def test_week_boundary_uses_utc_equivalent_of_moscow_monday():
    assert reports.within('2026-11-01T21:00:00Z',START,END)
    assert not reports.within('2026-11-01T20:59:59Z',START,END)

def test_report_access_filters_rows_and_totals_for_colleagues(env,monkeypatch):
    db,site,_=env
    monkeypatch.setattr('app.report_ids.get',lambda *a:3044)
    job=models.BackgroundJob(id=str(uuid4()),kind='maintenance_report',status='completed',payload={'task_type':reports.TASK,'site_ids':[site.id,'secret'],'name':'Pelican','report_kind':'weekly_brand','period_start':START.isoformat(),'period_end':END.isoformat()},result={'entries':[{'site_id':site.id,'included':True,'state_source':'webdev','events':[],'pages_added':2},{'site_id':'secret','included':True,'state_source':'webdev','events':[{}],'pages_added':100}]})
    db.add(job);db.commit()
    out=reports.public_view(db,job,{'username':'colleague','allowed_site_ids':[site.id]})
    assert out['total']==1 and out['pages_added']==2 and out['scope']==1
    with pytest.raises(HTTPException):reports.public_view(db,job,{'allowed_site_ids':[]})

def test_collect_is_read_only_and_retains_verification_failure(env):
    db,site,remote=env;site.domain_types={'main.test':'drop'}
    job=models.BackgroundJob(id=str(uuid4()),kind='maintenance_report',payload={'task_type':reports.TASK,'site_ids':[site.id],'report_kind':'drop_inner','period_start':START.isoformat(),'period_end':END.isoformat()})
    db.add(job);db.commit()
    before=deepcopy(site.network_state)
    result=reports.collect_one(db,job.id,site.id)
    assert not result['included'] and result['state_source']=='webdev'
    assert remote.calls==[] and site.network_state==before

def test_weekly_reports_do_not_appear_among_execution_plans(env,monkeypatch):
    from app import auto_pilot
    db,site,_=env
    j=models.BackgroundJob(id=str(uuid4()),kind='maintenance_report',payload={'actor':'anton','task_type':reports.TASK,'site_ids':[site.id]})
    db.add(j);db.commit()
    monkeypatch.setattr('app.report_ids.ensure',lambda db:{j.id:3044})
    assert auto_pilot.tasks(db,{'username':'anton','allowed_site_ids':None})['items']==[]


def test_registered_report_endpoint_requires_authentication():
    from app.main import app
    from fastapi.testclient import TestClient
    response=TestClient(app).get('/api/project-reports')
    assert response.status_code==401
