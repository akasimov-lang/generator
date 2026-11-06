"""Retry only unstarted rows rejected by the former-Main validation."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

from app import models, mass_reglue_launch as launch
from app.project_network import NetworkConflict, network_lock

FORMER_MAIN_ERRORS = {
    'Выбранный домен уже использовался как Main в этой сетке.',
    'Выбранный домен уже использовался как Main.',
}


def retry_former_main_rows(db, job_id, actor):
    with network_lock(db, 'mass-reglue-list:' + str(job_id)):
        job = db.get(models.BackgroundJob, str(job_id))
        if not job or job.kind != launch.KIND or not job.payload.get('streaming_start'):
            raise NetworkConflict('Требуется запущенный потоковый план Auto Pilot.')
        if job.status == 'cancelled':
            raise NetworkConflict('План отменён.')
        result = deepcopy(job.result)
        plans = {p['site_id']: p for g in result['groups'] for p in g.get('plans', [])}
        selected = [sid for sid, row in result['items'].items()
            if sid in plans and row.get('status') == 'failed'
            and row.get('reason') in FORMER_MAIN_ERRORS and not row.get('run_id')
            and not db.get(models.AutoReglueRun, str(uuid5(UUID(job.id), sid)))]
        if not selected:
            return {'job_id': job.id, 'retried': []}
        now = datetime.now(timezone.utc).isoformat()
        key = 'pilot-error-recovery:' + str(uuid4())
        db.add(models.AutoReglueConfig(key=key, value={
            'job_id': job.id, 'actor': actor, 'at': now, 'site_ids': selected,
            'status_before': job.status, 'result_before': deepcopy(job.result)}))
        for sid in selected:
            row = result['items'][sid]
            row['retry_history'] = [*(row.get('retry_history') or []), {
                'at': now, 'actor': actor, 'reason': row['reason'], 'backup_key': key}]
            row.update(status='pending', reason=None, phase='prepared')
        for group in result['groups']:
            if set(group['site_ids']).intersection(selected):
                group['status'] = 'waiting'
        job.result = result
        job.status = 'queued'
        job.finished_at = job.dispatched_at = None
        job.error = None
        db.commit()
        return {'job_id': job.id, 'retried': selected, 'backup_key': key}
