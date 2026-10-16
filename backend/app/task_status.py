"""One task status derived from the current content rows, including unflushed changes."""
from sqlalchemy import select
from app import models


def refresh_task_status(db, task_id):
    db.flush()
    task = db.get(models.GenerationTask, task_id, with_for_update=True)
    if not task:
        return
    statuses = set(db.scalars(select(models.ContentItem.status).where(models.ContentItem.task_id == task_id)))
    active = statuses - {'deleted'}
    if not active:
        task.status = 'empty'
    elif active & {'generation_queued', 'generating'}:
        task.status = 'generating'
    elif active & {'publishing', 'publication_pending_confirmation'}:
        task.status = 'publishing'
    elif active == {'published'}:
        task.status = 'published'
    elif 'generation_failed' in active:
        task.status = 'generation_failed'
    elif 'publication_failed' in active:
        task.status = 'publication_failed'
    elif 'system_stopped' in active:
        task.status = 'system_stopped'
    elif active & {'scheduled', 'retry_scheduled', 'publication_paused'}:
        task.status = 'scheduled'
    elif task.auto_publish and 'approved' in active:
        task.status = 'publishing'
    elif active == {'draft'}:
        task.status = 'created'
    else:
        task.status = 'generated'
    return task.status
