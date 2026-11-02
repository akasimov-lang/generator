"""Confirmed Main changes, with an immutable confirmation time and Moscow weeks."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app import models

MOSCOW = ZoneInfo('Europe/Moscow')


def utc(value):
    if isinstance(value, str):
        try: value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError: return None
    if not isinstance(value, datetime): return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def week_start(now=None):
    local = (utc(now) or datetime.now(timezone.utc)).astimezone(MOSCOW)
    return (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def changed_this_week(site, now=None):
    last = utc(site.last_reglue_at)
    current = utc(now) or datetime.now(timezone.utc)
    return bool(last and week_start(current) <= last <= current)


def weekly_reason(site, now=None):
    if not changed_this_week(site, now): return None
    stamp = utc(site.last_reglue_at).astimezone(MOSCOW).strftime('%d.%m.%Y, %H:%M')
    return f'Исключён: уже переклеен на текущей календарной неделе — {stamp} МСК. Доступен со следующего понедельника.'


def observe_main(site, before, after, at=None):
    """A changed Webdev Main is evidence even when no local operation exists.

    This is the time the change was observed, not a domain's membership date.
    Initial imports, partial responses and membership-only updates do not count.
    """
    from app.network_state import domain_name
    before, after = domain_name(before), domain_name(after)
    if not before or not after or before == after:
        return
    at = utc(at) or datetime.now(timezone.utc)
    if not utc(site.last_reglue_at) or utc(site.last_reglue_at) < at:
        site.last_reglue_at = at


def confirm(site, operation):
    if operation.action != 'reglue': return
    payload = operation.request_payload or {}
    source, target = payload.get('source_domain'), payload.get('reserve')
    if source and target and source == target: return
    at = utc(payload.get('confirmed_at')) or datetime.now(timezone.utc)
    operation.request_payload = {**payload, 'confirmed_at': at.isoformat()}
    if not utc(site.last_reglue_at) or utc(site.last_reglue_at) < at:
        site.last_reglue_at = at


def backfill(db):
    """Historical receipts lack confirmed_at; use their recorded confirmation update."""
    changed = 0
    for op in db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.action == 'reglue', models.NetworkOperation.status == 'confirmed')):
        site = db.get(models.Site, op.site_id)
        if not site: continue
        payload = op.request_payload or {}
        if payload.get('source_domain') and payload.get('source_domain') == payload.get('reserve'): continue
        at = utc(payload.get('confirmed_at')) or utc(op.updated_at)
        if at and (not utc(site.last_reglue_at) or utc(site.last_reglue_at) < at):
            site.last_reglue_at = at
            changed += 1
    for site in db.scalars(select(models.Site)):
        before_at = utc(site.last_reglue_at)
        previous = None
        for snapshot in site.network_snapshot_history or []:
            canon = snapshot.get('canon')
            at = utc(snapshot.get('observed_at'))
            if previous and canon and at:
                observe_main(site, previous, canon, at)
            if canon:
                previous = canon
        if utc(site.last_reglue_at) != before_at:
            changed += 1
    db.commit()
    return changed
