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
    state={'canon':'www.main.test','fake_main_current':'/pl/','fake_main_enabled':True,'enableCanonical':True,'canonicalDefaultMarkup':'<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}">','canonicalFakeMainMarkup':'<link rel="canonical" href="https://{{settings.canon}}/pl/">','enableAlternates':True,'alternateMarkup':'<link rel="alternate" hreflang="pl" href="https://{{settings.canon}}/">'}
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
    def log(i,path,at=AT,id=None):
        db.add(models.PublicationLog(id=id or str(uuid4()),content_item_id=i.id,endpoint_url='https://webdev.test/projects/'+path,request_payload={'page':page('one two')|{'slug':i.slug}},response_status=201,created_at=at))
    new=item('/new/');log(new,'create');log(new,'create');log(new,'update',id='00000000-0000-0000-0000-000000000001')
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


def test_confirmed_showcase_templates_count_as_layout_even_when_batch_is_partial(env):
    db,site,_=env
    edit=models.ProjectPageEdit(id=str(uuid4()),site_id=site.id,page_key='template-receipt',requested_by='anton',fingerprint='test',
        before_page={'node':{'name':'casinos.hbs','data':'old'}},after_page={'node':{'name':'casinos.hbs','data':'new'}},status='confirmed',updated_at=AT)
    db.add(edit);db.commit()
    result=reports.row(db,site,{},START,END,AT,'cache')
    assert result['layout_work'] and result['showcase_layout_work'] and result['showcase_work']
    assert not result['template_work'] and not result['menu_work']
    assert result['events'][0]['message']=='Обновлён шаблон: casinos.hbs'


def test_planned_empty_or_unchanged_template_is_not_completed_work():
    from app.report_work_evidence import template_event
    edit=SimpleNamespace(id='e',status='pending',updated_at=AT,before_page={'name':'header.hbs','data':'old'},after_page={'name':'header.hbs','data':'new'})
    assert template_event(edit) is None
    edit.status='confirmed'
    assert template_event(edit)['categories']==['template','menu']
    edit.after_page=deepcopy(edit.before_page)
    assert template_event(edit) is None
    edit.after_page={'node':{'name':'new.hbs','created':True}}
    assert template_event(edit) is None


def test_ledger_counts_confirmed_changes_with_their_own_dates_and_not_planned_work():
    from app.report_work_evidence import ledger_events,work_flags
    ledger=SimpleNamespace(key='site-menu-repair:report',value={'status':'applying','applied_at':(START-timedelta(days=2)).isoformat(),
        'receipts':[{'field':'header','status':'confirmed','confirmed_at':AT.isoformat()},
                    {'field':'styles','status':'unknown','at':AT.isoformat()},
                    {'field':'layout','status':'confirmed','at':(START-timedelta(days=1)).isoformat()}]})
    events=ledger_events(ledger,START,END)
    assert len(events)==1 and events[0]['at']==AT.isoformat()
    assert work_flags(events)=={'layout_work':True,'showcase_layout_work':False,'template_work':True,'menu_work':True,'showcase_work':False}


def test_uploaded_logo_does_not_count_as_template_repair():
    from app.report_work_evidence import ledger_events,work_flags
    ledger=SimpleNamespace(key='showcase-example:original',value={'receipts':[{'kind':'logo','brand':'Example','status':'confirmed','verified_at':AT.isoformat()}]})
    flags=work_flags(ledger_events(ledger,START,END))
    assert flags['showcase_work'] and not flags['layout_work']
    ledger.value={'status':'prepared','plan':{'templates':['planned']}}
    assert ledger_events(ledger,START,END)==[]


def test_chat_repair_receipt_has_description_without_link_to_nonexistent_report():
    from app.report_work_evidence import ledger_events
    ledger=SimpleNamespace(key='site-menu-repair:chat-project',value={'receipts':[
        {'field':'header','status':'confirmed','at':AT.isoformat(),'message':'Добавлено меню.'}]})
    event=ledger_events(ledger,START,END)[0]
    assert event['message']=='Добавлено меню.' and 'report_url' not in event


def test_menu_report_ignores_failed_other_project_and_identical_resends(env):
    from app.report_work_evidence import menu_events
    db,site,_=env
    def log(at,items,project=None,status=200):
        db.add(models.PublicationLog(endpoint_url='https://webdev.test/projects/menu',created_at=at,response_status=status,
            request_payload={'action':'menu_sync','project_name':project or site.name,'type':'header','list':items}))
    old=[{'title':'Old','slug':'/old/'}];new=old+[{'title':'New','slug':'/new/'}]
    log(START-timedelta(days=1),old)
    log(START+timedelta(hours=1),old)
    log(AT,new)
    log(AT+timedelta(minutes=1),new)
    log(AT+timedelta(minutes=2),[],status=500)
    log(AT+timedelta(minutes=3),[],'other.test')
    db.commit()
    events=menu_events(db,site.name,START,END)
    assert len(events)==1 and events[0]['menu_items']==2
    assert events[0]['at']==AT.isoformat() and events[0]['message']=='Добавлены пункты: New'


def test_empty_menu_sync_and_only_new_ids_are_not_work(env):
    from app.report_work_evidence import menu_events
    db,site,_=env
    logs=[]
    def add(menu,items,minute):
        logs.append(SimpleNamespace(id=str(uuid4()),created_at=AT+timedelta(minutes=minute),response_status=200,error_message=None,
            request_payload={'action':'menu_sync','project_name':site.name,'type':menu,'list':items}))
    add('footer',[],0)
    add('header',[],1)
    add('header',[{'id':1,'title':'Hry','slug':'/games/'}],2)
    add('header',[{'id':999,'title':'Hry','slug':'/games/'}],3)
    db.info['state_report_menu_logs']=logs
    events=menu_events(db,site.name,START,END)
    assert len(events)==1 and events[0]['message']=='Добавлены пункты: Hry'


def test_removal_of_real_menu_items_has_specific_description(env):
    from app.report_work_evidence import menu_events
    db,site,_=env
    def log(items,at):return SimpleNamespace(id=str(uuid4()),created_at=at,response_status=200,error_message=None,
        request_payload={'action':'menu_sync','project_name':site.name,'type':'footer','list':items})
    db.info['state_report_menu_logs']=[log([{'title':'Old contact','slug':'/contact/'}],START-timedelta(days=1)),log([],AT)]
    events=menu_events(db,site.name,START,END)
    assert len(events)==1 and events[0]['message']=='Удалены пункты: Old contact'


def test_report_counts_projects_not_receipts_and_ignores_errors_outside_work_scope(env,monkeypatch):
    db,site,_=env
    monkeypatch.setattr('app.report_ids.get',lambda *a:3048)
    job=models.BackgroundJob(id=str(uuid4()),kind='maintenance_report',status='running',payload={'task_type':reports.TASK,'site_ids':[site.id,'no-work'],
        'name':'work','report_kind':'weekly_brand','period_start':START.isoformat(),'period_end':END.isoformat()},
        result={'entries':[{'site_id':site.id,'project':site.name,'included':True,'status':'completed','events':[{},{}],
            'layout_work':True,'showcase_layout_work':True,'template_work':True,'menu_work':True},
            {'site_id':'no-work','project':'other.test','included':False,'status':'partial','events':[],'state_error':'Unavailable'}]})
    db.add(job);db.commit()
    reports.save_rows(db,job.id,[],finish=True)
    result=reports.public_view(db,job,{'allowed_site_ids':None})
    assert result['layout_projects']==result['showcase_layout_projects']==result['template_projects']==result['menu_projects']==1
    assert result['errors']==0 and result['unverified']==[] and result['status']=='completed'


def test_confirmed_title_h1_values_are_extracted_without_markup(env):
    db,site,_=env
    old=page('body');old['title']='Pelican Casino old'
    old['content']['blocks'].append({'type':'header','data':{'level':1,'text':'Pelican <b>old</b> heading'}})
    new=deepcopy(old);new['title']='Pelican Casino new'
    new['content']['blocks'][-1]['data']['text']='Pelican <em>new</em> heading'
    edit=models.ProjectPageEdit(id=str(uuid4()),site_id=site.id,page_key='/',requested_by='test',fingerprint='h1',before_page=old,after_page=new,status='confirmed',updated_at=AT)
    pending=models.ProjectPageEdit(id=str(uuid4()),site_id=site.id,page_key='/other/',requested_by='test',fingerprint='pending',before_page=old,after_page=new,status='pending',updated_at=AT)
    db.add_all([edit,pending]);db.commit()
    row=reports.row(db,site,{},START,END,AT,'cache')
    assert row['heading_changes']==1
    assert row['events'][0]['heading_changes']==[
        {'field':'title','before':'Pelican Casino old','after':'Pelican Casino new'},
        {'field':'h1','before':'Pelican old heading','after':'Pelican new heading'}]
    assert row['events'][0]['at']==AT.isoformat()


def test_description_only_change_is_not_a_title_h1_rewrite():
    before=page('body');after={**before,'description':'Updated description'}
    edit=SimpleNamespace(id='desc',before_page=before,after_page=after,updated_at=AT)
    assert reports.text_event(edit,'Pelican')['heading_changes']==[]


def test_homepage_and_current_inner_use_special_canonical_when_alternates_enabled(env):
    _,site,_=env
    state={'canon':'main.test','fake_main_current':'/current/','fake_main_enabled':True,
        'enableCanonical':True,'enableAlternates':True,
        'canonicalDefaultMarkup':'<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}">',
        'canonicalFakeMainMarkup':'<link rel="canonical" href="https://{{settings.canon}}/current/">'}
    result=reports.scheme(site,state)
    assert result['canonical']==result['inner_canonical']=='<link rel="canonical" href="https://main.test/current/">'
    assert result['canonical_source']=='fake_main' and 'Canonical на внутряк' in result['scheme']
    assert result['canonical_templates']['default']==state['canonicalDefaultMarkup']


def test_disabled_alternates_use_default_canonical_with_each_request_path(env):
    _,site,_=env
    state={'canon':'main.test','fake_main_current':'/current/','fake_main_enabled':True,
        'enableCanonical':True,'enableAlternates':False,
        'canonicalDefaultMarkup':'<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}">',
        'canonicalFakeMainMarkup':'<link rel="canonical" href="https://obsolete.test/old/">'}
    result=reports.scheme(site,state)
    assert result['canonical']=='<link rel="canonical" href="https://main.test/">'
    assert result['inner_canonical']=='<link rel="canonical" href="https://main.test/current/">'
    assert result['canonical_source']=='default' and 'Canonical на главную' in result['scheme']


def test_special_canonical_request_placeholder_resolves_home_and_inner_separately(env):
    _,site,_=env
    state={'canon':'main.test','fake_main_current':'/current/','fake_main_enabled':True,
        'enableCanonical':True,'enableAlternates':True,
        'canonicalDefaultMarkup':'<link rel="canonical" href="https://wrong.test/">',
        'canonicalFakeMainMarkup':'<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}">'}
    result=reports.scheme(site,state)
    assert result['canonical']=='<link rel="canonical" href="https://main.test/">'
    assert result['inner_canonical']=='<link rel="canonical" href="https://main.test/current/">'


def test_disabled_canonical_is_not_shown_as_an_active_tag(env):
    _,site,_=env
    state={'canon':'main.test','fake_main_current':'/current/','fake_main_enabled':True,
        'enableCanonical':False,'enableAlternates':True,
        'canonicalDefaultMarkup':'<link rel="canonical" href="https://main.test/">',
        'canonicalFakeMainMarkup':'<link rel="canonical" href="https://main.test/current/">'}
    result=reports.scheme(site,state)
    assert result['canonical']==result['inner_canonical']==''
    assert result['canonical_source']=='disabled' and 'Canonical выключен' in result['scheme']
    assert result['canonical_templates']['fake_main']==state['canonicalFakeMainMarkup']


def test_empty_special_canonical_does_not_fall_back_to_unapplied_default(env):
    _,site,_=env
    state={'canon':'main.test','enableCanonical':True,'enableAlternates':True,
        'canonicalDefaultMarkup':'<link rel="canonical" href="https://main.test/">'}
    result=reports.scheme(site,state)
    assert result['canonical']=='' and 'Canonical не задан' in result['scheme']


def test_report_canonical_parser_ignores_alternate_href_and_external_root(env):
    _,site,_=env
    state={'canon':'main.test','fake_main_current':'/current/','fake_main_enabled':True,
        'enableCanonical':True,'enableAlternates':True,
        'canonicalFakeMainMarkup':'<link rel="alternate" href="https://main.test/current/" hreflang="pl"><link rel="canonical" href="https://other.test/">'}
    result=reports.scheme(site,state)
    assert 'Canonical см. разметку' in result['scheme']
