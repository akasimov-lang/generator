"""Immediate, durable delivery of independent network edits; one head per site."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app import models
from app.job_queues import NETWORK_CHANGE_KINDS

log = logging.getLogger(__name__)
TERMINAL = ('completed', 'failed', 'cancelled')


def head_ids():
    # Limit before dispatch, not inside the worker: one large site's queue must
    # not occupy all 30 slots while the rest wait. Existing project locks still
    # protect against old/duplicate broker deliveries and interactive edits.
    job = models.BackgroundJob
    site = job.payload['site_id'].as_string()
    # Existing queue executors use their own sequence. Preserve it even if
    # timestamps coincide or clocks move backwards, then merge the queue heads.
    per_kind = select(job.id, site.label('site_id'), job.created_at,
        func.row_number().over(
            partition_by=(site, job.kind),
            order_by=(job.payload['sequence'].as_integer(), job.created_at, job.id),
        ).label('position')).where(
        models.BackgroundJob.kind.in_(NETWORK_CHANGE_KINDS),
        models.BackgroundJob.status.not_in(TERMINAL),
    ).subquery()
    ranked = select(per_kind.c.id, func.row_number().over(
        partition_by=per_kind.c.site_id,
        order_by=(per_kind.c.created_at, per_kind.c.id),
    ).label('position')).where(per_kind.c.position == 1).subquery()
    return select(ranked.c.id).where(ranked.c.position == 1)


def dispatch_ready(db, send, site_id):
    now = datetime.now(timezone.utc)
    jobs = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.id.in_(head_ids()),
        models.BackgroundJob.status == 'queued',
        models.BackgroundJob.payload['site_id'].as_string() == site_id,
        or_(models.BackgroundJob.dispatched_at.is_(None),
            models.BackgroundJob.dispatched_at < now - timedelta(minutes=1)),
    ).with_for_update(skip_locked=True)).all()
    sent = 0
    for job in jobs:
        try:
            send(job.id)
        except Exception:
            log.warning('Immediate network dispatch unavailable; durable job retained', exc_info=True)
            continue
        job.dispatched_at = now
        sent += 1
    db.commit()
    return sent


def kick(site_id):
    """Run after the HTTP response / completed job, with periodic recovery."""
    from app.db import SessionLocal
    from app.worker import celery_app, background_operation_job
    try:
        # Never wait through Celery's normal publisher retries in an API task.
        with celery_app.connection_for_write(connect_timeout=2, transport_options={
            'socket_connect_timeout': 2, 'socket_timeout': 2,
        }) as connection, SessionLocal() as db:
            return dispatch_ready(db, lambda job_id: background_operation_job.apply_async(
                args=[job_id], queue='network_changes', task_id=job_id,
                connection=connection, retry=False,
            ), site_id)
    except Exception:
        log.warning('Network dispatch deferred to durable recovery', exc_info=True)
        return 0
