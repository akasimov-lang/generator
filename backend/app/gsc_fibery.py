"""Durable, idempotent Fibery receipts for explicitly saved GSC values."""
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.fibery_client import FiberyClient, FiberyConflict, FiberyError
from app.fibery_tasks import project_number
from app.network_state import domain_name
from app.reglue_history import utc

KIND = 'gsc_fibery'


def enqueue(db, site, value, actor):
    """Called under the site's row lock, committed together with the GSC field."""
    domain = domain_name(site.cache_canon) or domain_name(site.name)
    identity = json.dumps([site.id, domain, value], ensure_ascii=False)
    task_id = str(uuid5(NAMESPACE_URL, 'pagepilot:gsc:' + identity))
    existing = db.get(models.BackgroundJob, task_id)
    if existing:
        return existing
    # Literal fenced text preserves HTML, Markdown, and the complete entered value.
    fence = '`' * max(3, 1 + max((len(x) for x in re.findall(r'`+', value)), default=0))
    description = f'- Домен: {domain}\n- Значение поля GSC в PagePilot:\n\n{fence}text\n{value}\n{fence}'
    job = models.BackgroundJob(id=task_id, kind=KIND, status='queued', payload={
        'site_id': site.id, 'actor': actor, 'domain': domain, 'value': value,
        'project_number': project_number(site.fibery_name), 'task_id': task_id,
        'title': f'{domain} - Добавлен в GSC', 'description': description,
        'due_at': datetime.now(timezone.utc).isoformat(),
    })
    db.add(job)
    return job


def due(job, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    retry_at = utc((job.result or {}).get('next_attempt_at'))
    return not retry_at or now >= retry_at


def recover(db, inflight_ids, now):
    # Only reclaim a lost worker when a broker snapshot confirms it is absent.
    if inflight_ids is None:
        return
    jobs = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.kind == KIND, models.BackgroundJob.status == 'running',
        models.BackgroundJob.started_at < now - timedelta(minutes=15),
        models.BackgroundJob.id.not_in(inflight_ids),
    ).with_for_update(skip_locked=True))
    for job in jobs:
        job.status, job.dispatched_at = 'queued', None
        job.error = 'Обработка прервалась. Проверяем существующую задачу Fibery.'


def execute(db, job_id, *, client=None, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == job_id)
                    .with_for_update().execution_options(populate_existing=True))
    if not job or job.kind != KIND or job.status != 'queued' or not due(job, now):
        db.rollback()
        return {'status': 'waiting_or_claimed'}
    job.status, job.started_at = 'running', now
    job.result = {**(job.result or {}), 'attempts': int((job.result or {}).get('attempts', 0)) + 1}
    db.commit()
    owned = client is None
    try:
        site = db.get(models.Site, job.payload['site_id'])
        if not site:
            raise FiberyConflict('Проект удалён. Создание SEO-задачи остановлено.')
        number = job.payload.get('project_number') or project_number(site.fibery_name)
        if not number:
            raise FiberyError('У проекта не указан номер Fibery. Ожидаем восстановления привязки.')
        if not job.payload.get('project_number'):
            job.payload = {**job.payload, 'project_number': number}
            db.commit()
        if client is None:
            client = FiberyClient(get_settings().fibery_api_token.get_secret_value())
        receipt = client.ensure_task(task_id=job.payload['task_id'], project_number=number,
            title=job.payload['title'], description=job.payload['description'])
        job.result = {**job.result, 'task': receipt, 'verified_at': now.isoformat(), 'next_attempt_at': None}
        job.status, job.error, job.finished_at = 'completed', None, datetime.now(timezone.utc)
        db.commit()
        return {'status': 'completed', 'url': receipt['url']}
    except Exception as error:
        db.rollback()
        job = db.get(models.BackgroundJob, job_id)
        conflict = isinstance(error, FiberyConflict)
        job.error = str(error) if isinstance(error, FiberyError) else 'Не удалось подтвердить SEO-задачу. Повтор начнётся с проверки существующей задачи Fibery.'
        delay = min(1800, 60 * 2 ** min(int((job.result or {}).get('attempts', 1)) - 1, 5))
        job.status, job.dispatched_at = ('failed' if conflict else 'queued'), None
        job.result = {**(job.result or {}), 'next_attempt_at': (now + timedelta(seconds=delay)).isoformat()}
        if conflict:
            job.finished_at = now
        db.commit()
        return {'status': job.status}
    finally:
        if owned and client is not None:
            client.close()
