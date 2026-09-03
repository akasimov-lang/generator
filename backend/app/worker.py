import asyncio
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.db import SessionLocal
from app.indexing import submit_pending_content_indexing
from app.project_cache import ProjectCacheError, fetch_project_cache, fetch_project_menu_capabilities, refresh_project_server_id, sync_project_data_update
from app.services import COMPETITOR_RESEARCH_MAX_ATTEMPTS, collect_competitor_research_for_item, continue_competitor_research_for_item, generate_content_item, publish_campaign_bundle, publish_item, refresh_campaign_status, revise_content_item, validate_content_for_publication

settings = get_settings()

celery_app = Celery("generator", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(
    timezone="UTC",
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)
celery_app.conf.beat_schedule = {
    "publish-due-items-every-minute": {
        "task": "app.worker.publish_due_items",
        "schedule": 60.0,
    },
    "submit-pending-content-indexing": {
        "task": "app.worker.submit_pending_content_indexing",
        "schedule": 5.0,
    },
}


@celery_app.task(name="app.worker.submit_pending_content_indexing")
def submit_pending_content_indexing_job() -> dict[str, int]:
    db = SessionLocal()
    try:
        return submit_pending_content_indexing(db)
    finally:
        db.close()


@celery_app.task(name="app.worker.check_site_menu_visibility")
def check_site_menu_visibility_job(check_id: str) -> dict:
    db = SessionLocal()
    try:
        check = db.get(models.MenuVisibilityCheck, check_id)
        if not check:
            return {"status": "missing", "check_id": check_id}
        if check.status not in {"queued", "running"}:
            return {"status": check.status, "check_id": check_id}
        check.status = "running"
        check.started_at = datetime.now(timezone.utc)
        check.error_code = None
        check.error_message = None
        db.commit()

        site = db.get(models.Site, check.site_id)
        if not site:
            raise ProjectCacheError("Project was not found", "PROJECT_NOT_FOUND")
        refresh_project_server_id(db, site)
        capabilities = fetch_project_menu_capabilities(site, force=True)
        projects = fetch_project_cache([site.name])
        project = next((item for item in projects if str(item.get("name") or "").strip() == site.name), None)
        if project is None:
            raise ProjectCacheError(f"Project '{site.name}' was not found in cache")
        sync_project_data_update(db, site.name, project)
        site.header_menu_template_rendered = capabilities["header_menu_template_rendered"]
        site.header_menu_rendered = capabilities["header_menu_rendered"]
        site.header_menu_nested = capabilities["header_menu_nested"]
        site.footer_menu_template_rendered = capabilities["footer_menu_template_rendered"]
        site.footer_menu_rendered = capabilities["footer_menu_rendered"]
        site.footer_menu_nested = capabilities["footer_menu_nested"]
        site.menu_capabilities_checked_at = datetime.now(timezone.utc)
        check.status = "completed"
        check.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "completed", "check_id": check_id, "site_id": site.id}
    except Exception as error:
        db.rollback()
        check = db.get(models.MenuVisibilityCheck, check_id)
        if check:
            check.status = "failed"
            check.error_code = getattr(error, "code", "TECHNICAL_ERROR")
            check.error_message = f"{type(error).__name__}: {error}"[:1000]
            check.finished_at = datetime.now(timezone.utc)
            db.commit()
        return {
            "status": "failed",
            "check_id": check_id,
            "error_code": getattr(error, "code", "TECHNICAL_ERROR"),
        }
    finally:
        db.close()


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
            retry_delay = min(15 * (2 ** (failed_attempt - 1)), 300)
            raise self.retry(exc=exc, countdown=retry_delay)
        raise
    finally:
        db.close()


@celery_app.task(name="app.worker.generate_task_content", acks_late=True, reject_on_worker_lost=True)
def generate_task_content_job(task_id: str) -> dict:
    db = SessionLocal()
    try:
        task = db.get(models.GenerationTask, task_id)
        if not task:
            return {"status": "missing", "task_id": task_id}
        item_ids = [
            item.id
            for item in task.items
            if item.status == "generation_queued" or (task.auto_publish and item.status == "generated")
        ]
        for item_id in item_ids:
            run_content_item_pipeline_job.delay(item_id, False)
        return {"status": "queued", "task_id": task_id, "items": len(item_ids)}
    finally:
        db.close()


@celery_app.task(name="app.worker.run_task_pipeline", acks_late=True, reject_on_worker_lost=True)
def run_task_pipeline_job(task_id: str) -> dict:
    db = SessionLocal()
    try:
        task = db.get(models.GenerationTask, task_id)
        if not task:
            return {"status": "missing", "task_id": task_id}
        item_ids = [
            item.id
            for item in task.items
            if item.status == "generation_queued" or (task.auto_publish and item.status == "generated")
        ]
        for item_id in item_ids:
            run_content_item_pipeline_job.delay(item_id, True)
        return {"status": "queued", "task_id": task_id, "items": len(item_ids)}
    finally:
        db.close()


def _refresh_parallel_task_status(db, task_id: str) -> None:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        return
    # Another worker can finish an item while this session still holds an older
    # relationship snapshot. Always calculate the aggregate from current rows.
    db.expire(task, ["items"])
    statuses = [item.status for item in task.items]
    if any(status in {"generation_queued", "generating"} for status in statuses):
        task.status = "generating"
    elif any(status == "generation_failed" for status in statuses):
        task.status = "generation_failed"
    elif task.auto_publish and any(status == "publication_failed" for status in statuses):
        task.status = "publication_failed"
    elif task.auto_publish and any(status in {"approved", "publishing", "publication_pending_confirmation"} for status in statuses):
        task.status = "publishing"
    elif task.auto_publish and statuses and all(status in {"published", "deleted"} for status in statuses):
        task.status = "published"
    else:
        task.status = "generated"
    db.commit()


@celery_app.task(bind=True, name="app.worker.run_content_item_pipeline", acks_late=True, reject_on_worker_lost=True)
def run_content_item_pipeline_job(self, content_item_id: str, collect_competitors: bool) -> dict:
    db = SessionLocal()
    try:
        item = db.scalar(
            select(models.ContentItem)
            .where(models.ContentItem.id == content_item_id)
            .with_for_update()
        )
        if not item:
            return {"status": "missing", "content_item_id": content_item_id}
        task_id = item.task_id
        task = db.get(models.GenerationTask, task_id)
        publish_generated = bool(task and task.auto_publish and item.status == "generated")
        redelivered = bool((self.request.delivery_info or {}).get("redelivered"))
        if item.status != "generation_queued" and not publish_generated and not (redelivered and item.status == "generating"):
            return {"status": "skipped", "content_item_id": content_item_id}
        if not publish_generated:
            item.status = "generating"
            item.generation_progress = max(1, item.generation_progress or 0)
            item.generation_error = None
            db.commit()

        if not publish_generated and collect_competitors and task and task.collect_competitors and not item.competitor_brief:
            research_error: Exception | None = None
            for attempt_index in range(COMPETITOR_RESEARCH_MAX_ATTEMPTS):
                try:
                    asyncio.run(continue_competitor_research_for_item(db, item))
                    research_error = None
                    break
                except Exception as error:
                    research_error = error
                    db.rollback()
                    item = db.get(models.ContentItem, content_item_id)
                    if not item:
                        break
                    has_next_attempt = attempt_index + 1 < COMPETITOR_RESEARCH_MAX_ATTEMPTS
                    item.competitor_research_status = "queued" if has_next_attempt else "research_failed"
                    item.competitor_research_error = (
                        f"Attempt {attempt_index + 1}/{COMPETITOR_RESEARCH_MAX_ATTEMPTS}: "
                        f"{type(error).__name__}: {error}"
                    )[:500]
                    db.commit()
            if research_error is not None:
                item = db.get(models.ContentItem, content_item_id)
                if item:
                    item.status = "generation_failed"
                    item.generation_error = f"Не удалось собрать конкурентов: {type(research_error).__name__}: {research_error}"[:500]
                    db.commit()
                _refresh_parallel_task_status(db, task_id)
                return {"status": "failed", "content_item_id": content_item_id}

        item = db.get(models.ContentItem, content_item_id)
        if not item:
            return {"status": "missing", "content_item_id": content_item_id}
        if not publish_generated:
            generate_content_item(db, item)
        task = db.get(models.GenerationTask, task_id)
        if task and task.auto_publish:
            site = db.get(models.Site, item.site_id or task.site_id) if (item.site_id or task.site_id) else None
            if not site:
                raise ValueError("Automatic publication requires a project")
            validate_content_for_publication(item)
            item.status = "approved"
            db.commit()
            asyncio.run(publish_item(db, item, site, initiator_username="automatic-menu-generation"))
        _refresh_parallel_task_status(db, task_id)
        return {"status": "complete", "content_item_id": content_item_id}
    except Exception as error:
        db.rollback()
        item = db.get(models.ContentItem, content_item_id)
        if item:
            task = db.get(models.GenerationTask, item.task_id)
            automatic_publication_failed = bool(task and task.auto_publish and item.status in {"generated", "approved"})
            if item.status not in {"publication_failed", "publication_pending_confirmation", "published"}:
                item.status = "publication_failed" if automatic_publication_failed else "generation_failed"
            error_prefix = "Автопубликация" if automatic_publication_failed else type(error).__name__
            item.generation_error = f"{error_prefix}: {error}"[:500]
            db.commit()
            _refresh_parallel_task_status(db, item.task_id)
        raise
    finally:
        db.close()


@celery_app.task(name="app.worker.generate_content_item", acks_late=True, reject_on_worker_lost=True)
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


@celery_app.task(name="app.worker.revise_content_item", acks_late=True, reject_on_worker_lost=True)
def revise_content_item_job(content_item_id: str, revision_id: str) -> dict:
    db = SessionLocal()
    try:
        item = db.get(models.ContentItem, content_item_id)
        revision = db.get(models.ContentRevision, revision_id)
        if not item or not revision or revision.content_item_id != content_item_id:
            return {"status": "missing", "content_item_id": content_item_id}
        try:
            revise_content_item(db, item, revision)
        except Exception as exc:
            db.rollback()
            failed_item = db.get(models.ContentItem, content_item_id)
            failed_revision = db.get(models.ContentRevision, revision_id)
            error_message = f"{type(exc).__name__}: {exc}"[:500]
            if failed_item and failed_revision:
                failed_item.generated_json = failed_revision.source_json
                failed_item.status = "generation_failed"
                failed_item.generation_error = error_message
                failed_revision.status = "failed"
                failed_revision.error_message = error_message
                task = db.get(models.GenerationTask, failed_item.task_id)
                if task:
                    task.status = "generation_failed"
                db.commit()
            raise
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
            .join(models.GenerationTask, models.GenerationTask.id == models.ContentItem.task_id)
            .where(models.GenerationTask.archived_at.is_(None))
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
