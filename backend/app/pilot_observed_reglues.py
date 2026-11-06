"""Attribute already confirmed moves to every affected plan without starting work."""
from collections import defaultdict
from copy import deepcopy

from sqlalchemy import select

from app import models
from app.network_state import domain_name
from app.reglue_history import utc
from app.reglue_journal import confirmed_at


def evidence(db, job, result=None):
    result = result if result is not None else job.result or {}
    rows = result.get('items', {})
    plans = {p['site_id']: p for g in result.get('groups', []) for p in g.get('plans', [])}
    own_runs = {r['run_id'] for r in rows.values() if r.get('run_id')}
    operations = defaultdict(list)
    if rows:
        for op in db.scalars(select(models.NetworkOperation).where(
                models.NetworkOperation.site_id.in_(rows),
                models.NetworkOperation.action == 'reglue',
                models.NetworkOperation.status == 'confirmed')):
            operations[op.site_id].append(op)
    found = {}
    for site_id, row in rows.items():
        if row.get('completed_elsewhere'):
            found[site_id] = deepcopy(row['completed_elsewhere'])
            continue
        # Never relabel or interfere with a running move, or our own success.
        run = db.get(models.AutoReglueRun, row['run_id']) if row.get('run_id') else None
        if run and run.status not in {'failed', 'cancelled'}:
            continue
        plan = plans.get(site_id, row)
        old_main = domain_name(plan.get('old_main'))
        if not old_main:
            continue
        floor = utc(job.created_at)
        history = result.get('row_versions', {}).get(site_id, {})
        selected = next((v for v in history.get('versions', []) if v['number'] == history.get('selected')), {})
        selected_at = utc(selected.get('created_at'))
        if selected_at and (not floor or selected_at > floor):
            floor = selected_at
        for op in sorted(operations[site_id], key=lambda item: (confirmed_at(item), item.id)):
            payload = op.request_payload or {}
            at = confirmed_at(op)
            old, new = domain_name(payload.get('source_domain')), domain_name(payload.get('reserve'))
            if not floor or at <= floor or old != old_main or not new or new == old:
                continue
            if payload.get('auto_run_id') in own_runs:
                continue
            other_run = db.get(models.AutoReglueRun, payload['auto_run_id']) if payload.get('auto_run_id') else None
            if other_run and (other_run.plan or {}).get('list_launch_id') == job.id:
                continue
            before, after = payload.get('journal_before') or {}, payload.get('journal_after') or {}
            found[site_id] = {'operation_id': op.id, 'source': 'confirmed_operation',
                'at': at.isoformat(), 'before': {'main': old, 'fake_path': before.get('fake_path')},
                'after': {'main': new, 'fake_path': after.get('fake_path')},
                'planned_main': plan.get('new_main'), 'run_id': payload.get('auto_run_id')}
            break
    return found


def apply(row, confirmation):
    row.update(completed_elsewhere=deepcopy(confirmation), status='completed', reason=None,
               performed_at=confirmation['at'], progress=100, phase='completed_elsewhere')


def project(db, job, rows):
    confirmations = evidence(db, job)
    for row in rows:
        if row['site_id'] in confirmations:
            apply(row, confirmations[row['site_id']])
    return confirmations


def retire(db, job, result):
    """Before dispatch, archive the exact plan and remove only already fulfilled moves."""
    confirmations = evidence(db, job, result)
    if not confirmations:
        return False
    changed = False
    from app.cross_reglue_batch import key
    for group in result.get('groups', []):
        removed = [p for p in group.get('plans', []) if p['site_id'] in confirmations]
        if not removed:
            continue
        changed = True
        group['plans'] = [p for p in group['plans'] if p['site_id'] not in confirmations]
        for plan in removed:
            row = result['items'][plan['site_id']]
            row['completed_elsewhere_plan'] = deepcopy(plan)
            apply(row, confirmations[plan['site_id']])
        if not group['plans']:
            group['status'] = 'done'
        ledger = db.get(models.AutoReglueConfig, key(group['batch_id'])) if group.get('batch_id') else None
        if ledger:
            ledger.value = {**ledger.value, 'plans': deepcopy(group['plans'])}
    return changed
