"""Durable FIFO for fake-page changes. Enqueue never contacts Webdev."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid5

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import models, project_network as network
from app.fake_main import normalize_fake_path

KIND = 'fake_main_queue'
LIMIT = 10
TERMINAL = ('completed', 'failed', 'cancelled')


class Request(BaseModel):
    request_id: UUID
    action: Literal['delete', 'create', 'select']
    path: str = Field(min_length=1, max_length=250)


def query(site_id):
    return select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload['site_id'].as_string() == str(site_id))


def active(db, site_id):
    return list(db.scalars(query(site_id).where(models.BackgroundJob.status.not_in(TERMINAL))
        .order_by(models.BackgroundJob.payload['sequence'].as_integer(), models.BackgroundJob.id)))


def item(job):
    receipt = str(job.id)
    return {'id': job.id, 'action': job.payload['action'], 'path': job.payload['path'],
        'status': job.status if job.status in TERMINAL else (job.result or {}).get('phase', 'queued'),
        'message': job.error or (job.result or {}).get('message', 'В очереди'),
        'operation_ids': [receipt, str(uuid5(UUID(receipt), 'fake-main-head'))],
        'created_at': job.created_at, 'finished_at': job.finished_at}


def snapshot(db, site, *, include=None):
    pending = active(db, site.id)
    recent = list(db.scalars(query(site.id).where(models.BackgroundJob.status.in_(TERMINAL))
        .order_by(models.BackgroundJob.created_at.desc(), models.BackgroundJob.id.desc()).limit(20)))
    if include and all(job.id != include.id for job in [*pending, *recent]):
        recent.insert(0, include)
    state = site.network_state or {}
    return {'items': [item(job) for job in [*pending, *recent]], 'limit': LIMIT,
        'active_count': len(pending),
        'network': network.result(db, site, state) if state.get('has_head') and 'domains' in state else None}


def enqueue(db, site, payload, actor):
    # A short DB row lock, independent from the lock held during slow Webdev I/O.
    db.execute(select(models.Site.id).where(models.Site.id == site.id).with_for_update()).scalar_one()
    path = normalize_fake_path(payload.path)
    existing = db.get(models.BackgroundJob, str(payload.request_id))
    if existing:
        if existing.kind != KIND or any(existing.payload.get(k) != v for k, v in
                {'site_id': site.id, 'action': payload.action, 'path': path}.items()):
            raise network.NetworkConflict('Идентификатор запроса уже используется другой задачей.')
        db.commit()
        return snapshot(db, site)
    pending = active(db, site.id)
    if any(job.payload['path'] == path and job.payload['action'] == payload.action for job in pending):
        db.commit()
        return snapshot(db, site)
    if len(pending) >= LIMIT:
        raise network.NetworkConflict('В очереди уже 10 страниц. Дождитесь завершения одной задачи.')
    if payload.action == 'delete' and path == (site.network_state or {}).get('fake_main_current'):
        raise ValueError('Перед удалением текущей страницы назначьте другую.')
    last = db.scalar(query(site.id).order_by(models.BackgroundJob.payload['sequence'].as_integer().desc()).limit(1))
    sequence = (last.payload.get('sequence', 0) if last else 0) + 1
    job = models.BackgroundJob(id=str(payload.request_id), kind=KIND, status='queued',
        payload={'site_id': site.id, 'project': site.name, 'action': payload.action, 'path': path,
                 'actor': actor, 'sequence': sequence}, result={'phase': 'queued', 'message': 'В очереди'})
    db.add(job); db.commit()
    return snapshot(db, site)


def cancel(db, site, payload, actor):
    """Keep a tombstone so a late enqueue response cannot resurrect the request."""
    with network.network_lock(db, site.id):
        db.execute(select(models.Site.id).where(models.Site.id == site.id).with_for_update()).scalar_one()
        path = normalize_fake_path(payload.path)
        job = db.get(models.BackgroundJob, str(payload.request_id))
        if job and (job.kind != KIND or any(job.payload.get(k) != v for k, v in
                {'site_id': site.id, 'action': payload.action, 'path': path}.items())):
            raise network.NetworkConflict('Задача относится к другому запросу.')
        if job and job.status in TERMINAL:
            return snapshot(db, site, include=job)
        if job is None:
            job = models.BackgroundJob(id=str(payload.request_id), kind=KIND, status='queued',
                payload={'site_id': site.id, 'project': site.name, 'action': payload.action,
                         'path': path, 'actor': actor, 'sequence': 0})
            db.add(job)
        receipt = db.get(models.NetworkOperation, str(payload.request_id))
        if receipt and receipt.status == 'confirmed':
            finish(db, job, 'completed', 'Изменение уже выполнено и подтверждено.')
        else:
            at = datetime.now(timezone.utc).isoformat()
            job.payload = {**job.payload, 'cancelled_by': actor, 'cancelled_at': at}
            if receipt:
                receipt.request_payload = {**receipt.request_payload, 'queue_cancelled_at': at}
            finish(db, job, 'cancelled', 'Отправка удалена.' if not receipt else
                   'Запрос уже отправлен в Webdev. Ожидание удалено; история запроса сохранена.')
        return snapshot(db, site, include=job)


def waiting(db, job, message):
    job.result = {'phase': 'waiting', 'message': message}
    job.dispatched_at = None
    db.commit()
    return {'status': 'waiting'}


def finish(db, job, status, message):
    job.status = status
    job.result = {'phase': status, 'message': message}
    job.error = message if status == 'failed' else None
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {'status': status}


def execute_step(db, job_id):
    job = db.get(models.BackgroundJob, str(job_id))
    if not job or job.kind != KIND or job.status in TERMINAL:
        return {'status': 'skipped'}
    try:
        with network.network_lock(db, job.payload['site_id']):
            db.refresh(job)
            if job.status in TERMINAL:
                return {'status': 'skipped'}
            pending = active(db, job.payload['site_id'])
            if not pending or pending[0].id != job.id:
                return waiting(db, job, 'Ожидает предыдущую задачу очереди.')
            site = db.get(models.Site, job.payload['site_id'])
            if not site or site.name != job.payload['project']:
                return finish(db, job, 'failed', 'Проект удалён или переименован. Создайте новую задачу.')
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.result = {'phase': 'processing', 'message': {'delete': 'Удаляем страницу…',
                'select': 'Назначаем страницу и обновляем разметку…', 'create': 'Создаём и назначаем страницу…'}[job.payload['action']]}
            db.commit()
            # Also resumes a saved head update, once, after create-and-activate.
            state = network.read_network(db, site)
            receipt = db.get(models.NetworkOperation, job.id)
            if not receipt:
                path = job.payload['path']
                if job.payload['action'] == 'delete' and not isinstance((state.get('fake_main_settings') or {}).get('fakeMain'), list):
                    return waiting(db, job, 'Webdev не вернул список фейковых страниц. Ожидаем полные данные.')
                if job.payload['action'] == 'delete' and path not in state.get('fake_main_paths', []):
                    return finish(db, job, 'completed', 'Страница отсутствует в Webdev; удаление подтверждено.')
                payload = network.NetworkChange(request_id=UUID(job.id), revision=state['revision'],
                    action='create_fake_main' if job.payload['action']=='create' else 'select_fake_main',
                    fake_main_path=path, delete_fake_main=job.payload['action']=='delete',
                    activate_fake_main=job.payload['action']=='create')
                network.change_network(db, site, payload, job.payload['actor'])
                receipt = db.get(models.NetworkOperation, job.id)
            if receipt and receipt.status == 'confirmed':
                return finish(db, job, 'completed', {'delete': 'Удалено.', 'create': 'Создано и назначено.',
                    'select': 'Назначено. Canonical и альтернейты обновлены.'}[job.payload['action']])
            if receipt and receipt.status == 'failed':
                return finish(db, job, 'failed', receipt.message or 'Webdev отклонил изменение.')
            return waiting(db, job, (receipt.message if receipt else None) or 'Ждём подтверждения Webdev; повторная запись не отправляется.')
    except network.NetworkConflict as error:
        return waiting(db, job, str(error))
    except (httpx.HTTPError, network.ProjectCacheError) as error:
        return waiting(db, job, 'Webdev пока недоступен. Очередь сохранена; проверка будет повторена.')
    except ValueError as error:
        return finish(db, job, 'failed', str(error))
