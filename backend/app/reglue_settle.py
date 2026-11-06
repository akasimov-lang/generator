"""Persist a provisioning grace period without occupying a worker with sleep."""
from datetime import datetime, timedelta, timezone
from app.reglue_history import utc

SECONDS = 15


def ready(db, run, operation, state, *, now=None):
    if operation is None:
        return True  # An existing network domain needs no provisioning delay.
    now = now or datetime.now(timezone.utc)
    domains = [item['domain'] for item in operation.request_payload.get('domains', [])]
    if operation.status != 'confirmed' or not domains or any(d not in state['domains'] for d in domains):
        run.status = 'waiting'
        run.message = 'Ждём подтверждённого добавления домена в сетку.'
        db.commit()
        return False
    confirmed = utc(operation.request_payload.get('provisioning_confirmed_at'))
    if confirmed is None:
        confirmed = now
        operation.request_payload = {**operation.request_payload, 'provisioning_confirmed_at': now.isoformat()}
    deadline = confirmed + timedelta(seconds=SECONDS)
    if now < deadline:
        run.status = 'waiting'
        run.message = 'Домен добавлен. Ждём 15 секунд перед назначением резерва.'
        run.plan = {**run.plan, 'domain_ready_after': deadline.isoformat()}
        db.commit()
        return False
    db.commit()
    return True
