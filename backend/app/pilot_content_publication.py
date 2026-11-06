"""Publish reviewed homepage fields independently of a manually launched reglue."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid5
from sqlalchemy import select
from app import models
from app.project_network import network_lock, NetworkConflict

KIND = 'pilot_content_publication'
FIELDS = ('title_h1', 'paragraphs')


def enabled(parent):
    return bool(parent and parent.kind == 'mass_reglue_list' and parent.payload.get('manual_start') and parent.payload.get('streaming_start'))


def attach(db, run):
    parent = db.get(models.BackgroundJob, run.plan.get('list_launch_id')) if run.plan.get('list_launch_id') else None
    if not enabled(parent) or run.status == 'cancelled' or run.plan.get('content_prepared_at'):
        return False
    for field in FIELDS:
        if not run.plan.get('rewrite_' + field): continue
        id = str(uuid5(UUID(run.id), 'publish-content:' + field))
        if not db.get(models.BackgroundJob, id):
            db.add(models.BackgroundJob(id=id, kind=KIND, status='queued', payload={
                'parent_id': parent.id, 'run_id': run.id, 'site_id': run.site_id, 'field': field},
                result={'phase': 'waiting_generation'}))
    db.flush()
    return True


def states(db, parent_id, site_id=None):
    query = select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload['parent_id'].as_string() == parent_id)
    if site_id: query = query.where(models.BackgroundJob.payload['site_id'].as_string() == site_id)
    return list(db.scalars(query))


def merge_metadata(db, parent, metadata):
    if not enabled(parent): return metadata
    jobs = states(db, parent.id)
    if not jobs: return metadata
    metadata = dict(metadata)
    if any(job.status == 'queued' for job in jobs):
        metadata.update(status='running', finished_at=None)
    elif metadata['status'] == 'completed' and any(job.status != 'completed' for job in jobs):
        metadata['status'] = 'partial'
    from app.reglue_history import utc
    if metadata.get('finished_at'):
        metadata['finished_at'] = max(utc(t) for t in [metadata['finished_at'], *(job.finished_at for job in jobs)] if t)
    metadata['updated_at'] = max(utc(t) for t in [metadata['updated_at'], *(job.updated_at for job in jobs)] if t)
    return metadata


def merge_row(db, parent, row):
    jobs = states(db, parent.id, row['site_id'])
    if not jobs: return
    row['content_jobs'] = [{'field': job.payload['field'], 'status': job.status,
                           'phase': (job.result or {}).get('phase'), 'error': job.error,
                           'finished_at': job.finished_at} for job in jobs]
    pending = any(job.status == 'queued' for job in jobs)
    failed = any(job.status == 'failed' for job in jobs)
    if (row['status'] == 'completed' or row.get('reglue_status') == 'completed') and (pending or failed):
        row['reglue_status'] = 'completed'
        row.update(status='running' if pending else 'partial',
                   phase='content_generation' if pending else 'content_failed',
                   progress=95 if pending else 100,
                   reason='Переклей выполнен. Тексты публикуются по готовности.' if pending else 'Переклей выполнен. Есть ошибка обновления текста.')


def execute(db, job_id):
    row = db.get(models.BackgroundJob, job_id)
    if not row or row.status != 'queued': return {'status': 'skipped'}
    try:
        with network_lock(db, 'auto-run:' + row.payload['run_id']), network_lock(db, row.payload['site_id']):
            db.refresh(row)
            if row.status != 'queued': return {'status': 'skipped'}
            parent = db.get(models.BackgroundJob, row.payload['parent_id'])
            run = db.get(models.AutoReglueRun, row.payload['run_id'])
            if not enabled(parent) or parent.status == 'cancelled' or not run or run.status == 'cancelled':
                row.status = 'cancelled'; row.finished_at = datetime.now(timezone.utc); db.commit()
                return {'status': row.status}
            plan = next((p for g in parent.result['groups'] for p in g.get('plans', []) if p['site_id'] == run.site_id), None)
            from app.mass_action_scope import require_run_scope
            require_run_scope(db, run)
            if not plan or plan.get('new_main') != run.plan.get('new_main'):
                raise ValueError('План проекта изменился. Публикация старой версии остановлена.')
            field = row.payload['field']
            if plan.get(field + '_error'): raise ValueError(plan[field + '_error'])
            from app.auto_pilot import heading_mode_ready, paragraphs_ready
            ready = (heading_mode_ready(db, plan, plan.get('title_rewrite_mode', 'minimal'))
                     if field == 'title_h1' else paragraphs_ready(db, plan))
            if not ready:
                row.result = {**(row.result or {}), 'phase': 'waiting_generation'}; db.commit()
                return {'status': 'waiting_generation'}
            # Headings and paragraphs share a document. Save headings first when both
            # are selected, then merge paragraphs into the fresh document.
            if field == 'paragraphs' and plan.get('rewrite_title_h1'):
                heading_job = db.get(models.BackgroundJob, str(uuid5(UUID(run.id), 'publish-content:title_h1')))
                if heading_job and heading_job.status == 'queued':
                    row.result = {**(row.result or {}), 'phase': 'waiting_headings'}; db.commit()
                    return {'status': 'waiting_headings'}
            from app.project_network import read_network
            site = db.get(models.Site, run.site_id)
            state = read_network(db, site)
            if state['canon'] not in {run.plan.get('old_main'), run.plan.get('new_main')}:
                raise ValueError('Main изменился вне этого запуска. Публикация контента остановлена.')
            if state['canon'] == run.plan.get('new_main'):
                prefix = 'cross:' if run.plan.get('execution_mode') == 'cross_network' else ''
                receipt = db.get(models.NetworkOperation, str(uuid5(UUID(run.id), prefix + 'reglue')))
                if not receipt or receipt.status != 'confirmed':
                    raise ValueError('Нет подтверждения переклея этого запуска.')
            row.started_at = row.started_at or datetime.now(timezone.utc)
            row.result = {**(row.result or {}), 'phase': 'publishing'}; db.commit()
            # The existing writer persists backup/save receipts. Its temporary status
            # belongs to this content job and must not overwrite the network outcome.
            work = SimpleNamespace(id=run.id, site_id=run.site_id, initiator=run.initiator,
                status=run.status, phase=run.phase, message=run.message,
                plan={**deepcopy(run.plan), field + '_preview': deepcopy(plan[field + '_preview'])})
            if field == 'title_h1':
                from app.reglue_title_h1 import finish
            else:
                from app.reglue_paragraphs import finish
            confirmed = finish(db, work, before_network=state['canon'] == run.plan.get('old_main'))
            db.refresh(run)
            run.plan = {**run.plan, **{key: value for key, value in work.plan.items()
                       if key.startswith(field + '_') or key == 'backup_note'}}
            row.status = 'completed' if confirmed else 'queued' if work.status == 'waiting' else 'failed'
            row.error = None if confirmed else work.message
            row.result = {**row.result, 'phase': 'confirmed' if confirmed else 'confirmation' if row.status == 'queued' else 'failed'}
            if row.status != 'queued': row.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {'status': row.status}
    except NetworkConflict:
        db.rollback(); return {'status': 'busy'}
    except Exception as error:
        db.rollback(); row = db.get(models.BackgroundJob, job_id)
        row.status = 'failed'; row.error = str(getattr(error, 'detail', error))[:1500]
        row.finished_at = datetime.now(timezone.utc); db.commit()
        return {'status': 'failed'}
