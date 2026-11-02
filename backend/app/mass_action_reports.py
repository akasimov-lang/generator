"""Durable launch manifests; report rows come from confirmed execution receipts."""
from datetime import datetime, timezone
from sqlalchemy import select
from app import models
from app.mass_action_scope import brand_key


def save(db, report_id, filters, results, actor, skipped=()):
    key = 'mass-report:' + str(report_id)
    row = db.get(models.AutoReglueConfig, key)
    if row is None:
        row = models.AutoReglueConfig(key=key, value={})
        db.add(row)
    elif row.value.get('filter') != filters:
        raise ValueError('Идентификатор отчёта уже использован для другого бренда или GEO.')
    previous = {item['site_id']: item for item in row.value.get('results', [])}
    for result in results:
        if previous.get(result['site_id'], {}).get('run_id') not in {None, result.get('run_id')}:
            raise ValueError('Запуск проекта уже записан в этом отчёте.')
        run = db.get(models.AutoReglueRun, result.get('run_id')) if result.get('run_id') else None
        if run:
            run.plan = {**run.plan, 'mass_report_id': str(report_id)}
        previous[result['site_id']] = {**result, **(entry(run) if run else {})}
    row.value = {**row.value, 'id': str(report_id), 'filter': filters, 'actor': row.value.get('actor') or actor,
                 'brand_key': brand_key(filters['brand']), 'geo': filters['geo'],
                 'created_at': row.value.get('created_at') or datetime.now(timezone.utc).isoformat(),
                 'results': list(previous.values()), 'skipped': list(skipped)}
    db.commit()


def refresh_run(db, run):
    """Persist a complete result in the same transaction as execution completion."""
    report_id = run.plan.get('mass_report_id')
    if not report_id:
        return
    row = db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key == 'mass-report:' + report_id)
                    .with_for_update().execution_options(populate_existing=True))
    if row:
        row.value = {**row.value, 'results': [{**result, **entry(run)} if result.get('run_id') == run.id else result
                                             for result in row.value['results']]}


def entry(run):
    plan = run.plan
    domain_errors = plan.get('domain_errors', [])
    message = run.message
    if not domain_errors and not plan.get('use_selected_reserve') and run.status in {'partial','failed'} and plan.get('execution_mode') in {'transfer_only','cross_network'}:
        raw = run.message or ''
        code = 'SUBDOMAIN_CREATE_FAILED' if 'создания поддомена' in raw.lower() else 'DNS' if 'ошибка dns' in raw.lower() else 'TRANSFER_STOPPED'
        simple = ('Webdev не завершил создание поддомена (CDN/DMS).' if code=='SUBDOMAIN_CREATE_FAILED' else
                  'Webdev сообщил об ошибке DNS.' if code=='DNS' else raw or 'Операция остановлена без описания причины. Проверьте журнал.')
        domain_errors = [{'domain': d['domain'], 'code':code, 'message':simple, 'system_response':raw} for d in (plan.get('domains') or [{'domain':plan.get('new_main')}]) if d.get('domain')]
        message = raw or simple
    applied = plan.get('applied_result') or {}
    # None denotes an unknown historic value, never an invented previous path.
    old_path = plan.get('old_fake_main_path')
    confirmed = run.status == 'completed'
    new_path = applied.get('fake_main_path', plan.get('new_fake_main_path')) if confirmed else None
    from app.transfer_confirmation import view as confirmation_view
    return {'run_id': run.id, 'status': run.status, 'phase': run.phase, 'message': message,
            'confirmation': confirmation_view(run),
            'use_selected_reserve': bool(plan.get('use_selected_reserve')),
            'verification': plan.get('report_verification'),
            'domain_errors': domain_errors, 'replacement_error': plan.get('replacement_error'),
            'drop_domains': [d['domain'] for d in plan.get('domains',[]) if d.get('domain_type')=='drop'],
            'rolled_back_at': plan.get('rolled_back_at'),
            'source_site_id': plan.get('source_site_id', run.site_id),
            'source_project': plan.get('source_project') or plan.get('project'),
            'target_project': plan.get('project'),
            'domains': [d['domain'] for d in plan.get('domains', [])] or [plan.get('new_main')],
            'old_main': plan.get('old_main'), 'new_main': applied.get('new_main', plan.get('new_main', plan.get('old_main'))) if confirmed else None,
            'old_fake_main_path': old_path, 'new_fake_main_path': new_path,
            'confirmed_at': applied.get('confirmed_at') or (run.updated_at.isoformat() if run.status == 'completed' else None)}


def list_reports(db, brand, geo, allowed=None):
    rows = db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.like('mass-report:%'),
                      models.AutoReglueConfig.value['brand_key'].as_string() == brand_key(brand),
                      models.AutoReglueConfig.value['geo'].as_string() == geo)
                      .order_by(models.AutoReglueConfig.created_at.desc()).limit(500)).all()
    reports = []
    for row in rows:
        value = row.value
        scope = value['filter']
        if brand_key(scope['brand']) != brand_key(brand) or scope['geo'] != geo:
            continue
        if allowed is not None and any(item.get('site_id') not in allowed for item in value.get('skipped', [])):
            continue
        entries = []
        permitted = True
        for result in value['results']:
            run = db.get(models.AutoReglueRun, result.get('run_id')) if result.get('run_id') else None
            participants = {result['site_id']}
            if result.get('source_site_id'):
                participants.add(result['source_site_id'])
            if run and run.plan.get('source_site_id'):
                participants.add(run.plan['source_site_id'])
            if allowed is not None and not participants.issubset(allowed):
                permitted = False; break
            entries.append(entry(run) if run else result)
        if permitted:
            reports.append({**value, 'entries': entries})
        if len(reports) == 50:
            break
    return reports
