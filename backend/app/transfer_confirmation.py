"""Persisted confirmation polling metadata; never a promise of Webdev completion."""
from datetime import datetime, timedelta, timezone

INTERVAL = 15
BATCH_LIMIT = 10


def record_check(db, run, attempt):
    if run is None:
        return False
    now = datetime.now(timezone.utc)
    old = run.plan.get('confirmation') or {}
    if run.status != 'waiting' and not old:
        return False
    limit = BATCH_LIMIT if run.plan.get('batch_id') else 30
    waiting = run.status == 'waiting'
    busy = waiting and bool(run.plan.get('waiting_for_network'))
    again = waiting and (busy or attempt < limit)
    run.plan = {**run.plan, 'confirmation': {
        'started_at': old.get('started_at') or (now.isoformat() if waiting else None),
        'checked_at': now.isoformat(),
        'next_check_at': (now + timedelta(seconds=INTERVAL)).isoformat() if again else None,
        'attempt': attempt, 'limit': limit, 'interval_seconds': INTERVAL, 'waiting_for_network': busy,
        'exhausted': waiting and not again,
    }}
    db.commit()
    return again


def view(run):
    data = dict(run.plan.get('confirmation') or {})
    if run.status != 'waiting':
        data.update(next_check_at=None, exhausted=False)
    data.update(operation_started_at=(run.created_at.isoformat() if run.created_at else None))
    return data
