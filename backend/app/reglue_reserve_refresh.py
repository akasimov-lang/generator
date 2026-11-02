"""Explicit, resumable read-only Webdev refresh for reserve membership."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from app import models, reglue_reserves as pool
from app.project_network import network_lock

KIND = 'reserve_membership_refresh'
TERMINAL = {'completed', 'partial', 'failed'}


def view(job):
    result = job.result or {}
    total = len(result.get('site_ids', []))
    done = len(result.get('checked', []))
    return {'id': job.id, 'status': job.status,
            'progress': {'done': done, 'total': total,
                         'percent': round(done * 100 / total) if total else (100 if job.status in TERMINAL else 0)},
            'issues': result.get('issues', []), 'error': job.error,
            'started_at': job.started_at, 'finished_at': job.finished_at}


def authorized(db, job_id, user):
    job = db.get(models.BackgroundJob, str(job_id))
    if not job or job.kind != KIND:
        raise HTTPException(404, 'Обновление резерва не найдено.')
    if job.payload.get('actor') != user['username']:
        raise HTTPException(403, 'Нет доступа к этому обновлению.')
    allowed = user.get('allowed_site_ids')
    if allowed is not None and not set(job.payload.get('site_ids', [])).issubset(set(allowed)):
        raise HTTPException(403, 'Доступ к проектам изменился.')
    return job


def request(db, request_id, user):
    job_id = str(UUID(str(request_id)))
    with network_lock(db, 'reserve-refresh:' + user['username']):
        existing = db.get(models.BackgroundJob, job_id)
        if existing:
            return authorized(db, job_id, user)
        # A second click or another tab joins the same in-flight refresh.
        jobs = db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
            models.BackgroundJob.status.in_(['queued', 'running'])).order_by(models.BackgroundJob.created_at.desc()))
        for job in jobs:
            if job.payload.get('actor') == user['username']:
                return authorized(db, job.id, user)
        allowed = user.get('allowed_site_ids')
        sites = list(db.scalars(select(models.Site).where(models.Site.is_active.is_(True)).order_by(models.Site.id)))
        ids = [site.id for site in sites if allowed is None or site.id in allowed]
        job = models.BackgroundJob(id=job_id, kind=KIND, payload={'actor': user['username'], 'site_ids': ids},
                                   result={'checked': [], 'issues': []})
        db.add(job); db.commit()
        return job


def latest(db, user):
    jobs = db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND)
        .order_by(models.BackgroundJob.created_at.desc()).limit(100))
    for job in jobs:
        if job.payload.get('actor') == user.get('username'):
            allowed = user.get('allowed_site_ids')
            if allowed is None or set(job.payload.get('site_ids', [])).issubset(set(allowed)):
                return view(job)
    return None


def discover(db, job):
    from app import project_cache
    from app.network_state import project_network_state
    sites = list(db.scalars(select(models.Site).where(models.Site.id.in_(job.payload['site_ids']), models.Site.is_active.is_(True))))
    stock = set(db.scalars(select(models.ReglueReserveDomain.domain)))
    candidates = {site.id for site in sites if pool.observed_domains(site, pool.cached_state(site)) & stock
                  or pool.domain_key(site.name) in stock}
    issues = []
    if stock and sites:
        try:
            snapshots = project_cache.fetch_project_cache([site.name for site in sites])
            by_name = {site.name: site for site in sites}
            for snapshot in snapshots:
                site = by_name.get(snapshot.get('name'))
                if site and pool.observed_domains(site, project_network_state(snapshot)) & stock:
                    candidates.add(site.id)
                    # Use this only for server discovery; membership below uses
                    # the freshly read native project, never a stale cache copy.
                    server = snapshot.get('serverId') or snapshot.get('server_id') or snapshot.get('serverIp') or snapshot.get('server_ip')
                    if server: site.cache_server_ip = str(server)
            db.commit()
        except Exception as error:
            db.rollback()
            issues.append({'project': None, 'error': 'Не удалось проверить общий список Webdev: ' + str(error)[:400]})
    return {'site_ids': sorted(candidates), 'checked': [], 'issues': issues}


def execute_step(db, job_id):
    from app import project_network, project_cache
    with network_lock(db, 'reserve-refresh-job:' + str(job_id)):
        job = db.get(models.BackgroundJob, str(job_id))
        if not job or job.kind != KIND or job.status in TERMINAL:
            return {'status': 'skipped'}
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc); db.commit()
        if 'site_ids' not in (job.result or {}):
            job.result = discover(db, job); db.commit()
        result = dict(job.result or {})
        checked = list(result.get('checked', [])); issues = list(result.get('issues', []))
        pending = [sid for sid in result['site_ids'] if sid not in checked]
        # One network per delivery keeps refreshes resumable without holding a
        # worker for a complete inventory. Repeated reads have no remote writes.
        if pending:
            site = db.get(models.Site, pending[0])
            try:
                if not site or not site.is_active:
                    raise ValueError('Проект больше не доступен.')
                with project_network.Remote(db, site) as remote:
                    snapshot = remote.project()
                project_cache._apply_direct_project_snapshot(db, site, snapshot)
            except Exception as error:
                db.rollback()
                issues.append({'project': site.name if site else None, 'error': str(error)[:500]})
            checked.append(pending[0])
        job = db.get(models.BackgroundJob, str(job_id))
        job.result = {**result, 'checked': checked, 'issues': issues}
        if len(checked) == len(result['site_ids']):
            job.status = 'partial' if issues else 'completed'
            job.finished_at = datetime.now(timezone.utc)
        else:
            job.status = 'queued'; job.dispatched_at = None
        db.commit()
        return view(job)
