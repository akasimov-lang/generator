"""Live text progress for the explicitly recorded tasks of a maintenance report."""
from sqlalchemy import select, tuple_
from app import models

READY = {'generated', 'approved', 'scheduled', 'retry_scheduled', 'publication_paused',
         'publishing', 'publication_pending_confirmation', 'published'}


def for_entries(db, entries):
    pairs = {(row.get('site_id'), task_id) for row in entries
             for task_id in (row.get('generation_task_ids') or [])
             if isinstance(task_id, str) and row.get('site_id')}
    if db is None or not pairs:
        return {}
    item, task = models.ContentItem, models.GenerationTask
    rows = db.execute(select(item.id, item.site_id, item.task_id, item.topic, item.slug,
        item.status, item.generation_progress, item.competitor_research_progress,
        item.competitor_research_status, item.updated_at)
        .join(task, task.id == item.task_id)
        .where(tuple_(item.site_id, item.task_id).in_(pairs), task.site_id == item.site_id)
        .order_by(item.created_at, item.id)).mappings()
    result = {}
    for row in rows:
        ready = row['status'] in READY
        result.setdefault(row['site_id'], []).append({
            'id': row['id'], 'task_id': row['task_id'], 'topic': row['topic'],
            'slug': row['slug'], 'status': row['status'], 'ready': ready,
            'percent': 100 if ready else max(0, min(99, row['generation_progress'] or 0)),
            'research_percent': max(0, min(100, row['competitor_research_progress'] or 0)),
            'research_status': row['competitor_research_status'],
            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
        })
    return result
