import asyncio
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.db import SessionLocal
from app.services import publish_item

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
            task = db.get(models.GenerationTask, item.task_id)
            site_id = item.site_id or (task.site_id if task else None)
            if not site_id:
                continue
            site = db.get(models.Site, site_id)
            if not site:
                continue
            asyncio.run(publish_item(db, item, site))
            published += 1
        return {"processed": published}
    finally:
        db.close()
