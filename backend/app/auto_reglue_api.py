"""Admin-only configuration and explicit preview/start API."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, auto_reglue as auto
from app.alternate_templates import template_catalog
from app.db import get_db
from app.security import AdminUser
from app.project_network import NetworkConflict, network_lock
from app.project_cache import ProjectCacheError
import httpx

router = APIRouter(prefix='/auto-reglue', tags=['auto-reglue'])


def site_or_404(db, site_id):
    site = db.get(models.Site, site_id)
    if not site: raise HTTPException(404, 'Проект не найден.')
    return site


def call(fn, *args):
    try: return fn(*args)
    except NetworkConflict as e: raise HTTPException(409, str(e)) from e
    except ValueError as e: raise HTTPException(400, str(e)) from e
    except (ProjectCacheError, httpx.HTTPError) as e: raise HTTPException(502, 'Не удалось прочитать состояние Webdev.') from e


def dispatch(db, run):
    from app.worker import auto_reglue_job
    try: auto_reglue_job.delay(run.id)
    except Exception:
        run.status = 'waiting'; run.message = 'Очередь недоступна. Повторите продолжение запуска.'; db.commit()


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


@router.get('')
def overview(_: AdminUser, db: Session = Depends(get_db)):
    sites = db.scalars(select(models.Site).where(models.Site.project_status == 'mass_actions').order_by(models.Site.name)).all()
    runs = db.scalars(select(models.AutoReglueRun).order_by(models.AutoReglueRun.created_at.desc()).limit(100)).all()
    return {'settings': auto.config(db).model_dump(),
            'projects': [{'id':s.id,'name':s.name,'geo':s.cache_geo,'next_run_at':auto.next_scheduled_at(db,s),'config':auto.config(db,s.id).model_dump()} for s in sites if auto.config(db,s.id).scope != 'personal'],
            'language_pool': auto.default_language_pool(), 'templates': template_catalog(), 'runs': [auto.serialize(r) for r in runs]}


@router.put('/settings')
def settings(payload: auto.GlobalConfig, _: AdminUser, db: Session = Depends(get_db)):
    saved = call(auto.save_config, db, payload)
    kick_due_schedule(db)
    return saved


@router.get('/projects/{site_id}')
def project_settings(site_id: str, _: AdminUser, db: Session = Depends(get_db)):
    site = site_or_404(db, site_id)
    runs = db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.site_id==site.id).order_by(models.AutoReglueRun.created_at.desc()).limit(20)).all()
    return {'config':auto.config(db,site.id).model_dump(), 'settings':auto.config(db).model_dump(),
            'eligible':site.project_status=='mass_actions' or auto.config(db,site.id).scope=='personal', 'geo':site.cache_geo, 'next_run_at':auto.next_scheduled_at(db,site),
            'language_pool':auto.default_language_pool(), 'templates':[p for p in template_catalog() if auto.domain_name(p['project'])==auto.domain_name(site.name)],
            'runs':[auto.serialize(r) for r in runs]}


@router.put('/projects/{site_id}')
def save_project(site_id: str, payload: auto.ProjectConfig, _: AdminUser, db: Session = Depends(get_db)):
    site_or_404(db,site_id)
    payload = auto.saved_project_rules(payload)
    effective = auto.effective_project_config(auto.config(db), payload)
    if effective.enabled and effective.domain_layout != 'root_main':
        base_only = auto.effective_config(auto.config(db), payload).scheme_mode == 'base_only'
        if (effective.parent_kind == 'drop' and not effective.drop_domain
            or effective.parent_kind == 'newreg' and not effective.newreg_domain
            or not base_only and (effective.x_default_use_newreg and not effective.x_default_newreg_domain
                                  or not effective.x_default_use_newreg and not effective.drop_domain)):
            raise HTTPException(400,'Укажите родительский домен и настройки x-default.')
    saved = call(auto.save_config, db, payload, site_id)
    kick_due_schedule(db)
    return saved


@router.post('/projects/{site_id}/preview')
def preview(site_id: str, _: AdminUser, db: Session = Depends(get_db), scope: Literal['mass', 'project'] = 'mass'):
    return call(auto.preview,db,site_or_404(db,site_id),scope)


class StartItem(BaseModel):
    site_id: str
    request_id: UUID
    preview_token: str = Field(min_length=64,max_length=64)


class BatchStart(BaseModel):
    scope: Literal["mass", "project"] = "mass"
    items: list[StartItem] = Field(min_length=1,max_length=100)


@router.post('/start')
def start(payload: BatchStart, user: AdminUser, db: Session = Depends(get_db)):
    if payload.scope == 'project' and len(payload.items) != 1: raise HTTPException(400,'Персональный запуск содержит один проект.')
    if payload.scope == 'mass' and len(payload.items)>auto.config(db).max_projects: raise HTTPException(400,'Превышен лимит проектов одного запуска.')
    results=[]
    for item in payload.items:
        try:
            run, fresh = call(auto.prepare_run,db,site_or_404(db,item.site_id),item.request_id,item.preview_token,user['username'],payload.scope)
            if fresh: dispatch(db,run)
            results.append({'site_id':item.site_id,'run':auto.serialize(run)})
        except HTTPException as error:
            db.rollback();results.append({'site_id':item.site_id,'error':error.detail})
    return {'results':results}


@router.post('/runs/{run_id}/{action}')
def control(run_id: str, action: str, _: AdminUser, db: Session = Depends(get_db)):
    run=db.get(models.AutoReglueRun,run_id)
    if not run:raise HTTPException(404,'Запуск не найден.')
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
    if action == 'resume': dispatch(db, run)
    return auto.serialize(run)
