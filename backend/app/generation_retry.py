"""Bounded automatic recovery, with a durable outbox and no published-page replay."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5
from app import models

MAX_ATTEMPTS = 3


def schedule(db, item, *, explicit=False):
    task = db.get(models.GenerationTask, item.task_id)
    site_id = item.site_id or (task.site_id if task else None)
    site = db.get(models.Site, site_id) if site_id else None
    if (not task or task.archived_at or not site or not site.is_active
            or item.status != 'generation_failed' or item.published_at):
        return False
    error = item.generation_error or ''
    if not explicit and any(token in error.lower() for token in (
        '401 unauthorized', '403 forbidden', 'api key', 'api_key', 'credentials',
        'not configured', 'не настроен', 'slug', 'уже существует', 'permission')):
        return False
    recovery = dict((item.generation_context or {}).get('automatic_generation_retry') or {})
    if recovery.get('attempts', 0) >= MAX_ATTEMPTS - 1 and not explicit: return False
    if explicit:
        recovery = {**recovery, 'attempts': 0, 'cycle': recovery.get('cycle', 0) + 1}
    attempt = recovery.get('attempts', 0) + 1
    job_id = str(uuid5(UUID(item.id), f"generation-retry:{recovery.get('cycle', 0)}:{attempt}"))
    if db.get(models.BackgroundJob, job_id): return False
    now = datetime.now(timezone.utc)
    item.generation_context = {**(item.generation_context or {}), 'automatic_generation_retry': {
        **recovery, 'attempts': attempt, 'previous_error': error, 'queued_at': now.isoformat(), 'job_id': job_id}}
    item.status = 'generation_queued'
    item.generation_error = f'Повторяем генерацию автоматически. Попытка {attempt + 1} из {MAX_ATTEMPTS}.'
    task.status = 'generating'
    db.add(models.BackgroundJob(id=job_id, kind='generation_retry', status='queued',
        payload={'content_id': item.id, 'collect_competitors': task.collect_competitors,
                 'not_before': (now + timedelta(seconds=10)).isoformat()}))
    db.commit()
    return True


def due(job):
    value = job.payload.get('not_before')
    return not value or datetime.fromisoformat(value) <= datetime.now(timezone.utc)
