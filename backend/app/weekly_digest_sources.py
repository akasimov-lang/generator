"""Bounded, local-only weekly evidence for the narrative digest.

Stored network/cache observations remain labelled with their original time. No
Webdev requests or content/network mutations are made while collecting reports.
Large original-project backups and upload bodies are never selected as ledgers.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import or_, select
from sqlalchemy.orm import load_only

from app import models, project_state_reports as reports
from app.reglue_history import utc
from app.weekly_digest_review import unresolved

RECEIPT_FIELDS = ('field', 'kind', 'brand', 'status', 'confirmed_at', 'verified_at', 'checked_at', 'at', 'message')
MIGRATION_FIELDS = ('status', 'presentation_status', 'presentation_verified_at', 'confirmed_at', 'message', 'before_count', 'after_count')
INFO_KEYS = ('state_report_sources', 'state_report_ledgers', 'state_report_menu_logs')


def _maintenance(db):
    grouped = defaultdict(list)
    q = select(models.BackgroundJob.id,
        models.BackgroundJob.payload['task_type'].as_string().label('task_type'),
        models.BackgroundJob.payload['name'].as_string().label('name'),
        models.BackgroundJob.result['entries'].label('entries'),
    ).where(models.BackgroundJob.kind == 'maintenance_report')
    for source in db.execute(q).mappings():
        if source['task_type'] in {'project_state_report', 'weekly_digest'}:
            continue
        for entry in source['entries'] or []:
            if not isinstance(entry, dict) or not entry.get('site_id'):
                continue
            safe = {k: entry[k] for k in ('site_id', 'status', 'confirmed_at', 'finished_at', 'message', 'comment') if k in entry}
            migration = entry.get('migration') or {}
            safe['migration'] = {k: migration[k] for k in MIGRATION_FIELDS if k in migration}
            grouped[entry['site_id']].append(SimpleNamespace(id=source['id'],
                payload={'task_type': source['task_type'], 'name': source['name']}, result={'entries': [safe]}))
    return grouped


def _ledgers(db):
    # JSON projections are intentional: value also contains whole project
    # backups and, for logo repairs, potentially large encoded asset bodies.
    config = models.AutoReglueConfig
    fields = ('site_id', 'status', 'applied_at', 'verified_at', 'receipts', 'contrast_receipt')
    q = select(config.key, *(config.value[k].label(k) for k in fields)).where(
        config.key.like('site-%repair:%') | config.key.like('showcase-%'))
    grouped = defaultdict(list)
    for source in db.execute(q).mappings():
        if not source['site_id']:
            continue
        value = {k: source[k] for k in fields if source[k] is not None}
        value['receipts'] = [{k: receipt[k] for k in RECEIPT_FIELDS if k in receipt}
                             for receipt in source['receipts'] or [] if isinstance(receipt, dict)]
        if isinstance(source['contrast_receipt'], dict):
            value['contrast_receipt'] = {k: source['contrast_receipt'][k] for k in RECEIPT_FIELDS if k in source['contrast_receipt']}
        grouped[source['site_id']].append(SimpleNamespace(key=source['key'], value=value))
    return grouped


def _menu_logs(db, end):
    log = models.PublicationLog
    fields = ('action', 'project_name', 'type', 'list')
    q = select(log.id, log.created_at, log.response_status, log.error_message,
               *(log.request_payload[k].label(k) for k in fields)).where(
        log.request_payload['action'].as_string() == 'menu_sync', log.created_at < end,
    ).order_by(log.created_at, log.id)
    grouped = defaultdict(list)
    for source in db.execute(q).mappings():
        grouped[source['project_name']].append(SimpleNamespace(id=source['id'],
            created_at=source['created_at'], response_status=source['response_status'], error_message=source['error_message'],
            request_payload={k: source[k] for k in fields}))
    return grouped


def _operations(db, event_ids, sites):
    if not event_ids:
        return []
    op = models.NetworkOperation
    fields = ('reserve', 'source_domain', 'redirects_before', 'redirects_after', 'redirect_old_main', 'auto_run_id')
    q = select(op.id, op.site_id, op.status, *(op.request_payload[k].label(k) for k in fields),
        op.request_payload['journal_before']['main'].label('before_main'),
        op.request_payload['journal_after']['main'].label('after_main'),
        op.request_payload['cross_network_transfer']['source_site_id'].label('source_site_id'),
        op.request_payload['cross_network_transfer']['target_site_id'].label('target_site_id'),
    ).where(op.id.in_(event_ids), op.status == 'confirmed')
    result = []
    for source in db.execute(q).mappings():
        payload = {k: source[k] for k in fields if source[k] is not None}
        payload.update(journal_before={'main': source['before_main']}, journal_after={'main': source['after_main']},
            cross_network_transfer={k: source[k] for k in ('source_site_id', 'target_site_id') if source[k] is not None})
        result.append({'id': source['id'], 'site_id': source['site_id'], 'status': source['status'],
            'payload': payload, 'types': deepcopy(sites[source['site_id']].domain_types or {})})
    return result


def _runs(db, operations):
    ids = {op['payload']['auto_run_id'] for op in operations if op['payload'].get('auto_run_id')}
    if not ids:
        return []
    run = models.AutoReglueRun
    fields = ('balance_mode', 'combination_id', 'domain_type', 'main_target_kind', 'required_domain_type')
    return [{'id': source['id'], 'site_id': source['site_id'], 'status': source['status'],
             'plan': {k: source[k] for k in fields if source[k] is not None}}
        for source in db.execute(select(run.id, run.site_id, run.status,
            *(run.plan[k].label(k) for k in fields)).where(run.id.in_(ids))).mappings()]


def collect(db, start, end):
    """Collect confirmed work in ``[start, end)`` and current logical leftovers."""
    start, end = utc(start), utc(end)
    if start is None or end is None or start >= end:
        raise ValueError('Invalid weekly report interval')
    inclusive_end = end - timedelta(microseconds=1)
    maintenance, ledgers, menus = _maintenance(db), _ledgers(db), _menu_logs(db, end)
    site = models.Site
    sites = {s.id: s for s in db.scalars(select(site).options(load_only(
        site.id, site.name, site.brand, site.cache_geo, site.cache_canon, site.cache_synced_at,
        site.fibery_name, site.domain_types, site.network_state, site.site_type,
    )).where(or_(site.is_test_project.is_(False), site.is_test_project.is_(None))).order_by(site.name, site.id))}
    missing = object()
    previous = {key: db.info.get(key, missing) for key in INFO_KEYS}
    rows = []
    try:
        for current in sites.values():
            db.info['state_report_sources'] = maintenance[current.id]
            db.info['state_report_ledgers'] = ledgers[current.id]
            db.info['state_report_menu_logs'] = menus[current.name]
            state = deepcopy(current.network_state or {})
            value = reports.row(db, current, state, start, inclusive_end, current.cache_synced_at, 'cache')
            if not value['events']:
                continue
            value['site_type'] = current.site_type
            if not state or not current.cache_synced_at or not state.get('has_head'):
                value.update(status='partial', state_error='Текущая схема не подтверждена: нет полного сохранённого снимка сетки.')
            rows.append(value)
    finally:
        for key, value in previous.items():
            if value is missing:
                db.info.pop(key, None)
            else:
                db.info[key] = value
    event_ids = {event['id'] for row in rows for event in row['events'] if event['kind'] == 'reglue'}
    operations = _operations(db, event_ids, sites)
    return {'rows': rows, 'operations': operations, 'runs': _runs(db, operations),
            'review': [ref for ref in unresolved(db, start, end) if ref['site_id'] in sites]}
