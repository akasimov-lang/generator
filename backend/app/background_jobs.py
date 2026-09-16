"""Durable jobs: commit intent before dispatch, claim once before external I/O."""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, or_
from app import models


def enqueue_publication(db, item, actor):
    from app.services import validate_content_for_publication
    item = db.scalar(select(models.ContentItem).where(models.ContentItem.id == item.id)
                     .with_for_update().execution_options(populate_existing=True))
    if item.status in {"publishing", "publication_pending_confirmation", "published"}:
        return
    validate_content_for_publication(item)
    previous_status = item.status
    item.status = "publishing"
    db.add(models.BackgroundJob(kind="publication", payload={
        "content_id": item.id, "actor": actor, "previous_status": previous_status,
    }))
    # The dispatcher recovers a broker failure after this commit.
    db.commit()


def dispatch_pending(db, send):
    now = datetime.now(timezone.utc)
    jobs = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.status == "queued",
        or_(models.BackgroundJob.dispatched_at.is_(None),
            models.BackgroundJob.dispatched_at < now - timedelta(minutes=1)),
    ).order_by(models.BackgroundJob.created_at).limit(100).with_for_update(skip_locked=True)).all()
    sent = 0
    for job in jobs:
        try:
            send(job.id, "publication" if job.kind == "publication" else "cache_sync")
        except Exception:
            continue
        job.dispatched_at = now
        sent += 1
    db.commit()
    return {"dispatched": sent}


def run_job(db, job_id):
    job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == job_id).with_for_update())
    if not job or job.status != "queued":
        db.rollback()
        return {"status": "skipped"}
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()  # Duplicated broker deliveries must never repeat remote mutations.
    try:
        if job.kind == "cache_sync":
            from app.project_cache import sync_project_cache, fetch_project_cache
            result = sync_project_cache(db, fetch_project_cache(job.payload.get("names") or None))
        elif job.kind == "publication":
            from app.project_cache import sync_project_cache, fetch_project_cache
            from app.services import publish_item, refresh_campaign_status
            item = db.get(models.ContentItem, job.payload["content_id"])
            if not item:
                raise ValueError("Content not found")
            site = db.get(models.Site, item.site_id)
            if not site:
                raise ValueError("Project not found")
            if job.payload.get("previous_status") == "publication_failed":
                # A previous timeout may have succeeded remotely: verify before sending again.
                sync_project_cache(db, fetch_project_cache([site.name]))
                db.refresh(item)
            if item.status not in {"published", "publication_pending_confirmation"}:
                item.status = "approved"
                asyncio.run(publish_item(db, item, site, initiator_username=job.payload.get("actor")))
            if item.status == "published":
                item.scheduled_at = None
            refresh_campaign_status(db, item.publication_campaign_id)
            result = {"content_id": item.id, "status": item.status}
            if item.status == "publication_failed":
                raise ValueError(item.generation_error or "Publication failed; see project history")
        else:
            raise ValueError("Unknown background operation")
        job = db.get(models.BackgroundJob, job_id)
        job.status = "completed"
        job.result = result
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "completed"}
    except Exception as error:
        db.rollback()
        job = db.get(models.BackgroundJob, job_id)
        job.status = "failed"
        job.error = f"{type(error).__name__}: {error}"[:1000]
        job.finished_at = datetime.now(timezone.utc)
        if job.kind == "publication":
            item = db.get(models.ContentItem, job.payload["content_id"])
            if item and item.status == "publishing":
                item.status = "publication_failed"
                item.generation_error = job.error
        db.commit()
        return {"status": "failed"}
