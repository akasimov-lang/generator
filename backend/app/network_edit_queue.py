"""Durable per-project FIFO for reserve and redirect edits; enqueue does no remote I/O."""
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import Field
from sqlalchemy import select

from app import models, project_network as network
from app.fake_main_queue import waiting, finish

KIND = 'network_edit_queue'
TERMINAL = ('completed', 'failed')
LIMIT = 30


class Request(network.NetworkChange):
    action: Literal['reserve', 'reglue', 'domain_redirect', 'domain_redirects_main', 'page_redirect']
    expected: dict = Field(default_factory=dict)


def query(site_id):
    return select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload['site_id'].as_string() == str(site_id))


def active(db, site_id):
    return list(db.scalars(query(site_id).where(models.BackgroundJob.status.not_in(TERMINAL))
        .order_by(models.BackgroundJob.payload['sequence'].as_integer(), models.BackgroundJob.id)))


def fingerprint(state, request):
    if request.action in {'reserve', 'reglue'}:
        return {'canon': state.get('canon', ''), 'reserve': state.get('reserve', '')}
    if request.action == 'domain_redirects_main':
        return {'canon': state.get('canon', ''), 'rows': state.get('domain_redirects', [])}
    if request.action == 'domain_redirect':
        source = request.redirect_original_source or request.redirect_source
        return {'rows': [r for r in state.get('domain_redirects', []) if r['url'] == source]}
    domain = request.page_redirect_original_domain or request.page_redirect_domain
    source = request.page_redirect_original_source or request.page_redirect_source
    return {'rows': [r for g in state.get('page_redirects', []) if g['domain'] == domain
                     for r in g['redirects'] if r['url'] == source]}


def item(job):
    return {'id': job.id, 'request': job.payload['request'],
        'status': job.status if job.status in TERMINAL else (job.result or {}).get('phase', 'queued'),
        'message': job.error or (job.result or {}).get('message', 'В очереди на сервере'),
        'created_at': job.created_at}


def snapshot(db, site):
    recent = list(db.scalars(query(site.id).where(models.BackgroundJob.status.in_(TERMINAL))
        .order_by(models.BackgroundJob.created_at.desc(), models.BackgroundJob.id.desc()).limit(30)))
    state = site.network_state or {}
    return {'items': [item(job) for job in [*active(db, site.id), *recent]], 'limit': LIMIT,
            'network': network.result(db, site, state) if state.get('has_head') and 'domains' in state else None}


def enqueue(db, site, request, actor):
    db.execute(select(models.Site.id).where(models.Site.id == site.id).with_for_update()).scalar_one()
    serialized = request.model_dump(mode='json')
    existing = db.get(models.BackgroundJob, str(request.request_id))
    if existing:
        if existing.kind != KIND or existing.payload['site_id'] != site.id or existing.payload['request'] != serialized:
            raise network.NetworkConflict('Идентификатор запроса уже используется другой задачей.')
        db.commit()
        return snapshot(db, site)
    if not request.expected:
        raise ValueError('Не передано исходное значение. Обновите данные перед сохранением.')
    if len(active(db, site.id)) >= LIMIT:
        raise network.NetworkConflict('В очереди уже 30 изменений. Дождитесь завершения одной задачи.')
    last = db.scalar(query(site.id).order_by(models.BackgroundJob.payload['sequence'].as_integer().desc()).limit(1))
    job = models.BackgroundJob(id=str(request.request_id), kind=KIND, status='queued',
        payload={'site_id': site.id, 'project': site.name, 'request': serialized, 'actor': actor,
                 'sequence': (last.payload.get('sequence', 0) if last else 0) + 1},
        result={'phase': 'queued', 'message': 'Отправлено на сервер. В очереди…'})
    db.add(job)
    db.commit()
    return snapshot(db, site)


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
                return waiting(db, job, 'В очереди. Ожидает предыдущее изменение…')
            site = db.get(models.Site, job.payload['site_id'])
            if not site or site.name != job.payload['project']:
                return finish(db, job, 'failed', 'Проект удалён или переименован.')
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.result = {'phase': 'processing', 'message': 'Отправлено на сервер. Сохраняем…'}
            db.commit()
            state = network.read_network(db, site)
            receipt = db.get(models.NetworkOperation, job.id)
            if not receipt:
                request = Request.model_validate(job.payload['request'])
                if fingerprint(state, request) != request.expected:
                    return finish(db, job, 'failed', 'Редактируемое значение изменилось. Проверьте данные перед повторным сохранением.')
                change = network.NetworkChange.model_validate({**request.model_dump(exclude={'expected'}), 'revision': state['revision']})
                network.change_network(db, site, change, job.payload['actor'])
                receipt = db.get(models.NetworkOperation, job.id)
            if receipt and receipt.status == 'confirmed':
                return finish(db, job, 'completed', 'Сохранено')
            if receipt and receipt.status == 'failed':
                return finish(db, job, 'failed', receipt.message or 'Не удалось сохранить изменение.')
            return waiting(db, job, 'Отправлено на сервер. Ожидаем подтверждения…')
    except network.NetworkConflict as error:
        return waiting(db, job, str(error))
    except (httpx.HTTPError, network.ProjectCacheError):
        return waiting(db, job, 'Сервер временно недоступен. Задание сохранено в очереди…')
    except ValueError as error:
        return finish(db, job, 'failed', str(error))
