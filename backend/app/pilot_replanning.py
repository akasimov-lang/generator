"""Durable regeneration of one preview job, including while its worker is busy."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select
from app import models, auto_reglue as auto, mass_reglue_launch as launch
from app.project_network import NetworkConflict, network_lock


def key(job_id):
    return 'pilot-replan:' + str(job_id)


def pending(db, job_id):
    # Read the JSON column directly: a long-running planner may cache the ORM row.
    value = db.scalar(select(models.AutoReglueConfig.value).where(models.AutoReglueConfig.key == key(job_id)))
    return value if value and value.get('state') == 'pending' else None


def apply_pending(db, job):
    """Caller owns the job lock; no remote work and no additional job row."""
    command = pending(db, job.id)
    if not command or job.kind != launch.PREVIEW_KIND:
        return False
    from app.auto_pilot import deleted, draft_name
    if deleted(db, job.id):
        return False
    from app.pilot_versions import ensure_current
    old = deepcopy(job.result)
    if command.get('previous_completed'):
        ensure_current(job, old)
    job.payload = deepcopy(command['payload'])
    job.payload['generation_id'] = command['request_id']
    job.result = {**deepcopy(command['result']), 'row_versions': old.get('row_versions', {})}
    job.status = command['status']
    job.error = None
    job.started_at = job.finished_at = job.dispatched_at = None
    job.payload = {**job.payload, 'draft_name': draft_name(job)}
    ledger = db.get(models.AutoReglueConfig, key(job.id))
    ledger.value = {**command, 'state': 'applied'}
    db.commit()
    return True


def request(db, job_id, request_id, user, *, scope, percentages, title_rewrite_mode, planning_mode='percentages'):
    from app.auto_pilot import get, scope_sites, selected_scope_sites
    from app.pilot_mixed import parameters as settings
    parameters = {'planning_filter': scope.model_dump(),
        **settings(db, percentages, title_rewrite_mode, planning_mode)}
    signature = auto.digest(parameters)
    receipt_key = 'pilot-replan-request:' + str(request_id)
    with network_lock(db, 'mass-reglue-list-start'):
        job = get(db, job_id, user)
        receipt = db.get(models.AutoReglueConfig, receipt_key)
        if receipt:
            if receipt.value != {'job_id': job.id, 'signature': signature}:
                raise ValueError('Идентификатор запроса уже использован с другими параметрами.')
            return job
        if job.kind != launch.PREVIEW_KIND:
            raise NetworkConflict('Запущенное задание нельзя перепланировать. Создайте новый черновик.')
        if pending(db, job.id):
            raise NetworkConflict('Обновление этого черновика уже запрошено. Дождитесь новой подготовки.')
        ids = [site.id for site in selected_scope_sites(scope_sites(db, user), scope)]
        ids = [sid for sid in ids if sid not in job.payload.get('excluded_site_ids',[]) and (not job.payload.get('fixed_site_ids') or sid in job.payload['fixed_site_ids'])]
        if not ids:
            raise ValueError('Нет проектов для выбранного бренда и GEO.')
        allowed = user.get('allowed_site_ids')
        fresh = launch.initial_job(db, job.id, ids, user['username'], None if allowed is None else set(allowed), preview_only=True)
        payload = {**fresh.payload, **parameters, **{key:deepcopy(job.payload[key]) for key in ('excluded_site_ids','excluded_projects','original_site_ids','fixed_site_ids','template_report_id','template_report_number','source_maintenance_report_id') if key in job.payload}}
        if planning_mode == 'mixed': payload['execution_mode'] = 'cross_network'
        command = {'state': 'pending', 'request_id': str(request_id), 'payload': payload, 'previous_completed': job.status == 'completed',
            'result': fresh.result, 'status': fresh.status, 'requested_at': datetime.now(timezone.utc).isoformat()}
        ledger = db.get(models.AutoReglueConfig, key(job.id))
        if ledger is None:
            ledger = models.AutoReglueConfig(key=key(job.id)); db.add(ledger)
        ledger.value = command
        db.add(models.AutoReglueConfig(key=receipt_key, value={'job_id': job.id, 'signature': signature}))
        # The occupied lock may belong to a row refresh or version selection,
        # not a planner. Queue the same job so a dispatcher will consume the
        # command even if that other operation has no planning checkpoint.
        job.status = 'queued'
        job.dispatched_at = None
        db.commit()
        # A running worker sees the durable command at its next checkpoint. An
        # idle preview can be replaced immediately under the very same lock.
        try:
            with network_lock(db, 'mass-reglue-list:' + job.id):
                db.refresh(job)
                apply_pending(db, job)
        except NetworkConflict:
            pass
        return job
