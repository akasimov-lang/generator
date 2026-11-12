"""Explicit, read-only rechecks of individual sitemap report rows."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5, NAMESPACE_URL
from sqlalchemy import select
from app import models, maintenance_reports, network_sitemap, sitemap_maintenance
from app.project_network import Remote, network_lock

KIND = 'sitemap_row_recheck'
ACTIVE = {'queued', 'running'}


def locked_report(db, report_id):
    report = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == str(report_id))
                       .with_for_update().execution_options(populate_existing=True))
    if not report or report.kind != maintenance_reports.KIND or report.payload.get('task_type') != sitemap_maintenance.TASK:
        raise ValueError('Нужен отчёт проверки sitemap.')
    return report


def save_row(report, row):
    rows = [row if r['site_id'] == row['site_id'] else r for r in report.result['entries']]
    report.result = {**report.result, 'entries': rows}
    active = any(r['status'] in {'pending', 'running', 'waiting'} for r in rows)
    report.status = 'running' if active else 'completed' if all(r['status'] in {'completed', 'skipped'} for r in rows) else 'partial'
    report.finished_at = None if active else datetime.now(timezone.utc)


def prepare(db, report_id, site_id, request_id, user):
    maintenance_reports.get(db, report_id, user)  # Full report visibility, before mutation.
    report = locked_report(db, report_id)
    site_id = str(site_id)
    row = next((r for r in report.result['entries'] if r['site_id'] == site_id), None)
    site = db.get(models.Site, site_id)
    if not row or not site or site.hidden_from_projects or not site.is_active or site.project_status != 'mass_actions':
        raise ValueError('Проект не входит в доступную группу массовых действий отчёта.')
    job_id = str(uuid5(NAMESPACE_URL, f'{KIND}:{report.id}:{site_id}:{UUID(str(request_id))}'))
    if db.get(models.BackgroundJob, job_id):
        db.commit()
        return report
    pending = db.get(models.BackgroundJob, (row.get('recheck') or {}).get('id')) if row.get('recheck') else None
    if pending and pending.status in ACTIVE:
        db.commit()
        return report
    if row['status'] not in {'partial', 'failed'}:
        raise ValueError('Перепроверка доступна для строк с ошибкой или частичным результатом.')
    now = datetime.now(timezone.utc)
    db.add(models.BackgroundJob(id=job_id, kind=KIND, payload={
        'actor': user['username'], 'site_id': site_id, 'report_id': report.id,
    }))
    previous = {key: deepcopy(row.get(key)) for key in ('main', 'status', 'error', 'finished_at')}
    previous['sitemap'] = {key: deepcopy(value) for key, value in (row.get('sitemap') or {}).items() if key != 'before'}
    save_row(report, {**row, 'status': 'running',
        'recheck_history': [*row.get('recheck_history', []), previous],
        'recheck': {'id': job_id, 'requested_at': now.isoformat()}})
    db.commit()  # Dispatcher will retry a lost broker delivery; no synchronous remote I/O.
    return report


def check(db, site, row):
    evidence = deepcopy(row.get('sitemap') or {})
    result = {'sitemap': evidence}
    try:
        if not site or site.hidden_from_projects or not site.is_active or site.project_status != 'mass_actions':
            raise ValueError('Проект больше не имеет статуса «Массовые действия».')
        with network_lock(db, site.id), Remote(db, site) as remote:
            project = remote.project()
            main, urls = network_sitemap.expected(project)
            result['main'] = main
            evidence.update(sitemap_url=f'https://{main}/sitemap.xml', expected_count=len(urls), internal_pages=len(urls)-1,
                            webdev_verified=False, action='checking')
            # Clear stale public evidence as soon as the authoritative Main changes.
            evidence['after'] = {}
            public = sitemap_maintenance.public_snapshot(main, urls)
            current = remote.project()
            if network_sitemap.expected(current) != (main, urls):
                raise ValueError('Main или страницы изменились во время проверки. Повторите обновление строки.')
            try:
                stored = network_sitemap.locations(current.get('sitemap') or '')
                webdev_valid = len(stored) == len(urls) and set(stored) == set(urls)
            except ValueError:
                webdev_valid = False
            evidence.update(after=public, webdev_verified=webdev_valid)
            # Preserve confirmed earlier writes; a recheck itself never writes a sitemap.
            written = (row.get('sitemap') or {}).get('action') in {'updated', 'saved_unconfirmed'} and row.get('main') == main
            if public.get('valid'):
                result.update(status='completed', error=None)
                evidence['action'] = 'updated' if written else 'verified'
            else:
                error = public.get('error') or 'Публичный sitemap не подтверждён.'
                if public.get('status') == 404:
                    error = 'Текущий Main возвращает HTTP 404. Проверить публикацию sitemap на хостинге.'
                elif public.get('status') in {301, 302, 303, 307, 308}:
                    error = f"Sitemap текущего Main перенаправляется на {public.get('location') or 'другой URL'}. Нужен прямой ответ на выбранном Main."
                result.update(status='partial' if webdev_valid else 'failed', error=error)
                evidence['action'] = 'saved_unconfirmed' if written and webdev_valid else 'hosting_error'
            if row.get('main') != main:
                evidence['updated_urls'] = 0

        return result
    except Exception as error:
        db.rollback()
        evidence['action'] = 'check_error'
        return {**result, 'status': 'failed', 'error': str(error)[:700]}


def finish(db, job, result):
    report = locked_report(db, job.payload['report_id'])
    row = next((r for r in report.result['entries'] if r['site_id'] == job.payload['site_id']), None)
    if not row or (row.get('recheck') or {}).get('id') != job.id:
        return {'status': 'superseded'}
    save_row(report, {**row, **result, 'finished_at': datetime.now(timezone.utc).isoformat()})
    db.commit()
    return {'site_id': row['site_id'], 'report_id': report.id, 'status': result['status']}


def execute(db, job):
    report = db.get(models.BackgroundJob, job.payload['report_id'])
    row = next((deepcopy(r) for r in (report.result if report else {}).get('entries', [])
                if r['site_id'] == job.payload['site_id']), None)
    if not row or (row.get('recheck') or {}).get('id') != job.id:
        return {'status': 'superseded'}
    return finish(db, job, check(db, db.get(models.Site, job.payload['site_id']), row))


def recover(db, inflight_ids):
    """Read-only work can safely resume after a worker loss; never leave a row stuck."""
    if inflight_ids is None:
        return
    stale = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.kind == KIND, models.BackgroundJob.status == 'running',
        models.BackgroundJob.started_at < datetime.now(timezone.utc) - timedelta(minutes=10),
        models.BackgroundJob.id.not_in(inflight_ids),
    ).with_for_update(skip_locked=True)).all()
    for job in stale:
        job.status, job.dispatched_at = 'queued', None
    db.commit()

    failed = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.kind == KIND, models.BackgroundJob.status == 'failed',
        models.BackgroundJob.result['row_reconciled'].as_boolean().is_(None),
    ).limit(100)).all()
    for job in failed:
        try:
            finish(db, job, {'status': 'failed', 'error': 'Перепроверка прервана. Повторите обновление строки.'})
        except ValueError:
            db.rollback()  # The report may have been deleted in the meantime.
        job.result = {**(job.result or {}), 'row_reconciled': True}
        db.commit()
