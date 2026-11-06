"""Durable menu previews; applying a preview is a separate, at-most-once step."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app import models
from app.schemas import MenuStructurePreviewRequest, GeneratedMenuStructureApply

KIND = 'menu_generation'


def event(row, status, message):
    row.result = {**(row.result or {}), 'events': [*(row.result or {}).get('events', []),
                  {'at': now().isoformat(), 'status': status, 'message': message}][-50:]}


def recover_interrupted(db):
    """Only retry read-only generation after its worker has released the job lock."""
    from app.project_network import network_lock, NetworkConflict
    ids = db.scalars(select(models.BackgroundJob.id).where(
        models.BackgroundJob.kind == KIND,
        models.BackgroundJob.status.in_(['generating', 'applying']),
        models.BackgroundJob.started_at < now() - timedelta(minutes=5))).all()
    for job_id in ids:
        try:
            with network_lock(db, 'menu-generation:' + job_id):
                row = db.get(models.BackgroundJob, job_id, populate_existing=True)
                if row.status not in {'generating', 'applying'}:
                    continue
                if row.status == 'generating' and (row.result or {}).get('attempts', 1) < 2:
                    row.status = 'queued'; row.dispatched_at = None
                    event(row, 'queued', 'Обработчик прерван. Генерация структуры поставлена на повтор.')
                else:
                    row.error = ('Обработчик прерван во время применения меню. Требуется проверка результата на сайте.'
                                 if row.status == 'applying' else 'Генерация прервана повторно. Требуется новая попытка.')
                    row.status = 'failed'; row.finished_at = now()
                    event(row, 'failed', row.error)
                db.commit()
        except NetworkConflict:
            db.rollback()

class Request(BaseModel):
    request_id: UUID
    settings: MenuStructurePreviewRequest
    operation: Literal['append', 'replace'] = 'append'
    create_pages: bool = False


def now():
    return datetime.now(timezone.utc)


def expire(db):
    rows = db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND, models.BackgroundJob.status == 'awaiting_review').with_for_update(skip_locked=True)).all()
    for row in rows:
        expiry = (row.result or {}).get('expires_at')
        if expiry and datetime.fromisoformat(expiry) <= now():
            logs = db.scalars(select(models.PublicationLog).where(models.PublicationLog.endpoint_url == f"internal://sites/{row.payload['site_id']}/menu-structure-preview")).all()
            for log in logs:
                if (log.request_payload or {}).get('menu_generation_job_id') == row.id:
                    log.response_body = {'expired': True}
            row.status = 'expired'
            row.result = {'expired_at': now().isoformat()}
            row.finished_at = now()
    db.commit()


def view(db, row):
    result = row.result or {}
    task_id = (result.get('applied') or {}).get('page_task_id')
    pages = db.scalars(select(models.ContentItem).where(models.ContentItem.task_id == task_id)).all() if task_id else []
    progress = {'total': len(pages), 'generated': sum(p.generated_at is not None for p in pages),
                'published': sum(p.status == 'published' for p in pages),
                'deleted': sum(p.status == 'deleted' for p in pages),
                'errors': sum(p.status in {'generation_failed', 'publication_failed', 'failed'} for p in pages)}
    site = db.get(models.Site, row.payload['site_id'])
    return {'id': row.id, 'status': row.status, 'error': row.error, 'created_at': row.created_at,
            'site_id': row.payload['site_id'], 'project_name': site.name if site else '',
            'started_at': row.started_at, 'finished_at': row.finished_at,
            'settings': row.payload['settings'], 'operation': row.payload['operation'],
            'create_pages': row.payload['create_pages'], **result,
            'progress': progress,
            'pages': [{'id': p.id, 'topic': p.topic, 'slug': p.slug, 'status': p.status,
                       'generation_progress': p.generation_progress, 'error': p.generation_error} for p in pages]}


def get(db, site_id, job_id):
    row = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == str(job_id)).with_for_update())
    if not row or row.kind != KIND or row.payload['site_id'] != site_id:
        raise HTTPException(404, 'Задание не найдено.')
    return row


def create(db, site, request, user):
    existing = db.get(models.BackgroundJob, str(request.request_id))
    payload = {'site_id': site.id, 'settings': request.settings.model_dump(mode='json'),
               'operation': request.operation, 'create_pages': request.create_pages,
               'actor': {'id': user['id'], 'username': user['username']},
               'baseline_menu': site.default_menu}
    if existing:
        if existing.kind != KIND or existing.payload != payload:
            raise HTTPException(409, 'Идентификатор задания уже используется.')
        return view(db, existing)
    row = models.BackgroundJob(id=str(request.request_id), kind=KIND, status='queued', payload=payload)
    event(row, 'queued', 'Задание принято в очередь генерации меню.')
    db.add(row); db.commit()
    return view(db, row)


def accept(db, site_id, job_id, payload):
    expire(db)
    row = get(db, site_id, job_id)
    if row.status != 'awaiting_review':
        raise HTTPException(409, 'Результат уже принят или срок хранения истёк.')
    if payload.menu_type != row.payload['settings']['menu_type'] or payload.operation != row.payload['operation']:
        raise HTTPException(409, 'Тип меню и действие изменились. Создайте новое задание.')
    row.payload = {**row.payload, 'accepted': payload.model_dump(mode='json')}
    row.status = 'queued'; row.dispatched_at = None
    event(row, 'queued', 'Результат принят. Ожидает применения к сайту.')
    db.commit()
    return view(db, row)


def execute(db, job_id):
    from app.project_network import network_lock, NetworkConflict
    try:
        with network_lock(db, 'menu-generation:' + job_id):
            return _execute(db, job_id)
    except NetworkConflict:
        db.rollback(); return {'status': 'busy'}


def _execute(db, job_id):
    row = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == job_id).with_for_update())
    if not row or row.status != 'queued':
        db.rollback(); return {'status': 'skipped'}
    applying = bool(row.payload.get('accepted'))
    row.status = 'applying' if applying else 'generating'
    if not applying:
        row.result = {**(row.result or {}), 'attempts': (row.result or {}).get('attempts', 0) + 1}
    event(row, row.status, 'Применяем структуру меню.' if applying else 'Генерируем структуру меню.')
    row.started_at = now(); db.commit()
    try:
        from app.api import preview_site_menu_structure, apply_site_generated_menu_structure
        site_id = row.payload['site_id']; actor = row.payload['actor']
        if not applying:
            db.info['menu_generation_job_id'] = row.id
            preview = asyncio.run(preview_site_menu_structure(site_id, MenuStructurePreviewRequest.model_validate(row.payload['settings']), actor, db))
            db.refresh(row)
            if row.status == 'cancelled': return {'status': 'cancelled'}
            row.result = {**(row.result or {}), 'preview': preview, 'expires_at': (now() + timedelta(hours=24)).isoformat()}
            if not row.payload['create_pages']:
                row.status = 'awaiting_review'
                event(row, row.status, 'Структура готова. Результат хранится 24 часа до принятия.')
                db.commit(); return {'status': row.status}
            accepted = GeneratedMenuStructureApply.model_validate({**preview, 'operation': row.payload['operation'], 'create_pages': True})
            row.payload = {**row.payload, 'accepted': accepted.model_dump(mode='json')}
            row.status = 'queued'; row.dispatched_at = None
            event(row, row.status, 'Структура готова. Применение и создание страниц выполнятся автоматически.')
            db.commit()
            return {'status': 'queued'}
        # Never retry an applying job after a lost worker: remote writes may have succeeded.
        site = db.get(models.Site, site_id)
        if site.default_menu != row.payload['baseline_menu']:
            raise ValueError('Меню изменилось после начала генерации. Проверьте результат и создайте новый план.')
        accepted = GeneratedMenuStructureApply.model_validate(row.payload['accepted'])
        from app.project_network import network_lock
        with network_lock(db, site_id):
            applied = asyncio.run(apply_site_generated_menu_structure(site_id, accepted, actor, db))
        if not applied.get('success'):
            raise ValueError('Сервер не подтвердил применение меню: ' + str(applied.get('results', ''))[:500])
        db.refresh(row)
        row.result = {**(row.result or {}), 'applied': applied, 'applied_at': now().isoformat()}
        row.status = 'completed'; row.finished_at = now()
        event(row, row.status, 'Меню добавлено. Генерация страниц выполняется в очереди текстов.' if applied.get('page_task_id') else 'Меню добавлено на сайт.')
        db.commit()
        return {'status': row.status}
    except Exception as error:
        db.rollback(); row = db.get(models.BackgroundJob, job_id)
        row.status = 'failed'; row.error = str(getattr(error, 'detail', error))[:1000]
        event(row, 'failed', row.error)
        row.finished_at = now(); db.commit()
        return {'status': 'failed'}
