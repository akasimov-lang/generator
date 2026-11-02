"""Durable minute-by-minute reconciliation for 30 minutes after a reglue."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app import models
from app.project_network import network_lock, NetworkConflict

INTERVAL = 60
WINDOW = timedelta(minutes=30)
LEASE = timedelta(minutes=5)


def utc(value):
    if not value: return None
    if isinstance(value, str): value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def start(db, run, *, now=None):
    if not run or run.status not in {'completed', 'partial', 'failed', 'waiting'}:
        return False
    if run.plan.get('execution_mode') == 'transfer_only': return False
    now = now or datetime.now(timezone.utc)
    previous = run.plan.get('post_reglue_monitor') or {}
    completed = utc(run.plan.get('completed_at')) if run.status == 'completed' else None
    if previous:
        # Waiting for provisioning is not part of the post-publication window.
        # completed_at is stable, unlike the time of a subsequent verification.
        if not completed or completed <= utc(previous['started_at']): return False
        started = completed
    else:
        started = max(now, completed) if completed else now
    run.plan = {**run.plan, 'post_reglue_monitor': {
        'state': 'watching', 'started_at': started.isoformat(), 'deadline_at': (started + WINDOW).isoformat(),
        'next_check_at': (now + timedelta(seconds=INTERVAL)).isoformat(), 'queued_at': now.isoformat(),
        'attempts': 0, 'message': 'Проверяем применение настроек и доступность доменов раз в минуту в течение 30 минут.',
        **({'before_completion': previous} if previous else {}),
    }}
    db.commit()
    return True


def dispatch(db, send, *, now=None):
    now = now or datetime.now(timezone.utc)
    ids = list(db.scalars(select(models.AutoReglueRun.id).where(
        models.AutoReglueRun.plan['post_reglue_monitor']['state'].as_string() == 'watching')))
    sent = 0
    for id in ids:
        try:
            with network_lock(db, 'auto-run:' + id):
                run = db.get(models.AutoReglueRun, id); db.refresh(run)
                monitor = dict(run.plan.get('post_reglue_monitor') or {})
                if run.status == 'cancelled':
                    run.plan = {**run.plan, 'post_reglue_monitor': {**monitor, 'state': 'cancelled', 'next_check_at': None}}
                    db.commit(); continue
                due = utc(monitor.get('next_check_at'))
                if monitor.get('state') != 'watching' or due is None or due > now: continue
                queued = utc(monitor.get('queued_at'))
                if queued and queued + LEASE > now: continue
                # Persist intent first. Broker/worker failure is recovered after the lease.
                run.plan = {**run.plan, 'post_reglue_monitor': {**monitor, 'queued_at': now.isoformat()}}
                db.commit()
                try: send(id)
                except Exception:
                    run.plan = {**run.plan, 'post_reglue_monitor': {**monitor, 'queued_at': None}}
                    db.commit(); continue
                sent += 1
        except NetworkConflict:
            db.rollback()
    return {'dispatched': sent}


def check(db, run_id, *, now=None):
    from app.reglue_recheck import check_run
    from app.reglue_dns import audit_pages, archive_confirmed_notes
    from app.mass_action_reports import refresh_run
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    with network_lock(db, 'auto-run:' + run_id):
        run = db.get(models.AutoReglueRun, run_id)
        if not run or run.status == 'cancelled': return {'status': 'cancelled'}
        monitor = dict(run.plan.get('post_reglue_monitor') or {})
        if monitor.get('state') != 'watching': return {'status': 'finished'}
        due = utc(monitor.get('next_check_at'))
        if due is None or due > now: return {'status': 'not_due'}
        result = check_run(db, run_id)
        if (now < utc(monitor['deadline_at']) and result and result['status'] == 'mismatch'
                and (run.status == 'waiting' or run.plan.get('read_retryable'))
                and run.status in {'waiting', 'failed', 'partial'}):
            # Continue the SAME saved run. Its receipts prevent repeating confirmed
            # writes and force uncertain writes through Webdev reconciliation.
            from app.auto_reglue import execute
            run.status = 'waiting'
            run.plan = {**run.plan, 'read_retryable': False}
            db.commit()
            execute(db, run.id)
            result = check_run(db, run_id)
        if start(db, run, now=fixed_now or datetime.now(timezone.utc)):
            monitor = dict(run.plan['post_reglue_monitor'])
        availability = audit_pages(db, run)
        now = fixed_now or datetime.now(timezone.utc)
        confirmed = bool(result and result['status'] == 'confirmed')
        if confirmed: archive_confirmed_notes(db, run)
        healthy = confirmed and bool(availability) and all(item['ok'] for item in availability)
        done = now >= utc(monitor['deadline_at'])
        message = ('Настройки и доступность подтверждены.' if healthy else
                   'Требуется ручная проверка: ' + ((result or {}).get('message') or 'Не удалось проверить сетку.') if done else
                   'Перепроверяем настройки и доступность. Следующая проверка через минуту.')
        if done and confirmed and not healthy:
            message = 'Требуется ручная проверка доступности доменов. Настройки переклея подтверждены.'
        run.plan = {**run.plan, 'post_reglue_monitor': {
            **monitor, 'state': ('confirmed' if healthy else 'manual') if done else 'watching',
            'attempts': monitor.get('attempts', 0) + 1, 'checked_at': now.isoformat(),
            'next_check_at': None if done else (now + timedelta(seconds=INTERVAL)).isoformat(),
            'queued_at': None, 'message': message, 'availability': availability,
        }}
        refresh_run(db, run); db.commit()
        return {'status': run.plan['post_reglue_monitor']['state'], 'healthy': healthy}
