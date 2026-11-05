"""Project-only timeline of recorded automatic runs and group reports."""
from sqlalchemy import select
from app import models


def changes(before, after, prefix=''):
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        rows = []
        for key in sorted(set(before) | set(after)):
            if any(secret in key.lower() for secret in ('token', 'password', 'secret', 'authorization', 'buffer')):
                continue
            rows.extend(changes(before.get(key), after.get(key), f'{prefix}.{key}'.strip('.')))
        return rows
    return [{'field': prefix or 'Данные', 'before': before, 'after': after}]


def timeline(db, site_id):
    result = []
    for run in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.site_id == site_id).order_by(models.AutoReglueRun.created_at.desc())):
        plan = run.plan or {}
        diff = []
        for label, left, right in [('Main', 'old_main', 'new_main'), ('Внутренняя страница', 'old_fake_main_path', 'new_fake_main_path'), ('Альтернейты', 'alternates_before', 'alternates_after'), ('Сетка источника', 'source_before', 'source_after'), ('Сетка назначения', 'target_before', 'target_after')]:
            if left in plan or right in plan:
                diff.extend(changes(plan.get(left), plan.get(right), label))
        result.append({'id': run.id, 'title': 'Автоматические действия с сеткой', 'status': run.status,
                       'created_at': run.created_at, 'actor': run.initiator, 'message': run.message,
                       'changes': diff, 'confirmed': run.status == 'completed',
                       'url': f'/auto-reglue/pilot/logs?id={run.id}'})
    for job in db.scalars(select(models.BackgroundJob).order_by(models.BackgroundJob.created_at.desc())):
        if 'index' in job.kind:
            continue
        payload, outcome = job.payload or {}, job.result or {}
        entries = outcome.get('entries', []) if isinstance(outcome, dict) else []
        entry = next((row for row in entries if isinstance(row, dict) and row.get('site_id') == site_id), None)
        if entry is None:
            if payload.get('site_id') != site_id or not (payload.get('batch_id') or payload.get('report_id') or payload.get('mass_filter')):
                continue
            entry = outcome if isinstance(outcome, dict) else {}
        diff = changes(entry.get('before'), entry.get('after'))
        # Project-specific page results have their own receipts; link to the complete report.
        status = entry.get('status', job.status)
        result.append({'id': job.id, 'title': payload.get('name') or payload.get('action') or 'Групповые действия',
                       'status': status, 'created_at': job.started_at or job.created_at,
                       'actor': payload.get('actor') or payload.get('initiator') or '',
                       'message': entry.get('message') or entry.get('error') or '', 'changes': diff,
                       'confirmed': status == 'completed',
                       'url': f'/auto-reglue/pilot/report?maintenance={job.id}' if job.kind == 'maintenance_report' else None})
    return sorted(result, key=lambda row: row['created_at'].isoformat(), reverse=True)
