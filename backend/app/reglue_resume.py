"""Resume existing writes only when their first stage is proven by fresh data."""
from datetime import datetime, timezone
from sqlalchemy import select
from app import models


def primary_matches(operation, state):
    payload = operation.request_payload or {}
    if operation.action in {'create_fake_main', 'select_fake_main'}:
        desired = payload.get('alternate')
        return bool(desired and all(state.get('fake_main_settings', {}).get(k) == v for k, v in desired.items()))
    if operation.action == 'reglue':
        return bool(payload.get('reserve') and state.get('canon') == payload['reserve'])
    from app.project_network import operation_matches
    return operation_matches(operation, state) if operation.action in {'alternates', 'reserve'} else False


def reconcile(db, site, state):
    """Do not replay a failed mutation. Allow its unperformed head stage to finish."""
    changed = False
    for op in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id == site.id, models.NetworkOperation.status == 'failed')):
        run_id = op.request_payload.get('auto_run_id')
        run = db.get(models.AutoReglueRun, run_id) if run_id else None
        if not run or run.status == 'cancelled' or not run.plan.get('list_launch_id'):
            continue
        if state.get('canon') not in {run.plan.get('old_main'), run.plan.get('new_main')}:
            continue
        if not primary_matches(op, state):
            continue
        at = datetime.now(timezone.utc).isoformat()
        from app.reglue_dns import note
        note(db, run, run.plan['new_main'], f'Настройки подтверждены Webdev. Ответ при сохранении: HTTP {op.response_status}. {op.message}')
        op.request_payload = {**op.request_payload, 'recovered_response': {
            'message': op.message, 'status': op.response_status, 'verified_at': at}}
        op.status = 'unknown'
        op.message = 'Сохранённые настройки подтверждены. Завершаем оставшиеся этапы.'
        run.plan = {**run.plan, 'read_retryable': True, 'write_recovered_at': at}
        changed = True
    if changed:
        db.commit()
    return changed


def resumable(run):
    return bool(run and run.status in {'partial', 'failed', 'waiting'}
                and run.plan.get('list_launch_id') and (run.plan.get('read_retryable') or run.status == 'waiting'))
