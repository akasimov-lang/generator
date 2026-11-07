"""Page saves survive navigation; an uncertain Webdev write is only read back."""
from datetime import datetime, timezone
from copy import deepcopy

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models, project_pages as pages

KIND = 'project_page_save'
MAX_CHECKS = 7


def result(job):
    value = job.result or {}
    return {'id': job.id, 'status': value.get('status', 'pending') if job.status in {'completed', 'failed'} else 'pending',
            'error': job.error if job.status == 'failed' else value.get('error') if job.status == 'completed' else None,
            'page': value.get('page'), 'background': True, 'requested_by': job.payload['actor']}


def matching_job(db, site_id, key, request_id):
    job = db.get(models.BackgroundJob, str(request_id))
    if job and job.kind == KIND and job.payload.get('site_id') == site_id and job.payload.get('page_key') == key:
        return job
    return None


def enqueue(db, site, key, payload, actor):
    serialized = payload.model_dump(mode='json')
    fingerprint = pages.digest(serialized)
    db.execute(select(models.Site.id).where(models.Site.id == site.id).with_for_update()).scalar_one()
    existing = db.get(models.BackgroundJob, str(payload.request_id))
    if existing:
        if existing.kind != KIND or any(existing.payload.get(k) != v for k, v in {
                'site_id': site.id, 'page_key': key, 'actor': actor, 'fingerprint': fingerprint}.items()):
            raise HTTPException(409, 'Идентификатор сохранения уже использован для других изменений.')
        db.commit()
        return result(existing)
    operation = db.get(models.ProjectPageEdit, str(payload.request_id))
    if operation:
        if (operation.site_id != site.id or operation.page_key != key or operation.requested_by != actor
                or operation.fingerprint != fingerprint):
            raise HTTPException(409, 'Идентификатор сохранения уже использован для других изменений.')
        db.commit()
        return pages.operation_result(operation)
    job = models.BackgroundJob(id=str(payload.request_id), kind=KIND, status='queued',
        payload={'site_id': site.id, 'project': site.name, 'page_key': key, 'actor': actor,
                 'fingerprint': fingerprint, 'request': serialized}, result={'status': 'pending', 'checks': 0})
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # The same UUID can race across different projects; check all identity fields.
        return enqueue(db, site, key, payload, actor)
    return result(job)


def notice(db, job, outcome):
    from app.project_notifications import record
    from app.project_notifications_api import Notice
    site = db.get(models.Site, job.payload['site_id'])
    if not site:
        return
    failed = outcome['status'] in {'unknown', 'failed'}
    record(db, site, job.payload['actor'], Notice(key='page-save:' + job.id,
        code='PAGE_SAVE', severity='warning' if outcome['status'] == 'unknown' else 'error', active=failed,
        message=outcome.get('error') or 'Сохранение страницы подтверждено.',
        context='Сохранение страницы: ' + job.payload['request']['title'][:500]))


def resolved(db, operation):
    job = matching_job(db, operation.site_id, operation.page_key, operation.id)
    if job and operation.status == 'confirmed':
        outcome = pages.operation_result(operation)
        # JSON columns require JSON-compatible timestamps; the API adds no date here.
        outcome.pop('updated_at', None)
        job.result = {**(job.result or {}), **outcome}
        job.status, job.error, job.finished_at = 'completed', None, datetime.now(timezone.utc)
        db.commit()
        notice(db, job, outcome)


def finish(db, job, outcome):
    outcome = deepcopy(outcome)
    outcome.pop('updated_at', None)
    job.result = {**(job.result or {}), **outcome}
    job.status = 'failed' if outcome['status'] == 'failed' else 'completed'
    job.error = outcome.get('error')
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    notice(db, job, outcome)
    return result(job)


def waiting(db, job, message=None):
    job.result = {**(job.result or {}), 'status': 'pending', 'message': message or 'Сохраняем в фоне…'}
    db.commit()
    return result(job)


def execute(db, job_id):
    job = db.get(models.BackgroundJob, job_id)
    if not job or job.kind != KIND or job.status in {'completed', 'failed'}:
        return {'status': 'skipped'}
    try:
        with pages.network_lock(db, job.payload['site_id']):
            db.refresh(job)
            if job.status in {'completed', 'failed'}:
                return {'status': 'skipped'}
            site = pages.site_for(db, job.payload['site_id'])
            if site.name != job.payload['project']:
                raise HTTPException(409, 'Проект переименован. Обновите страницу перед сохранением.')
            # Stay queued until terminal: a worker restart is recovered by the
            # dispatcher. The network lock excludes duplicate deliveries.
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.result = {**(job.result or {}), 'checks': (job.result or {}).get('checks', 0) + 1}
            db.commit()
            operation = db.get(models.ProjectPageEdit, job.id)
            if operation:
                if operation.status in {'pending', 'unknown'}:
                    with pages.Remote(db, site) as remote:
                        outcome = pages.confirm(db, operation, remote, site)
                else:
                    outcome = pages.operation_result(operation)
            else:
                outcome = pages.save_page(site.id, job.payload['page_key'],
                    pages.PageEdit.model_validate(job.payload['request']), {'username': job.payload['actor']}, db)
            if outcome['status'] in {'confirmed', 'failed'}:
                return finish(db, job, outcome)
            notice(db, job, outcome)
            if job.result.get('checks', 0) >= MAX_CHECKS:
                return finish(db, job, outcome)
            return waiting(db, job, 'Изменения отправлены. Ожидаем подтверждения Webdev…')
    except pages.NetworkConflict:
        return waiting(db, job, 'Ожидаем завершения другой операции с проектом…')
    except (httpx.HTTPError, pages.ProjectCacheError):
        if (job.result or {}).get('checks', 0) < MAX_CHECKS:
            return waiting(db, job, 'Webdev временно недоступен. Сохранение продолжится автоматически…')
        receipt = db.get(models.ProjectPageEdit, job.id)
        return finish(db, job, {'status': 'unknown' if receipt else 'failed',
            'error': 'Не удалось подтвердить сохранение страницы. Черновик сохранён; проверьте результат в редакторе.'})
    except HTTPException as error:
        return finish(db, job, {'status': 'failed', 'error': str(error.detail)})
    except Exception:
        db.rollback()
        return finish(db, job, {'status': 'unknown' if db.get(models.ProjectPageEdit, job.id) else 'failed',
            'error': 'Не удалось завершить сохранение страницы. Черновик сохранён; проверьте результат в редакторе.'})
