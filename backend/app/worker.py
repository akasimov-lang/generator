import asyncio
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.db import SessionLocal
from app.services import publish_item, refresh_campaign_status

settings = get_settings()

celery_app = Celery("generator", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "publish-due-items-every-minute": {
        "task": "app.worker.publish_due_items",
        "schedule": 60.0,
    }
}


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
