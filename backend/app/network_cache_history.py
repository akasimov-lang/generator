"""Observed changes are distinct from confirmed PagePilot write receipts."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app import models

KEY = 'cache_change_history'
BASELINE = 'cache_change_baseline'


def track(site, previous, state, settings, db=None):
    events = [dict(row) for row in previous.get(KEY, [])]
    now = datetime.now(timezone.utc).isoformat()
    before = previous
    # One-time reconciliation with the last recorded snapshot also covers changes
    # fetched before observation history was introduced. Time is discovery only.
    if db is not None and not previous.get(BASELINE) and previous:
        operation = db.scalar(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id == site.id,
            models.NetworkOperation.status == 'confirmed',
            models.NetworkOperation.action.in_(['reglue','create_fake_main','select_fake_main']))
            .order_by(models.NetworkOperation.updated_at.desc(), models.NetworkOperation.id.desc()).limit(1))
        if operation:
            after = (operation.request_payload or {}).get('journal_after') or {}
            baseline = {}
            if after.get('main'): baseline['canon'] = after['main']
            if 'fake_path' in after: baseline['fake_main_current'] = after['fake_path']
            add(events, baseline, previous, now, main='canon' in baseline, fake='fake_main_current' in baseline,
                comparison='last_recorded')
    alternate = settings.get('alternate')
    add(events, before, state, now, main=bool(settings.get('canon')),
        fake=isinstance(alternate,dict) and isinstance(alternate.get('currentFakeMain'),str))
    state[BASELINE] = True
    if events: state[KEY] = events


def add(events, before, after, at, *, main, fake, comparison='observed'):
    main_changed = main and bool(before.get('canon')) and before.get('canon') != after.get('canon')
    fake_changed = fake and 'fake_main_current' in before and before.get('fake_main_current') != after.get('fake_main_current')
    if not main_changed and not fake_changed: return
    events.append({'id':str(uuid4()), 'source':'cache', 'kind':'reglue' if main_changed else 'fake_path',
        'at':at, 'comparison':comparison,
        'old_main':before.get('canon'), 'new_main':after.get('canon'),
        'old_path':before.get('fake_main_current') if fake else None,
        'new_path':after.get('fake_main_current') if fake else None})


def visible(events, receipts):
    from app.reglue_history import utc
    result=[]
    for event in events:
        at=utc(event.get('at'))
        if not at: continue
        # A cache echo of our own confirmed write is one change, not two events.
        duplicate=False
        for receipt in receipts:
            if receipt['kind'] != event['kind']: continue
            if abs((utc(receipt['at'])-at).total_seconds()) > 300: continue
            fields=('old_main','new_main') if event['kind']=='reglue' else ('old_path','new_path')
            if all(receipt.get(key)==event.get(key) for key in fields):
                duplicate=True;break
        if not duplicate: result.append(event)
    return result
