"""Remove projects from future report work without erasing their saved history."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select
from app import models
from app.project_network import network_lock, NetworkConflict


def can_exclude(job):
    if job.kind == 'auto_pilot_preview':
        return job.status == 'completed'
    return job.kind == 'maintenance_report' and (job.payload.get('planning_only') or job.status in {'completed','partial','failed'}) and not job.payload.get('repeat')


def exclude(db, report_id, site_id, user, *, destination_report_id=None):
    from app import auto_pilot, maintenance_reports, mass_reglue_launch as launch
    with network_lock(db, 'mass-reglue-list-start'), network_lock(db, 'mass-reglue-list:' + str(report_id)):
        job = db.get(models.BackgroundJob, str(report_id))
        if job and job.kind == maintenance_reports.KIND:
            job = maintenance_reports.get(db, report_id, user)
        else:
            job = auto_pilot.get(db, report_id, user)
        if site_id in job.payload.get('excluded_site_ids', []):
            return job
        if site_id not in job.payload['site_ids']:
            raise ValueError('Проект не входит в этот отчёт.')
        if not can_exclude(job):
            raise NetworkConflict('Исключение доступно после расчёта плана или завершения работ. Выполняемое задание не изменяется.')
        if db.scalar(select(models.AutoReglueRun.id).where(models.AutoReglueRun.site_id == site_id, models.AutoReglueRun.status.in_(['planned','queued','running','waiting'])).limit(1)):
            raise NetworkConflict('У проекта выполняется переклей. Дождитесь его завершения.')
        payload = deepcopy(job.payload);result = deepcopy(job.result)
        original = payload.get('original_site_ids', payload['site_ids'])
        remaining = [sid for sid in payload['site_ids'] if sid != site_id]
        if job.kind == launch.PREVIEW_KIND:
            row = deepcopy(result.get('items', {}).get(site_id, {}))
        else:
            row = deepcopy(next(r for r in result['entries'] if r['site_id'] == site_id))
        record = {'site_id':site_id,'project':row.get('project') or db.get(models.Site,site_id).name,
                  'excluded_at':datetime.now(timezone.utc).isoformat(),'actor':user['username'],
                  'destination_report_id':destination_report_id,'entry':row}
        payload.update(original_site_ids=original, site_ids=remaining,
                       excluded_site_ids=[*payload.get('excluded_site_ids', []),site_id],
                       excluded_projects=[*payload.get('excluded_projects', []),record])
        if job.kind == launch.PREVIEW_KIND:
            # Reallocate all quotas and donor dependencies; no stale plan may launch.
            record['previous_result'] = result
            fresh = launch.initial_job(db, job.id, remaining, payload['actor'], payload.get('allowed'), preview_only=True)
            job.result = fresh.result
            job.status = fresh.status
            job.started_at = job.finished_at = job.dispatched_at = None
            payload['config_hash'] = fresh.payload['config_hash']
            payload['planner_version'] = fresh.payload['planner_version']
        else:
            result['entries'] = [r for r in result['entries'] if r['site_id'] != site_id]
            # A removed donor cannot remain an implicit participant in a plan.
            for entry in result['entries']:
                plan = entry.get('plan') or {}
                if job.payload.get('planning_only') and plan.get('source_site_id') == site_id:
                    entry.update(planning_status='blocked', pending_reason='Источник домена исключён. Требуется пересчитать план.',status='waiting')
            job.result = result
            if payload.get('planning_summary'):
                payload['planning_summary'] = {**payload['planning_summary'], 'total':len(remaining),
                    'ready':sum(r.get('planning_status')=='ready' for r in result['entries']),
                    'conditional':sum(r.get('planning_status')=='conditional' for r in result['entries']),
                    'excluded':len(payload['excluded_site_ids'])}
        job.payload = payload
        db.commit()
        return job
