"""Authenticated configuration and explicit preview/start API."""
from uuid import UUID, uuid5, NAMESPACE_URL
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, auto_reglue as auto
from app.alternate_templates import template_catalog
from app.db import get_db
from app.security import AuthUser
from app.project_network import NetworkConflict, network_lock
from app.project_cache import ProjectCacheError
import httpx
from app.mass_action_scope import MassActionFilter, constrain
from app import mass_action_reports
from app.pilot_scope import PilotSelection, PilotScopeError

router = APIRouter(prefix='/auto-reglue', tags=['auto-reglue'])
from app.reglue_reserves_api import router as reserves_router
router.include_router(reserves_router)


def site_or_404(db, site_id, user=None):
    site = db.get(models.Site, site_id)
    allowed = user.get('allowed_site_ids') if user else None
    if not site or not site.is_active or (allowed is not None and site.id not in allowed):
        raise HTTPException(404, 'Проект не найден.')
    return site


def allowed_site_ids(user):
    value = user.get('allowed_site_ids')
    return None if value is None else set(value)


def call(fn, *args):
    try: return fn(*args)
    except NetworkConflict as e: raise HTTPException(409, str(e)) from e
    except PilotScopeError as e: raise HTTPException(422, str(e)) from e
    except ValueError as e: raise HTTPException(400, str(e)) from e
    except (ProjectCacheError, httpx.HTTPError) as e: raise HTTPException(502, 'Не удалось прочитать состояние Webdev.') from e


def dispatch(db, run):
    from app.worker import auto_reglue_job
    try: auto_reglue_job.delay(run.id)
    except Exception:
        run.status = 'waiting'; run.message = 'Очередь недоступна. Повторите продолжение запуска.'; db.commit()


class MovePlus2Request(BaseModel):
    request_id: UUID
    filter: MassActionFilter
    site_ids: list[str] = Field(min_length=2, max_length=100)
    count: Literal[1, 2] = 2
    prefetch: bool = True


@router.post('/move-plus2', status_code=202)
def move_plus2(payload: MovePlus2Request, user: AuthUser, db: Session = Depends(get_db)):
    if payload.prefetch:
        from app.move_batch import prepare
        runs,fresh=call(prepare,db,payload.request_id,payload.filter,payload.site_ids,user.get('username') or 'user',allowed_site_ids(user),payload.count)
        if fresh:
            for run in runs:dispatch(db,run)
        return {**auto.serialize(runs[0]),'runs':[auto.serialize(r) for r in runs]}
    from app.move_plus2 import prepare
    run, fresh = call(prepare, db, payload.request_id, payload.filter, payload.site_ids,
                      user.get('username') or 'user', allowed_site_ids(user), payload.count)
    if fresh:
        dispatch(db, run)
    return auto.serialize(run)


def kick_due_schedule(db):
    from datetime import datetime, timezone
    if not db.scalar(select(models.AutoReglueSchedule.site_id).where(
        models.AutoReglueSchedule.enabled.is_(True),
        (models.AutoReglueSchedule.interval_days > 0) | models.AutoReglueSchedule.last_scheduled_at.is_(None),
        models.AutoReglueSchedule.next_run_at <= datetime.now(timezone.utc)).limit(1)):
        return
    from app.worker import schedule_auto_reglue_job
    try:
        schedule_auto_reglue_job.delay()
    except Exception:
        # Durable due date is already saved; Beat retries within a minute.
        pass


def schedule_task(db, site):
    row = db.get(models.AutoReglueSchedule, site.id)
    if not row:
        return None
    return schedule_task_record(site, row, auto.config(db, site.id), auto.next_scheduled_at(db, site))


def schedule_task_record(site, row, rules, next_run_at):
    if row is None:
        return None
    done = row.interval_days == 0 and row.last_scheduled_at is not None
    return {'site_id': site.id, 'project': site.name, 'enabled': row.enabled,
            'scope': rules.scope, 'interval_days': row.interval_days,
            'status': 'disabled' if not row.enabled else 'completed' if done else 'scheduled',
            'next_run_at': next_run_at,
            'url': f'/auto-reglue?project_id={site.id}#auto-task-{site.id}'}


@router.get('')
def overview(user: AuthUser, db: Session = Depends(get_db), project_id: str | None = None):
    allowed = allowed_site_ids(user)
    sites_query = select(models.Site).where(models.Site.project_status == 'mass_actions', models.Site.is_active.is_(True))
    if allowed is not None:
        sites_query = sites_query.where(models.Site.id.in_(allowed))
    sites = db.scalars(sites_query.order_by(models.Site.name)).all()
    query = select(models.AutoReglueRun)
    if allowed is not None:
        query = query.where(models.AutoReglueRun.site_id.in_(allowed))
    if project_id:
        site_or_404(db, project_id, user)
        query = query.where(models.AutoReglueRun.site_id == project_id)
    runs = db.scalars(query.order_by(models.AutoReglueRun.created_at.desc()).limit(100)).all()
    task_query = select(models.Site).join(models.AutoReglueSchedule, models.AutoReglueSchedule.site_id == models.Site.id).where(models.Site.is_active.is_(True))
    if allowed is not None:
        task_query = task_query.where(models.Site.id.in_(allowed))
    task_sites = db.scalars(task_query.order_by(models.Site.name)).all()
    # Missing per-project settings are normal. Session.get() does not cache a
    # missing row, so the former loop repeatedly queried the same defaults.
    # Keep this snapshot local to this read; a later request sees new settings.
    site_ids = {s.id for s in [*sites, *task_sites]}
    config_rows = {row.key: row.value for row in db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.in_([*site_ids, 'global'])))}
    global_rules = auto.GlobalConfig.model_validate(config_rows.get('global', {}))
    project_rules = {site_id: auto.ProjectConfig.model_validate(config_rows.get(site_id, {})) for site_id in site_ids}
    schedules = {row.site_id: row for row in db.scalars(select(models.AutoReglueSchedule).where(
        models.AutoReglueSchedule.site_id.in_(site_ids)))}

    def next_run(site):
        if not auto.schedule_eligible(site, global_rules, project_rules[site.id]):
            return None
        row = schedules.get(site.id)
        return auto.utc(row.next_run_at) if row and row.enabled and not (row.interval_days == 0 and row.last_scheduled_at) else None

    return {'tasks': [schedule_task_record(s, schedules.get(s.id), project_rules[s.id], next_run(s)) for s in task_sites if not project_id or s.id == project_id], 'settings': global_rules.model_dump(),
            'projects': [{'id':s.id,'name':s.name,'geo':s.cache_geo,'next_run_at':next_run(s),'config':project_rules[s.id].model_dump()} for s in sites if project_rules[s.id].scope != 'personal'],
            'language_pool': auto.default_language_pool(), 'templates': template_catalog(), 'runs': [auto.serialize(r) for r in runs]}


@router.put('/settings')
def settings(payload: auto.GlobalConfig, _: AuthUser, db: Session = Depends(get_db)):
    if payload.enabled and payload.schedule_enabled:
        call(constrain, db, payload.selection_filter, allowed_site_ids(_))
    saved = call(auto.save_config, db, payload)
    kick_due_schedule(db)
    return saved


@router.get('/projects/{site_id}')
def project_settings(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site = site_or_404(db, site_id, user)
    runs = db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.site_id==site.id).order_by(models.AutoReglueRun.created_at.desc()).limit(20)).all()
    return {'task': schedule_task(db, site), 'config':auto.config(db,site.id).model_dump(), 'settings':auto.config(db).model_dump(),
            'participation': site.reglue_participation is not False, 'eligible':site.project_status=='mass_actions' or auto.config(db,site.id).scope=='personal', 'geo':site.cache_geo, 'next_run_at':auto.next_scheduled_at(db,site),
            'language_pool':auto.default_language_pool(), 'templates':[p for p in template_catalog() if auto.domain_name(p['project'])==auto.domain_name(site.name)],
            'runs':[auto.serialize(r) for r in runs]}


@router.put('/projects/{site_id}')
def save_project(site_id: str, payload: auto.ProjectConfig, user: AuthUser, db: Session = Depends(get_db)):
    site_or_404(db,site_id,user)
    payload = auto.saved_project_rules(payload)
    effective = auto.effective_project_config(auto.config(db), payload)
    if effective.enabled and effective.domain_layout != 'root_main':
        base_only = auto.effective_config(auto.config(db), payload).scheme_mode in {'base_only', 'clean', 'locale_base'}
        if (effective.parent_kind == 'drop' and not effective.drop_domain
            or effective.parent_kind == 'newreg' and not effective.newreg_domain
            or not base_only and (effective.x_default_use_newreg and not effective.x_default_newreg_domain
                                  or not effective.x_default_use_newreg and not effective.drop_domain)):
            raise HTTPException(400,'Укажите родительский домен и настройки x-default.')
    saved = call(auto.save_config, db, payload, site_id)
    kick_due_schedule(db)
    return saved


class ScopedPreview(BaseModel):
    filter: MassActionFilter


@router.post('/projects/{site_id}/preview')
def preview(site_id: str, user: AuthUser, db: Session = Depends(get_db), scope: Literal['mass', 'project'] = 'mass', payload: ScopedPreview | None = Body(None)):
    db.info.pop('mass_participant_ids', None)
    db.info['cross_allowed_site_ids'] = allowed_site_ids(user)
    site = site_or_404(db,site_id,user)
    db.info.pop('mass_action_filter', None)
    if scope == 'mass':
        call(constrain, db, payload.filter if payload else None, allowed_site_ids(user), [site])
    return call(auto.preview,db,site,scope)


class BatchPreview(BaseModel):
    site_ids: list[str] = Field(min_length=1, max_length=100)
    filter: MassActionFilter


@router.post('/preview-batch')
def preview_batch(payload: BatchPreview, user: AuthUser, db: Session = Depends(get_db)):
    db.info['cross_allowed_site_ids'] = allowed_site_ids(user)
    if len(payload.site_ids) > auto.config(db).max_projects:
        raise HTTPException(400, 'Превышен лимит проектов одного запуска.')
    from app.cross_reglue_batch import build
    sites = [site_or_404(db, site_id, user) for site_id in dict.fromkeys(payload.site_ids)]
    call(constrain, db, payload.filter, allowed_site_ids(user), sites)
    db.info['mass_participant_ids'] = {site.id for site in sites}
    return call(build, db, sites, user['username'])


class StartItem(BaseModel):
    site_id: str
    request_id: UUID
    preview_token: str = Field(min_length=64,max_length=64)


class BatchStart(BaseModel):
    batch_id: UUID | None = None
    scope: Literal["mass", "project"] = "mass"
    items: list[StartItem] = Field(min_length=1,max_length=100)
    filter: MassActionFilter | None = None
    report_id: UUID | None = None


@router.post('/start')
def start(payload: BatchStart, user: AuthUser, db: Session = Depends(get_db)):
    db.info.pop('mass_participant_ids', None)
    db.info['cross_allowed_site_ids'] = allowed_site_ids(user)
    db.info.pop('mass_action_filter', None)
    if payload.scope == 'mass':
        call(constrain, db, payload.filter, allowed_site_ids(user), [site_or_404(db, item.site_id, user) for item in payload.items])
    if payload.scope == 'project' and len(payload.items) != 1: raise HTTPException(400,'Персональный запуск содержит один проект.')
    if payload.scope == 'mass' and len(payload.items)>auto.config(db).max_projects: raise HTTPException(400,'Превышен лимит проектов одного запуска.')
    if len({item.site_id for item in payload.items}) != len(payload.items) or len({item.request_id for item in payload.items}) != len(payload.items):
        raise HTTPException(400, 'В группе повторяется проект или идентификатор запуска.')
    if payload.batch_id:
        if payload.scope != 'mass':
            raise HTTPException(400, 'Группа распределения предназначена для массового запуска.')
        from app.cross_reglue_batch import manifest, reserve
        batch = call(manifest, db, str(payload.batch_id))
        selected = {item.site_id for item in payload.items}
        if batch.value.get('filter') != payload.filter.model_dump():
            raise HTTPException(409, 'Фильтр изменился после подготовки планов. Подготовьте их заново.')
        for plan in batch.value['plans']:
            if plan['site_id'] in selected:
                site_or_404(db, plan['site_id'], user)
                call(constrain, db, payload.filter, allowed_site_ids(user), [site_or_404(db, plan['source_site_id'], user)])
        reservations = call(reserve, db, str(payload.batch_id), [item.model_dump() for item in payload.items], user['username'])
        results = []
        for run, fresh in reservations:
            if fresh: dispatch(db, run)
            results.append({'site_id': run.site_id, 'run': auto.serialize(run)})
        return {'results': results}
    if payload.scope == 'mass' and auto.config(db).execution_mode == 'transfer_only' and len(payload.items) != 1:
        raise HTTPException(400, 'За одно нажатие можно перенести не более двух доменов в одну сетку.')
    if payload.scope == 'mass' and auto.config(db).execution_mode == 'cross_network' and len(payload.items) > 1:
        raise HTTPException(400, 'Подготовьте единый план распределения для массового обмена.')
    report_id = payload.report_id or uuid5(NAMESPACE_URL, 'mass-report:' + auto.digest(sorted(str(item.request_id) for item in payload.items)))
    if payload.scope == 'mass':
        existing_report = db.get(models.AutoReglueConfig, 'mass-report:' + str(report_id))
        if existing_report and existing_report.value['filter'] != payload.filter.model_dump():
            raise HTTPException(409, 'Идентификатор отчёта уже использован для другого фильтра.')
    results=[]
    dispatches=[]
    for item in payload.items:
        try:
            run, fresh = call(auto.prepare_run,db,site_or_404(db,item.site_id,user),item.request_id,item.preview_token,user['username'],payload.scope)
            if fresh: dispatches.append(run)
            results.append({'site_id':item.site_id,'run':auto.serialize(run)})
        except HTTPException as error:
            db.rollback();results.append({'site_id':item.site_id,'error':error.detail})
    if payload.scope == 'mass':
        call(mass_action_reports.save, db, report_id, payload.filter.model_dump(),
                                 [{'site_id': r['site_id'], 'target_project': db.get(models.Site, r['site_id']).name,
                                   **({'run_id': r['run']['id']} if r.get('run') else {'error': r.get('error')})} for r in results], user['username'])
    for run in dispatches:
        dispatch(db, run)
    return {'results':results}


@router.get('/reports')
def reports(brand: str, geo: str, user: AuthUser, db: Session = Depends(get_db)):
    try:
        filters = MassActionFilter(brand=brand, geo=geo)
    except ValueError as error:
        raise HTTPException(422, 'Выберите бренд и GEO отчёта.') from error
    return {'reports': mass_action_reports.list_reports(db, filters.brand, filters.geo, allowed_site_ids(user))}


class ReportCheckRequest(BaseModel):
    request_id: UUID
    filter: MassActionFilter


@router.post('/reports/check',status_code=202)
def check_reports(payload: ReportCheckRequest,user: AuthUser,db: Session=Depends(get_db)):
    from app.transfer_report_check import prepare,serialize
    job,_=call(prepare,db,payload.request_id,payload.filter,user['username'],allowed_site_ids(user))
    return serialize(job)


@router.get('/reports/check')
def report_check_status(brand: str,geo: str,user: AuthUser,db: Session=Depends(get_db)):
    from app.transfer_report_check import KIND,visible,serialize
    filters=MassActionFilter(brand=brand,geo=geo)
    jobs=db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind==KIND)
                   .order_by(models.BackgroundJob.created_at.desc())).all()
    job=next((j for j in jobs if mass_action_reports.brand_key(j.payload['brand'])==mass_action_reports.brand_key(filters.brand)
              and j.payload['geo']==filters.geo and visible(db,j,allowed_site_ids(user))),None)
    return serialize(job) if job else None


@router.get('/transfer-queue')
def transfer_queue(brand: str,geo: str,user: AuthUser,db: Session=Depends(get_db)):
    from app.domain_transfer_queue import listing
    filters=MassActionFilter(brand=brand,geo=geo)
    return listing(db,filters.brand,filters.geo,allowed_site_ids(user))


@router.post('/runs/{run_id}/{action}')
def control(run_id: str, action: str, user: AuthUser, db: Session = Depends(get_db)):
    run=db.get(models.AutoReglueRun,run_id)
    allowed = allowed_site_ids(user)
    if not run or (allowed is not None and run.site_id not in allowed):
        raise HTTPException(404,'Запуск не найден.')
    if run.plan.get('source_site_id'):
        site_or_404(db, run.plan['source_site_id'], user)
    if action == 'check':
        from datetime import datetime, timezone
        from uuid import uuid4
        from app.worker import auto_reglue_recheck_job
        check_request_id = str(uuid4())
        def prepare_check():
            with network_lock(db, 'auto-run:' + run.id):
                db.refresh(run)
                if run.status == 'cancelled': raise HTTPException(409, 'Переклей отменён.')
                if not run.plan.get('list_launch_id') or run.plan.get('execution_mode') != 'cross_network':
                    raise HTTPException(400, 'Проверка доступна для сохранённого плана Auto Pilot.')
                run.plan = {**run.plan, 'verification': {'status': 'queued', 'requested_at': datetime.now(timezone.utc).isoformat(), 'checks': []}}
                db.commit()
        call(prepare_check)
        try:
            auto_reglue_recheck_job.delay(run.id, retry_title_h1=True, request_id=check_request_id)
        except Exception:
            run.plan = {**run.plan, 'verification': {'status': 'failed', 'code': 'QUEUE_UNAVAILABLE', 'message': 'Очередь проверки недоступна. Повторите обновление.', 'checks': []}}
            db.commit()
            raise HTTPException(503, 'Очередь проверки недоступна. Повторите обновление.')
        return auto.serialize(run)
    if action == 'rollback':
        from app.domain_redistribution import prepare_rollback
        inverse, fresh = call(prepare_rollback, db, run, user['username'])
        if fresh: dispatch(db, inverse)
        return auto.serialize(inverse)
    if action not in {'resume','cancel'}:raise HTTPException(400,'Неизвестное действие.')
    try:
        with network_lock(db,'auto-run:'+run.id):
            db.refresh(run)
            if run.status not in auto.ACTIVE:raise HTTPException(409,'Запуск уже завершён.')
            if action=='cancel':
                run.status='cancelled';run.message='Остановлен. Уже подтверждённые изменения не отменяются.';db.commit()
            else:
                run.status='waiting';db.commit()
    except NetworkConflict as e: raise HTTPException(409,'Этап ещё выполняется. Дождитесь завершения запроса.') from e
    if run.plan.get('reserve_pool_id'):
        from app.reglue_reserves import sync_result
        sync_result(db, run)
    if action == 'resume': dispatch(db, run)
    return auto.serialize(run)


@router.get('/brands')
def brands(user: AuthUser, db: Session = Depends(get_db)):
    """Read-only inventory for future cross-project experiments. Never transfers domains."""
    import re
    import unicodedata
    groups = {}
    query = select(models.Site).where(models.Site.is_active.is_(True)).order_by(models.Site.name)
    allowed = allowed_site_ids(user)
    if allowed is not None:
        query = query.where(models.Site.id.in_(allowed))
    for site in db.scalars(query):
        brand = (site.brand or '').strip()
        if not brand or brand.casefold() == 'общие ключи':
            continue
        key = re.sub(r'[\s\-–—_]+', '', unicodedata.normalize('NFKC', brand).casefold())
        group = groups.setdefault(key, {'key': key, 'brand': brand, 'projects': [], 'project_count': 0, 'domain_count': 0})
        count = max(0, site.domains_count or 0)
        group['projects'].append({'id': site.id, 'name': site.name, 'geo': site.cache_geo,
                                 'domain_count': count, 'synced_at': site.cache_synced_at})
        group['project_count'] += 1
        group['domain_count'] += count
    return {'brands': sorted(groups.values(), key=lambda g: (-g['project_count'], g['brand'].casefold())),
            'counts_source': 'project_cache', 'transfers_enabled': False}


class ContentBatch(BaseModel):
    request_id: UUID
    site_ids: list[str] = Field(min_length=1, max_length=100)
    action: Literal['meta_headings','full_title_h1','full_title_headings','paragraphs','trim_50','trim_99']
    provider_id: str | None = None
    filter: MassActionFilter


@router.post('/content-drafts')
def content_drafts(payload: ContentBatch, user: AuthUser, db: Session = Depends(get_db)):
    from app import project_pages as pages
    from app.page_content_tools import targets, validate_heading_scope
    from copy import deepcopy
    selected=[site_or_404(db, sid, user) for sid in dict.fromkeys(payload.site_ids)]
    call(constrain, db, payload.filter, allowed_site_ids(user), selected)
    if any(site.project_status!='mass_actions' for site in selected):
        raise HTTPException(400,'Массовая обработка доступна только для статуса «Массовые действия».')
    provider=db.get(models.AiProvider,payload.provider_id) if payload.provider_id else None
    trimming=payload.action in {'trim_50','trim_99'}
    if not trimming and (not provider or not provider.is_active or provider.provider_type!='gemini' or not provider.api_key):
        raise HTTPException(422,'Выберите активный Gemini-провайдер.')
    key='content-batch:'+str(payload.request_id)
    with network_lock(db,key):
        ledger=db.get(models.AutoReglueConfig,key)
        signature=auto.digest(payload.model_dump(mode='json'))
        if ledger and ledger.value['signature']!=signature:
            raise HTTPException(409,'Идентификатор уже используется другой массовой обработкой.')
        results=list(ledger.value['results']) if ledger else []
        done={result['site_id'] for result in results}
        from app.short_h1 import allocate
        heading_action = payload.action in {'meta_headings', 'full_title_h1', 'full_title_headings'}
        short_ids=set(allocate([site.id for site in selected],payload.request_id)) if heading_action else set()
        for site in selected:
            if site.id in done:continue
            try:
                with pages.remote_errors(), pages.Remote(db,site) as remote:
                    project = remote.project()
                    home=next((page for page in pages.pages(project) if pages.is_home(page)),None)
                if home is None:raise ValueError('Главная страница не найдена.')
                content=pages.PageEdit.editor_document(deepcopy(home.get('content') or {}))
                mode = validate_heading_scope(project, pages.page_key(home), content, payload.action)
                if mode and not (home.get('title') or '').strip():
                    raise ValueError('Для полного переписывания нужен исходный Title страницы.')
                if payload.action!='meta_headings' and not targets(content,payload.action):
                    raise ValueError('Нет подходящих блоков для обработки.')
                draft=models.ProjectPageDraft(site_id=site.id,page_key=pages.page_key(home),requested_by=user['username'],
                    provider_id=provider.id if provider else None,action=payload.action,input_content=content,
                    input_metadata={'title':home.get('title') or '', 'description':home.get('description') or '',
                                    'revision': pages.digest(home),
                                    **({'title_rewrite_mode': mode} if mode else {}),
                                    **({'short_h1':site.id in short_ids} if heading_action else {})})
                db.add(draft);db.flush()
                db.add(models.BackgroundJob(kind='project_page_ai',payload={'draft_id':draft.id, 'mass_filter': payload.filter.model_dump()}))
                results.append({'site_id':site.id,'project':site.name,'draft_id':draft.id,'status':'queued',
                                'url':f'/project-content/{site.name}/'})
            except (ValueError,HTTPException) as error:
                db.rollback()
                results.append({'site_id':site.id,'project':site.name,'error':str(getattr(error,'detail',error))[:1000]})
            ledger=db.get(models.AutoReglueConfig,key)
            if ledger is None:
                ledger=models.AutoReglueConfig(key=key,value={});db.add(ledger)
            ledger.value={'signature':signature,'results':list(results)}
            db.commit()
        return {'results':results}


@router.get('/content-drafts/{request_id}')
def content_batch_status(request_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    ledger=db.get(models.AutoReglueConfig,'content-batch:'+str(request_id))
    if not ledger:raise HTTPException(404,'Массовая обработка не найдена.')
    results=[]
    for item in ledger.value['results']:
        site_or_404(db,item['site_id'],user)
        result=dict(item)
        if item.get('draft_id'):
            draft=db.get(models.ProjectPageDraft,item['draft_id'])
            if draft:result.update(status=draft.status,error=draft.error)
        results.append(result)
    return {'results':results}


class ParticipationRequest(BaseModel):
    enabled: bool


@router.patch('/projects/{site_id}/participation')
def participation(site_id: str, payload: ParticipationRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app.schemas import SiteResponse
    site = site_or_404(db, site_id, user)
    site.reglue_participation = payload.enabled
    db.commit(); db.refresh(site)
    return SiteResponse.model_validate(site)


class ListLaunchRequest(BaseModel):
    request_id: UUID
    site_ids: list[str] = Field(min_length=1, max_length=10000)


@router.post('/list-launch', status_code=202)
def launch_list(payload: ListLaunchRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app.mass_reglue_launch import enqueue, view
    job = call(enqueue, db, payload.request_id, payload.site_ids, user['username'], allowed_site_ids(user))
    # Durable dispatcher retries automatically if the broker is temporarily unavailable.
    return view(db, job)


@router.get('/list-launch')
def latest_list_launch(user: AuthUser, db: Session = Depends(get_db)):
    from app.mass_reglue_launch import KIND, view
    allowed = allowed_site_ids(user)
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND).order_by(models.BackgroundJob.created_at.desc()).limit(100)):
        if job.payload['actor'] == user['username'] and (allowed is None or set(job.payload['site_ids']).issubset(allowed)):
            return view(db, job)
    return None


from app.pilot_variations import PilotPercentages, TitleRewriteMode
from app.pilot_mixed import PlanningMode


class PilotPreviewRequest(PilotSelection):
    request_id: UUID
    title_rewrite_mode: TitleRewriteMode = 'mixed'
    planning_mode: PlanningMode = 'percentages'
    allow_stock_drops: bool = True
    percentages: PilotPercentages | None = None
    brand: str = Field(default="", max_length=200)
    geo: str = Field(default="", max_length=16)


@router.post('/pilot', status_code=202)
def prepare_pilot(payload: PilotPreviewRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    return auto_pilot.view(db, call(lambda: auto_pilot.create(db, payload.request_id, user, payload.brand, payload.geo,
        payload.percentages.model_dump() if payload.percentages else None,
        brands=payload.brands if 'brands' in payload.model_fields_set else None,
        geos=payload.geos if 'geos' in payload.model_fields_set else None, title_rewrite_mode=payload.title_rewrite_mode, scope_mode=payload.scope_mode, planning_mode=payload.planning_mode, allow_stock_drops=payload.allow_stock_drops)))


@router.get('/pilot')
def latest_pilot(user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind.in_(['auto_pilot_preview','mass_reglue_list'])).order_by(models.BackgroundJob.created_at.desc()).limit(100)):
        if job.payload.get('auto_pilot') and job.payload.get('actor')==user['username'] and not auto_pilot.deleted(db, job.id):
            return auto_pilot.view(db, call(auto_pilot.get, db, job.id, user))
    return None


@router.get('/pilot/tasks')
def pilot_tasks(user: AuthUser, offset: int = Query(0,ge=0), limit: int = Query(50,ge=1,le=100), q: str = Query('',max_length=200), group: str = Query('all', pattern='^(all|layout|showcases|reglues|brands|other)$'), refresh: bool = False, db: Session = Depends(get_db)):
    from app import pilot_task_cache
    return pilot_task_cache.tasks(db,user,offset,limit,q=q,group=group,refresh=refresh)


@router.get('/pilot/task-collection')
def pilot_task_collection(user: AuthUser, q: str = Query('',max_length=200), refresh: bool = False, db: Session = Depends(get_db)):
    from app import pilot_task_cache
    # One compact permission-scoped snapshot; tabs and pagination reuse it.
    return pilot_task_cache.tasks(db,user,limit=None,q=q,refresh=refresh)


@router.get('/maintenance-reports/{report_id}')
def maintenance_report(report_id: UUID, user: AuthUser, db: Session = Depends(get_db), archive: bool = False):
    from app import maintenance_reports
    try:
        job = db.get(models.BackgroundJob, str(report_id))
        if job and job.payload.get('maintenance_archive_key'):
            from app import auto_pilot, report_ids
            auto_pilot.get(db, report_id, user)
            if not archive:
                return {'pilot_report_url':f'/auto-reglue/pilot?id={job.id}'}
            from types import SimpleNamespace
            saved = db.get(models.AutoReglueConfig, job.payload['maintenance_archive_key']).value
            historic = SimpleNamespace(id=job.id, kind=maintenance_reports.KIND, payload=saved['payload'], result=saved['result'], status=saved['status'], created_at=job.created_at, started_at=job.created_at, finished_at=None, updated_at=saved['archived_at'])
            return {**maintenance_reports.view(historic), 'report_id':report_ids.get(db,job), 'can_exclude':False}
        return maintenance_reports.view(maintenance_reports.get(db, report_id, user), db)
    except ValueError as error:
        raise HTTPException(404, 'Отчёт не найден.') from error


class MaintenanceRepeatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    allow_reserve: bool = Field(default=False, strict=True)


@router.post('/maintenance-reports/{report_id}/repeat')
def repeat_maintenance_report(report_id: UUID, payload: MaintenanceRepeatRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import maintenance_reports, maintenance_repeat
    try:
        maintenance_reports.get(db, report_id, user)
    except ValueError as error:
        raise HTTPException(404, 'Отчёт не найден.') from error
    job = call(maintenance_repeat.create, db, report_id, payload.request_id, user, payload.allow_reserve)
    return maintenance_reports.view(job, db)


@router.get('/pilot/options')
def pilot_options(user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    return auto_pilot.scope_options(db, user)


@router.get('/pilot/{job_id}')
def read_pilot(job_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    return auto_pilot.view(db, call(auto_pilot.get, db, job_id, user))


@router.post('/pilot/{job_id}/start', status_code=202)
def start_pilot(job_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    return auto_pilot.view(db, call(auto_pilot.start, db, job_id, user))


@router.delete('/pilot/{job_id}')
def delete_pilot_draft(job_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    return call(auto_pilot.delete_draft, db, job_id, user)


@router.delete('/reports/{report_id}')
def delete_report_from_list(report_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    from app.report_list_visibility import hide
    return call(hide, db, report_id, user)


@router.post('/pilot/{job_id}/rows/{site_id}/refresh')
def refresh_pilot_row(job_id: UUID, site_id: UUID, payload: PilotPreviewRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot
    return auto_pilot.view(db, call(auto_pilot.refresh_row, db, job_id, site_id, payload.request_id, user))


@router.post('/pilot/{job_id}/rows/{site_id}/alternative', status_code=202)
def alternative_pilot_row(job_id: UUID, site_id: UUID, payload: PilotPreviewRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot, pilot_row_replan
    return auto_pilot.view(db, call(pilot_row_replan.request, db, job_id, site_id, payload.request_id, user))


@router.post('/pilot/{job_id}/rows/{site_id}/alternative/start', status_code=202)
def start_alternative_pilot_row(job_id: UUID, site_id: UUID, payload: PilotPreviewRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot, pilot_row_replan
    return auto_pilot.view(db, call(pilot_row_replan.start, db, job_id, site_id, payload.request_id, user))


@router.post('/pilot/{job_id}/prepare', status_code=202)
def reprepare_pilot(job_id: UUID, payload: PilotPreviewRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot, pilot_replanning
    from app.pilot_scope import selection
    scope = call(lambda: selection(brand=payload.brand, geo=payload.geo,
        brands=payload.brands if 'brands' in payload.model_fields_set else None,
        geos=payload.geos if 'geos' in payload.model_fields_set else None, scope_mode=payload.scope_mode))
    job = call(lambda: pilot_replanning.request(db, job_id, payload.request_id, user, scope=scope,
        percentages=payload.percentages.model_dump() if payload.percentages else None, title_rewrite_mode=payload.title_rewrite_mode, planning_mode=payload.planning_mode, allow_stock_drops=payload.allow_stock_drops))
    return auto_pilot.view(db, job)


class PilotVersionRequest(BaseModel):
    version: int = Field(ge=1, le=5, strict=True)


@router.post('/pilot/{job_id}/rows/{site_id}/version')
def select_pilot_version(job_id: UUID, site_id: UUID, payload: PilotVersionRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import auto_pilot, pilot_versions
    return auto_pilot.view(db, call(pilot_versions.select_version, db, job_id, site_id, payload.version, user))


@router.get("/projects/{site_id}/history")
def automatic_history(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site = site_or_404(db, site_id, user)
    from app.automatic_history import timeline
    return {"items": timeline(db, site.id)}


@router.post('/reports/{report_id}/projects/{site_id}/exclude')
def exclude_report_project(report_id: UUID, site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    from app import report_membership, maintenance_reports, auto_pilot
    job = call(report_membership.exclude, db, report_id, site_id, user)
    return maintenance_reports.view(job, db) if job.kind == maintenance_reports.KIND else auto_pilot.view(db, job)
