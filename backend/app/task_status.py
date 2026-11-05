"""One task status derived from the current content rows, including unflushed changes."""
from sqlalchemy import select
from app import models


def refresh_task_status(db, task_id):
    db.flush()
    task = db.get(models.GenerationTask, task_id, with_for_update=True)
    if not task:
        return
    statuses = set(db.scalars(select(models.ContentItem.status).where(models.ContentItem.task_id == task_id)))
    task.status = derive_status(statuses, task.auto_publish)
    return task.status


def derive_status(statuses, auto_publish=False):
    active = statuses - {'deleted'}
    if not active:
        return 'empty'
    elif active & {'generation_queued', 'generating'}:
        return 'generating'
    elif active & {'publishing', 'publication_pending_confirmation'}:
        return 'publishing'
    elif active == {'published'}:
        return 'published'
    elif 'generation_failed' in active:
        return 'generation_failed'
    elif 'publication_failed' in active:
        return 'publication_failed'
    elif 'system_stopped' in active:
        return 'system_stopped'
    elif active & {'scheduled', 'retry_scheduled', 'publication_paused'}:
        return 'scheduled'
    elif auto_publish and 'approved' in active:
        return 'publishing'
    elif active <= {'approved', 'published'}:
        return 'approved'
    elif active == {'draft'}:
        return 'created'
    else:
        return 'generated'


def task_error_summary(items):
    failures = [item for item in items if item.status in {'generation_failed', 'publication_failed', 'system_stopped'}]
    messages = []
    for item in failures:
        message = item.generation_error or item.competitor_research_error
        if not message:
            code = item.last_publication_status_code
            message = f'Публикация: HTTP {code}' if code and code >= 400 else 'Причина не сохранена. Откройте историю текста.'
        text = ' '.join(str(message).split())
        messages.append(f'{item.slug}: {text}')
    return ' · '.join(dict.fromkeys(messages))[:1500] or None
