import asyncio
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.db import SessionLocal
from app.services import collect_competitor_research_for_item, generate_content_item, generate_task_items, publish_campaign_bundle, publish_item, refresh_campaign_status, run_task_pipeline

settings = get_settings()

COMPETITOR_RESEARCH_MAX_ATTEMPTS = 3

celery_app = Celery("generator", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "publish-due-items-every-minute": {
        "task": "app.worker.publish_due_items",
        "schedule": 60.0,
    }
}


@celery_app.task(
    bind=True,
    max_retries=COMPETITOR_RESEARCH_MAX_ATTEMPTS - 1,
    name="app.worker.collect_competitor_research",
)
def collect_competitor_research_job(self, content_item_id: str) -> dict:
    db = SessionLocal()
    try:
        item = db.get(models.ContentItem, content_item_id)
        if not item:
            return {"status": "missing", "content_item_id": content_item_id}
        asyncio.run(collect_competitor_research_for_item(db, item))
        return {"status": "complete", "content_item_id": content_item_id}
    except Exception as exc:
        db.rollback()
        item = db.get(models.ContentItem, content_item_id)
        failed_attempt = self.request.retries + 1
        has_next_attempt = failed_attempt < COMPETITOR_RESEARCH_MAX_ATTEMPTS
        if item:
            item.competitor_research_status = "queued" if has_next_attempt else "research_failed"
            item.competitor_research_error = (
                f"Attempt {failed_attempt}/{COMPETITOR_RESEARCH_MAX_ATTEMPTS}: {type(exc).__name__}: {exc}"
            )[:500]
            db.commit()
        if has_next_attempt:
            raise self.retry(exc=exc, countdown=failed_attempt * 5)
        raise
    finally:
        db.close()


@celery_app.task(name="app.worker.generate_task_content")
def generate_task_content_job(task_id: str) -> dict:
    db = SessionLocal()
    try:
        task = db.get(models.GenerationTask, task_id)
        if not task:
            return {"status": "missing", "task_id": task_id}
        generate_task_items(db, task)
        return {"status": "complete", "task_id": task_id}
    finally:
        db.close()


@celery_app.task(name="app.worker.run_task_pipeline")
def run_task_pipeline_job(task_id: str) -> dict:
    db = SessionLocal()
    try:
        task = db.get(models.GenerationTask, task_id)
        if not task:
            return {"status": "missing", "task_id": task_id}
        run_task_pipeline(db, task)
        return {"status": "complete", "task_id": task_id}
    finally:
        db.close()


@celery_app.task(name="app.worker.generate_content_item")
def generate_content_item_job(content_item_id: str) -> dict:
    db = SessionLocal()
    try:
        item = db.get(models.ContentItem, content_item_id)
        if not item:
            return {"status": "missing", "content_item_id": content_item_id}
        generate_content_item(db, item)
        return {"status": "complete", "content_item_id": content_item_id}
    finally:
        db.close()


@celery_app.task(name="app.worker.publish_due_items")
def publish_due_items() -> dict:
    db = SessionLocal()
    published = 0
    try:
        items = db.scalars(
            select(models.ContentItem)
            .where(models.ContentItem.status.in_(["scheduled", "retry_scheduled"]))
            .where(models.ContentItem.scheduled_at <= datetime.now(timezone.utc))
            .order_by(models.ContentItem.scheduled_at.asc())
            .limit(10)
        ).all()
        for item in items:
            if item.publication_campaign_id:
                campaign = db.get(models.PublicationCampaign, item.publication_campaign_id)
                if not campaign or campaign.status != "active":
                    continue
            task = db.get(models.GenerationTask, item.task_id)
            site_id = item.site_id or (task.site_id if task else None)
            if not site_id:
                item.status = "publication_failed"
                db.add(
                    models.PublicationLog(
                        content_item_id=item.id,
                        endpoint_url="missing-site",
                        request_payload=item.generated_json,
                        error_message="Publication site is not configured",
                    )
                )
                refresh_campaign_status(db, item.publication_campaign_id)
                db.commit()
                continue
            site = db.get(models.Site, site_id)
            if not site or not site.is_active:
                item.status = "publication_failed"
                db.add(
                    models.PublicationLog(
                        content_item_id=item.id,
                        endpoint_url="missing-site",
                        request_payload=item.generated_json,
                        error_message="Publication site was not found or is inactive",
                    )
                )
                refresh_campaign_status(db, item.publication_campaign_id)
                db.commit()
                continue
            asyncio.run(publish_item(db, item, site))
            published += 1
        return {"processed": published}
    finally:
        db.close()


@celery_app.task(name="app.worker.publish_campaign_bundle")
def publish_campaign_bundle_job(campaign_id: str, log_id: str) -> dict:
    db = SessionLocal()
    try:
        asyncio.run(publish_campaign_bundle(db, campaign_id, log_id))
        campaign = db.get(models.PublicationCampaign, campaign_id)
        return {
            "status": campaign.status if campaign else "missing",
            "campaign_id": campaign_id,
            "log_id": log_id,
        }
    finally:
        db.close()
