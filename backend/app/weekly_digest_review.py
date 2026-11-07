"""Logical unfinished work in saved plans, without counting child retries twice.

This is a read-only snapshot for the weekly digest. Draft plans, arbitrary old
content drafts and individual network receipts are not extra tasks: a launched
run/branch owns those records. Callers filter returned site IDs for access.
"""
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import or_, select

from app import models
from app.reglue_history import utc

PILOT_KINDS = ('pilot_text', 'pilot_content_publication', 'pilot_internal_pages')
DONE = {'completed', 'confirmed', 'cancelled', 'canceled', 'skipped', 'deleted'}
PLAN_KINDS = {'mass_reglue_list', 'auto_pilot_preview'}


def _time(value):
    return utc(value) or datetime.min.replace(tzinfo=timezone.utc)


def _latest(records):
    # Completion time, then creation time, gives a successful retry precedence
    # over an older failure. IDs only make genuinely equal timestamps stable.
    return max(records, key=lambda r: (_time(r.updated_at), _time(r.created_at), r.id))


def unresolved(db, start, end):
    """Return unique ``{key, site_id, kind}`` work refs for ``start <= at < end``.

    Generation and publication of a homepage field form one task. Distinct
    fields, the network switch and the internal-pages branch remain independent.
    The latest current attempt decides whether each task still needs attention.
    """
    start, end = utc(start), utc(end)
    if start is None or end is None or start >= end:
        raise ValueError('Invalid weekly report interval')

    runs = list(db.scalars(select(models.AutoReglueRun).where(
        models.AutoReglueRun.updated_at >= start,
        models.AutoReglueRun.updated_at < end,
    )))
    jobs = list(db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.kind.in_(PILOT_KINDS),
        models.BackgroundJob.updated_at >= start,
        models.BackgroundJob.updated_at < end,
    )))
    parent_ids = {str(r.plan['list_launch_id']) for r in runs if (r.plan or {}).get('list_launch_id')}
    parent_ids.update(str(j.payload.get('parent_id') or j.payload.get('parent_job_id'))
                      for j in jobs if (j.payload or {}).get('parent_id') or (j.payload or {}).get('parent_job_id'))
    if not parent_ids:
        return []
    parents = {p.id: p for p in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.id.in_(parent_ids)))}
    deleted = {m.key.removeprefix('pilot-cancel:') for m in db.scalars(
        select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.in_(['pilot-cancel:' + p for p in parent_ids])))
        if (m.value or {}).get('deleted')}

    def parent_for(parent_id, site_id):
        parent = parents.get(parent_id)
        if (not parent or parent.kind not in PLAN_KINDS or parent.status in {'cancelled', 'canceled', 'deleted'}
                or parent_id in deleted or not site_id):
            return None
        item = ((parent.result or {}).get('items') or {}).get(site_id) or {}
        if item.get('status') in {'cancelled', 'canceled', 'skipped', 'deleted'}:
            return None
        return parent

    grouped_runs = defaultdict(list)
    for run in runs:
        parent_id = str((run.plan or {}).get('list_launch_id') or '')
        parent = parent_for(parent_id, run.site_id)
        if not parent:
            continue
        current_id = (((parent.result or {}).get('items') or {}).get(run.site_id) or {}).get('run_id')
        if current_id and current_id != run.id:
            continue
        grouped_runs[(parent_id, run.site_id)].append(run)

    result = []
    for (parent_id, site_id), attempts in grouped_runs.items():
        if _latest(attempts).status not in DONE:
            current = _latest(attempts)
            result.append({'key': f'plan:{parent_id}:{site_id}:reglue', 'site_id': site_id, 'kind': 'reglue',
                           'parent_id': parent_id, 'status': current.status, 'reason': current.message,
                           'updated_at': _time(current.updated_at).isoformat()})

    grouped_jobs = defaultdict(list)
    internal_jobs = []
    for job in jobs:
        p = job.payload or {}
        parent_id, site_id = str(p.get('parent_id') or p.get('parent_job_id') or ''), p.get('site_id')
        parent = parent_for(parent_id, site_id)
        if not parent:
            continue
        generation = (parent.payload or {}).get('generation_id')
        if generation and p.get('generation_id') and p['generation_id'] != generation:
            continue
        # Publication from a replaced/cancelled run must not resurrect its error.
        current_run = (((parent.result or {}).get('items') or {}).get(site_id) or {}).get('run_id')
        if p.get('run_id') and current_run and p['run_id'] != current_run:
            continue
        kind = 'internal_pages' if job.kind == 'pilot_internal_pages' else 'text'
        field = str(p.get('field') or 'content') if kind == 'text' else ''
        grouped_jobs[(parent_id, site_id, kind, field)].append(job)
        if kind == 'internal_pages':
            internal_jobs.append(job)

    # ContentItem is the source of truth for completed page branches. A worker
    # may have published the last page before updating the branch's old partial.
    task_ids = {str((j.result or {})['task_id']) for j in internal_jobs if (j.result or {}).get('task_id')}
    task_names = ['Auto Pilot inner pages: ' + j.id for j in internal_jobs]
    tasks = list(db.scalars(select(models.GenerationTask).where(or_(
        models.GenerationTask.id.in_(task_ids),
        models.GenerationTask.prompt_template_name.in_(task_names),
    )))) if internal_jobs else []
    tasks_by_id = {t.id: t for t in tasks}
    tasks_by_name = {t.prompt_template_name: t for t in tasks}
    items_by_task = defaultdict(list)
    if tasks:
        for item in db.scalars(select(models.ContentItem).where(models.ContentItem.task_id.in_(tasks_by_id))):
            items_by_task[item.task_id].append(item)

    for (parent_id, site_id, kind, field), attempts in grouped_jobs.items():
        job = _latest(attempts)
        if job.status in DONE:
            continue
        if kind == 'internal_pages':
            task = tasks_by_id.get(str((job.result or {}).get('task_id') or '')) or tasks_by_name.get('Auto Pilot inner pages: ' + job.id)
            if task and task.site_id == site_id:
                if task.archived_at and _time(task.archived_at) < end:
                    continue
                items = items_by_task[task.id]
                if items and all(i.status == 'published' and i.published_at and _time(i.published_at) < end for i in items):
                    continue
        suffix = kind + (':' + field if field else '')
        result.append({'key': f'plan:{parent_id}:{site_id}:{suffix}', 'site_id': site_id, 'kind': kind,
                       'parent_id': parent_id, 'field': field, 'status': job.status, 'reason': job.error,
                       'updated_at': _time(job.updated_at).isoformat()})
    sites = {s.id: s for s in db.scalars(select(models.Site).where(models.Site.id.in_({r['site_id'] for r in result})))} if result else {}
    for ref in result:
        site = sites.get(ref['site_id'])
        ref['project'] = site.name if site else ref['site_id']
        parent = parents.get(ref['parent_id'])
        ref['report_url'] = '/auto-reglue/pilot' + ('/logs' if parent and parent.kind == 'mass_reglue_list' else '') + '?id=' + ref['parent_id']
    return sorted(result, key=lambda r: r['key'])
