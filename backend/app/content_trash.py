"""Recoverable deletion of generated texts without losing drafts or revisions."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app import models


def trash_content(db, item):
    if item.status == "deleted":
        return
    if item.status in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "publication_pending_confirmation", "published", "deletion_pending", "generation_queued", "generating"}:
        raise ValueError("Дождитесь завершения операции. Опубликованные тексты удаляются через удаление с проекта.")
    item.generation_context = {**(item.generation_context or {}), "trash_source_status": item.status}
    item.status = "deleted"
    item.deletion_requested_at = datetime.now(timezone.utc)
    item.deletion_confirmed_at = item.deletion_requested_at
    item.deletion_error = None
    item.scheduled_at = None
    item.publication_campaign_id = None


def restore_content(db, item):
    from app.services import ensure_content_slug_available
    if item.status != "deleted":
        raise ValueError("Восстановить можно только удалённый текст. Дождитесь подтверждения удаления с проекта.")
    if item.site_id:
        db.execute(select(models.Site.id).where(models.Site.id == item.site_id).with_for_update())
    task = db.get(models.GenerationTask, item.task_id)
    if task and task.archived_at:
        raise ValueError("Сначала восстановите задачу из архива.")
    ensure_content_slug_available(db, item, apply_section_slug=False)
    section = db.get(models.Section, item.section_id) if item.section_id else None
    if not section or section.sync_status == "external_deleted":
        item.section_id = None
        item.section_content_mode = "nested"
    previous = (item.generation_context or {}).get("trash_source_status")
    item.status = "draft" if previous == "draft" or not item.generated_at else "generated"
    item.publication_campaign_id = None
    item.scheduled_at = None
    item.published_at = None
    item.published_url = None
    item.last_publication_status_code = None
    item.publication_author = None
    item.indexing_status = None
    item.indexing_task_id = None
    item.indexing_requested_at = None
    item.indexing_error = None
    item.deletion_requested_at = None
    item.deletion_confirmed_at = None
    item.deletion_error = None
    item.idempotency_key = f"restored-{item.id}-{uuid.uuid4().hex[:12]}"
    if task and task.status in {"empty", "published", "publication_failed"}:
        task.status = "generated" if item.generated_at else "created"
