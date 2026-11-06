"""Read-only project snapshots and weekly work evidence; no remote writes."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlsplit
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.db import get_db
from app.security import AuthUser
from app.reglue_history import utc
from app.network_state import domain_name, project_network_state
from app.domain_classification import registrable_root
from app import report_work_evidence as work

TASK='project_state_report'
router=APIRouter(prefix='/project-reports',tags=['project-reports'])

def iso(value):
    at=utc(value)
    return at.isoformat() if at else None

def within(value,start,end):
    at=utc(value)
    return bool(at and start<=at<=end)

def normalized_path(value):
    return '/'+urlsplit(str(value or '/')).path.strip('/')+'/' if str(value or '/').strip('/') else '/'

def scheme(site,state):
    main=domain_name(state.get('canon') or site.cache_canon)
    root=registrable_root(main.removeprefix('www.')) or main
    types=site.domain_types or {}
    kind=next((types[k] for k in [main,main.removeprefix('www.'),root,'www.'+root] if types.get(k) in {'drop','newreg'}),'unknown')
    path=state.get('fake_main_current') or ''
    def resolve(markup,req='/'):
        return str(markup or '').replace('{{settings.canon}}',main).replace('{{reqPath}}',req)
    canonical=resolve(state.get('canonicalDefaultMarkup'))
    inner_canonical=resolve(state.get('canonicalFakeMainMarkup'),path or '/')
    # Canonical is not an alternate link: inspect href directly.
    href=re.search(r'''href=["']([^"']+)["']''',canonical)
    dest=href.group(1) if href else ''
    canon_label=('выключен' if not state.get('enableCanonical') else 'на внутряк' if path and urlsplit(dest).path.rstrip('/')==path.rstrip('/') else 'на главную' if dest and urlsplit(dest).path in {'','/'} else 'см. разметку')
    label={'drop':'Дроп','newreg':'Новорег','unknown':'Тип домена не указан'}[kind]
    parts=[label+(' · поддомен' if main.removeprefix('www.')!=root else ''),('внутряк '+path+(' (выключен)' if not state.get('fake_main_enabled') else '')) if path else 'внутряк не назначен','с альтернейтами' if state.get('enableAlternates') else 'без альтернейтов','Canonical '+canon_label]
    redirects=state.get('domain_redirects') or []
    if redirects:parts.append('редиректы доменов: '+str(len(redirects)))
    return {'main':main,'main_type':kind,'root_domain':root,'fake_path':path,'fake_enabled':bool(state.get('fake_main_enabled')),'scheme':'; '.join(parts),'alternate':resolve(state.get('alternateMarkup')) if state.get('enableAlternates') else '', 'canonical':canonical,'inner_canonical':inner_canonical,'redirects':redirects,'head_known':bool(state.get('has_head'))}

def network_events(operations):
    events=[]
    for op in operations:
        if op.status!='confirmed':continue
        p=op.request_payload or {};at=iso(p.get('confirmed_at') or op.updated_at)
        before=p.get('journal_before') or {};after=p.get('journal_after') or {}
        if op.action=='reglue':
            old=before.get('main') or p.get('source_domain');new=after.get('main') or p.get('reserve')
            if new and domain_name(old)!=domain_name(new):events.append({'id':op.id,'kind':'reglue','at':at,'label':'Смена Main','before':old,'after':new,'source':'confirmed_operation'})
        elif op.action in {'create_fake_main','select_fake_main'}:
            old=before.get('fake_path');new=after.get('fake_path') or (p.get('alternate') or {}).get('currentFakeMain')
            if new and old!=new:events.append({'id':op.id,'kind':'fake_path','at':at,'label':'Замена внутренней страницы на уникальную.' if op.action=='create_fake_main' else 'Смена внутренней страницы','before':old,'after':new,'created':op.action=='create_fake_main','source':'confirmed_operation'})
        elif op.action in {'alternates','structured_data','delete_domain','create_domains','create_subdomains','reserve','domain_redirect','domain_redirects_main','page_redirect'}:
            names={'alternates':'Альтернейты / Canonical','structured_data':'Микроразметка','delete_domain':'Удаление домена из сетки','create_domains':'Добавление доменов в сетку','create_subdomains':'Создание поддомена','reserve':'Назначение резерва','domain_redirect':'Редирект домена','domain_redirects_main':'Обновление редиректов сетки','page_redirect':'Редирект страницы'}
            events.append({'id':op.id,'kind':op.action,'at':at,'label':names[op.action],'source':'confirmed_operation'})
    return events

def text_event(edit,brand):
    from app.page_word_count import page_visible_text,page_word_count
    from app.content_metrics import counts,comparison
    from app.maintenance_reports import paragraph_metrics
    before,after=edit.before_page or {},edit.after_page or {}
    old,new=page_visible_text(before),page_visible_text(after)
    if old is None or new is None:return None
    metadata=[k for k in ['title','description'] if before.get(k)!=after.get(k)]
    text_changed=old!=new
    if not text_changed and not metadata:return None
    a,b=paragraph_metrics(before),paragraph_metrics(after)
    return {'id':edit.id,'kind':'text','label':'Изменение текста' if text_changed else 'Изменение метаданных','at':iso(edit.updated_at),'path':after.get('slug') or before.get('slug') or '/', 'text_changed':text_changed,'metadata':metadata,'words_before':page_word_count(before),'words_after':page_word_count(after),'before_counts':counts(before,brand),'after_counts':counts(after,brand),**comparison(before,after),'paragraphs_before':a['count'],'paragraphs_after':b['count'],'paragraphs_added':len(set(b['ids'])-set(a['ids'])) if a['ids'] is not None and b['ids'] is not None else None,'paragraphs_removed':len(set(a['ids'])-set(b['ids'])) if a['ids'] is not None and b['ids'] is not None else None,'source':'confirmed_page_edit'}

def publication_events(db,site_id,start,end):
    """First confirmed create per path, never retries, updates, or draft generation."""
    from app.page_word_count import page_word_count
    pairs=db.execute(select(models.PublicationLog,models.ContentItem).join(models.ContentItem,models.ContentItem.id==models.PublicationLog.content_item_id).where(models.ContentItem.site_id==site_id).order_by(models.PublicationLog.created_at,models.PublicationLog.id)).all()
    first={};known={}
    for log,item in pairs:
        if not log.response_status or not 200<=log.response_status<300 or log.error_message:continue
        page=(log.request_payload or {}).get('page') or {};path=normalized_path(page.get('slug') or item.published_url or item.slug)
        endpoint=urlsplit(log.endpoint_url).path.rstrip('/')
        if endpoint.endswith('/update'):known.setdefault(path,log.created_at);continue
        # Equal timestamps do not prove an update predates the first create;
        # UUID ordering must not randomly remove a newly published page.
        if not endpoint.endswith('/create') or (path in known and known[path]<log.created_at) or path in first:continue
        if not item.published_at and not item.deletion_confirmed_at:continue
        first[path]={'id':log.id,'kind':'page_added','label':'Добавлена страница','at':iso(log.created_at),'confirmed_at':iso(item.published_at),'path':path,'words':page_word_count(page),'source':'confirmed_create_publication'}
    return [v for v in first.values() if within(v['at'],start,end)]

def maintenance_events(db,site_id,start,end):
    events=[]
    jobs=db.info.get('state_report_sources')
    if jobs is None:jobs=list(db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind=='maintenance_report')))
    for job in jobs:
        if job.payload.get('task_type')==TASK:continue
        for row in (job.result or {}).get('entries',[]):
            if row.get('site_id')!=site_id:continue
            migration=row.get('migration') or {};task=job.payload.get('task_type') or ''
            at=migration.get('presentation_verified_at') or migration.get('confirmed_at') or row.get('confirmed_at') or row.get('finished_at')
            if task=='showcase_standardization' and (migration.get('status') in {'completed','confirmed'} or migration.get('presentation_status')=='confirmed'):
                if within(at,start,end):events.append({'id':job.id+':showcase','kind':'showcase','label':'Витрина: добавление / обновление','at':iso(at),'message':migration.get('message'),'before':migration.get('before_count'),'after':migration.get('after_count'),'report_url':'/auto-reglue/pilot/report?maintenance='+job.id,'source':'confirmed_report'})
            elif row.get('status')=='completed' and task not in {'showcase_audit','showcase_inventory','showcase_standardization'}:
                if within(at,start,end):events.append({'id':job.id+':work','kind':'maintenance','label':job.payload.get('name'),'at':iso(at),'message':row.get('message') or row.get('comment'),'report_url':'/auto-reglue/pilot/report?maintenance='+job.id,'source':'confirmed_report'})
    ledgers=db.info.get('state_report_ledgers')
    if ledgers is None:ledgers=work.source_ledgers(db)
    for ledger in ledgers:
        if (ledger.value or {}).get('site_id')==site_id:
            events+=work.ledger_events(ledger,start,end)
    return events

def row(db,site,state,start,end,observed_at,source):
    ops=list(db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id==site.id)))
    network=network_events(ops)
    current=scheme(site,state)
    def latest(kind,value):
        matching=[e for e in network if e['kind']==kind and e.get('after')==value]
        if matching:return max(matching,key=lambda e:e['at'])
        key='new_main' if kind=='reglue' else 'new_path'
        observed=[e for e in state.get('cache_change_history',[]) if e.get(key)==value and e.get('at')]
        return {'at':max(e['at'] for e in observed),'source':'observed_change'} if observed else None
    events=[e for e in network if within(e['at'],start,end)]
    for edit in db.scalars(select(models.ProjectPageEdit).where(models.ProjectPageEdit.site_id==site.id,models.ProjectPageEdit.status=='confirmed',models.ProjectPageEdit.updated_at>=start,models.ProjectPageEdit.updated_at<=end)):
        event=work.template_event(edit) or text_event(edit,site.brand)
        if event:events.append(event)
        elif edit.page_key in {'showcase:work','showcase:casinos'}:
            value=edit.after_page or {}
            events.append({'id':edit.id,'kind':'showcase','label':'Изменение витрины','at':iso(edit.updated_at),'message':value.get('message'),'report_url':'/auto-reglue/pilot/report?maintenance='+value['report_id'] if value.get('report_id') else None,'source':'confirmed_showcase_edit'})
    events+=publication_events(db,site.id,start,end)
    events+=work.menu_events(db,site.name,start,end)
    report_urls={e.get('report_url') for e in events if e['kind']=='showcase'}
    events+=[e for e in maintenance_events(db,site.id,start,end) if e['kind']!='showcase' or not e.get('report_url') or e['report_url'] not in report_urls]
    events.sort(key=lambda e:(e['at'],e['id']),reverse=True)
    fibery=site.fibery_name or '';number=re.search(r'#\s*(\d+)',fibery)
    return {'site_id':site.id,'project':site.name,'brand':site.brand,'geo':site.cache_geo,'fibery_name':fibery,'fibery_url':'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/'+number.group(1) if number else None,**current,'reglue_date':latest('reglue',current['main']),'fake_date':latest('fake_path',current['fake_path']),'observed_at':iso(observed_at),'state_source':source,'status':'completed','events':events,'pages_added':sum(e['kind']=='page_added' for e in events),'fake_pages_created':sum(e['kind']=='fake_path' and e.get('created',False) for e in events),'text_changes':sum(e['kind']=='text' and e['text_changed'] for e in events),**work.work_flags(events)}

def collect_one(db,job_id,site_id,*,live=True):
    job=db.get(models.BackgroundJob,job_id);site=db.get(models.Site,site_id)
    if not job or job.payload.get('task_type')!=TASK or site_id not in job.payload['site_ids']:raise ValueError('Unknown report scope')
    start,end=utc(job.payload['period_start']),utc(job.payload['period_end'])
    state=deepcopy(site.network_state or {});observed=site.cache_synced_at;source='cache';error=None
    if live:
        try:
            from app.project_network import Remote
            with Remote(db,site) as remote:project=remote.project()
            if not (project.get('settings') or {}).get('canon'):raise ValueError('Main не получен от Webdev')
            state={**state,**project_network_state(project)};observed=datetime.now(timezone.utc);source='webdev'
        except Exception as exc:error=str(exc)[:300]
    result=row(db,site,state,start,end,observed,source)
    if error:result.update(status='partial',state_error=error)
    result['included']=bool(result['events']) and (job.payload['report_kind']!='drop_inner' or (result['main_type']=='drop' and bool(result['fake_path'])))
    return result

def save_rows(db,job_id,rows,*,finish=False):
    job=db.get(models.BackgroundJob,job_id);values={r['site_id']:r for r in (job.result or {}).get('entries',[])}
    values.update({r['site_id']:r for r in rows})
    job.result={'entries':[values[sid] for sid in job.payload['site_ids'] if sid in values]}
    if finish:
        job.status='partial' if any(r['status']=='partial' and r.get('included') for r in values.values()) else 'completed';job.finished_at=datetime.now(timezone.utc)
    db.commit()

def public_view(db,job,user,detail=True):
    if not job or job.kind!='maintenance_report' or job.payload.get('task_type')!=TASK:raise HTTPException(404,'Отчёт не найден.')
    allowed=user.get('allowed_site_ids');scope=[s for s in job.payload['site_ids'] if allowed is None or s in allowed]
    if not scope:raise HTTPException(404,'Отчёт не найден.')
    all_rows=[r for r in (job.result or {}).get('entries',[]) if r['site_id'] in scope]
    rows=[r for r in all_rows if r.get('included',False)]
    from app.report_ids import get
    result={'id':job.id,'number':get(db,job),'name':job.payload['name'],'kind':job.payload['report_kind'],'brand':job.payload.get('brand'),'status':job.status,'created_at':job.created_at,'finished_at':job.finished_at,'period_start':job.payload['period_start'],'period_end':job.payload['period_end'],'scope':len(scope),'checked':sum('state_source' in r for r in all_rows),'total':len(rows),'projects_with_work':sum(bool(r.get('events')) for r in rows),'pages_added':sum(r.get('pages_added',0) for r in rows),'text_changes':sum(r.get('text_changes',0) for r in rows),'layout_projects':sum(r.get('layout_work',False) for r in rows),'showcase_projects':sum(r.get('showcase_work',False) for r in rows),'showcase_layout_projects':sum(r.get('showcase_layout_work',False) for r in rows),'template_projects':sum(r.get('template_work',False) for r in rows),'menu_projects':sum(r.get('menu_work',False) for r in rows),'errors':sum(r.get('status')=='partial' for r in rows)}
    if detail:result.update(entries=rows,unverified=[{'site_id':r['site_id'],'project':r['project'],'error':r.get('state_error')} for r in rows if r.get('status')=='partial'])
    return result

@router.get('')
def listing(user:AuthUser,db:Session=Depends(get_db)):
    result=[]
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind=='maintenance_report').order_by(models.BackgroundJob.created_at.desc())):
        if job.payload.get('task_type')!=TASK:continue
        try:result.append(public_view(db,job,user,False))
        except HTTPException:continue
    return {'reports':result}

@router.get('/{report_id}')
def detail(report_id:str,user:AuthUser,db:Session=Depends(get_db)):
    return public_view(db,db.get(models.BackgroundJob,report_id),user)
