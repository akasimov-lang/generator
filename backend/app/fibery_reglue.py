"""One durable Fibery task per confirmed reglue, dispatched after its +3m boundary."""
import re
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from app import models
from app.core.config import get_settings
from app.fibery_client import FiberyClient, FiberyConflict, FiberyError
from app.fibery_reglue_evidence import WINDOW, build, stamp
from app.network_state import domain_name
from app.reglue_history import utc
from app.reglue_journal import confirmed_at

KIND = 'fibery_reglue'
START_KEY = 'fibery-reglue:enabled-at'


def identity(operation_id):
    return str(uuid5(NAMESPACE_URL, 'https://ai-seo-content-panel.site/fibery-reglue/' + operation_id))


def ensure_job(db, operation):
    payload = operation.request_payload or {}
    source, target = domain_name(payload.get('source_domain')), domain_name(payload.get('reserve'))
    if operation.action != 'reglue' or operation.status != 'confirmed' or not source or not target or source == target:
        return None
    id_ = identity(operation.id)
    existing = db.get(models.BackgroundJob, id_)
    if existing:
        return existing
    at = confirmed_at(operation)
    site = db.get(models.Site, operation.site_id)
    match = re.search(r'#\s*(\d+)', site.fibery_name or '') if site else None
    row = models.BackgroundJob(id=id_, kind=KIND, status='queued', payload={
        'site_id': operation.site_id, 'operation_id': operation.id, 'task_id': id_,
        'project_number': match.group(1) if match else None,
        'title': f'Переклей: {source} → {target}',
        'confirmed_at': at.isoformat(), 'due_at': (at + WINDOW).isoformat(),
        'window_start': (at - WINDOW).isoformat(), 'window_end': (at + WINDOW).isoformat(),
    })
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.get(models.BackgroundJob, id_)
        if existing:
            return existing
        raise
    return row


def schedule_confirmed(db, operation):
    if get_settings().fibery_api_token.get_secret_value():
        return ensure_job(db, operation)
    return None


def due(job, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    deadline = utc((job.payload or {}).get('due_at'))
    retry_at = utc((job.result or {}).get('next_attempt_at'))
    return bool(deadline and now >= deadline and (retry_at is None or now >= retry_at))


def tick(db, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    if not get_settings().fibery_api_token.get_secret_value():
        return {'status': 'not_configured'}
    config = db.get(models.AutoReglueConfig, START_KEY)
    if not config:
        try:
            with db.begin_nested():
                db.add(models.AutoReglueConfig(key=START_KEY, value={'enabled_at': now.isoformat()}))
                db.flush()
        except IntegrityError:
            pass
        db.commit()
    config = db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key == START_KEY).with_for_update())
    start = utc(config.value['enabled_at'])
    created = 0
    operations = db.scalars(select(models.NetworkOperation).outerjoin(models.BackgroundJob, and_(
        models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload['operation_id'].as_string() == models.NetworkOperation.id)).where(
        models.BackgroundJob.id.is_(None), models.NetworkOperation.action == 'reglue',
        models.NetworkOperation.status == 'confirmed', models.NetworkOperation.updated_at >= start)).all()
    for operation in operations:
        if confirmed_at(operation) < start:
            continue
        existed = db.get(models.BackgroundJob, identity(operation.id)) is not None
        row = ensure_job(db, operation)
        created += int(row is not None and not existed)
    recovered = 0
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
            models.BackgroundJob.status == 'running', models.BackgroundJob.started_at < now - timedelta(minutes=15))):
        job.status, job.dispatched_at = 'queued', None
        job.error = 'Обработка прервалась. Проверяем существующую задачу Fibery перед продолжением.'
        recovered += 1
    db.commit()
    return {'created': created, 'recovered': recovered}


def execute(db, job_id, *, client=None, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == job_id).with_for_update())
    if not job or job.kind != KIND or job.status != 'queued' or not due(job, now):
        db.rollback()
        return {'status': 'waiting_or_claimed'}
    operation = db.get(models.NetworkOperation, job.payload['operation_id'])
    site = db.get(models.Site, job.payload['site_id'])
    if not site or not operation or operation.status != 'confirmed':
        job.status, job.error, job.finished_at = 'failed', 'Подтверждённый переклей или проект недоступен.', now
        db.commit()
        return {'status': 'failed'}
    previous = dict(job.result or {})
    job.status, job.started_at = 'running', now
    job.result = {**previous, 'attempts': int(previous.get('attempts', 0)) + 1}
    db.commit()
    owned_client = client is None
    try:
        evidence = (job.result or {}).get('evidence')
        if evidence is None:
            evidence = build(db, site, operation)
            job.result = {**job.result, 'evidence': evidence}
            db.commit()
        number = job.payload.get('project_number')
        if not number:
            match = re.search(r'#\s*(\d+)', site.fibery_name or '')
            if not match:
                raise FiberyError('У проекта не указан номер Fibery. Задача будет создана после восстановления привязки.')
            number = match.group(1)
            job.payload = {**job.payload, 'project_number': number}
            db.commit()
        if client is None:
            client = FiberyClient(get_settings().fibery_api_token.get_secret_value())
        result = client.ensure_task(task_id=job.payload['task_id'], project_number=number,
                                   title=job.payload['title'], description=evidence['description'])
        job.result = {**job.result, 'task': result, 'next_attempt_at': None, 'verified_at': now.isoformat()}
        job.status, job.error, job.finished_at = 'completed', None, datetime.now(timezone.utc)
        db.commit()
        return {'status': 'completed', 'url': result['url']}
    except Exception as error:
        db.rollback()
        job = db.get(models.BackgroundJob, job_id)
        conflict = isinstance(error, FiberyConflict)
        job.error = str(error) if isinstance(error, FiberyError) else 'Не удалось подготовить или подтвердить SEO-задачу. Повтор начнётся с проверки существующей задачи.'
        delay = min(1800, 60 * 2 ** min(int((job.result or {}).get('attempts', 1)) - 1, 5))
        job.status, job.dispatched_at = ('failed' if conflict else 'queued'), None
        job.result = {**(job.result or {}), 'next_attempt_at': (now + timedelta(seconds=delay)).isoformat()}
        if conflict:
            job.finished_at = now
        db.commit()
        return {'status': job.status, 'message': job.error}
    finally:
        if owned_client and client is not None:
            client.close()


def notice(job):
    result, payload = job.result or {}, job.payload or {}
    task = result.get('task') or {}
    done = job.status == 'completed'
    title = payload.get('title') or 'SEO-задача переклея'
    message = ('Создана SEO-задача Fibery #' + str(task.get('public_id', '')) + ': ' + title if done else
               'SEO-задача Fibery: ' + title)
    context = (f'Работы: {stamp(payload["window_start"])} — {stamp(payload["window_end"])}.\n'
               f'Создание задачи не ранее {stamp(payload["due_at"])}.')
    if job.error:
        context += '\n' + job.error
    elif not done:
        context += '\nСобираем работы и подтверждённые изменения по проекту.'
    if result.get('evidence'):
        context += '\n\n' + result['evidence']['description']
    return {'id': 'fibery:' + job.id, 'source': 'fibery', 'code': 'FIBERY_REGLUE',
            'status': 'completed' if done else 'failed' if job.error else 'running' if job.status == 'running' else 'collecting',
            'message': message, 'context': context, 'severity': 'warning' if job.error else 'info',
            'active': True, 'created_at': job.finished_at or job.created_at, 'occurrences': 1,
            'task_url': task.get('url'), 'task_title': task.get('title')}
