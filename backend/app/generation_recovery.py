"""Explicit recovery of audited legacy generation states; never starts AI work."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app import models


def assert_generation_idle(celery_app, redis):
    """Fail closed on missing workers, broker uncertainty or pending deliveries."""
    inspect = celery_app.control.inspect(timeout=5)
    queues = inspect.active_queues()
    if not queues:
        raise RuntimeError("Workers did not answer; recovery stopped")
    workers = {name for name, entries in queues.items()
               if any(q["name"] in {"generation", "celery"} for q in entries)}
    if not workers:
        raise RuntimeError("Generation worker did not answer; recovery stopped")
    for kind in ("active", "reserved", "scheduled"):
        replies = getattr(inspect, kind)()
        if not replies or not workers.issubset(replies):
            raise RuntimeError("Incomplete worker snapshot; recovery stopped")
        if any(replies[name] for name in workers):
            raise RuntimeError("Generation worker has tasks; recovery stopped")
    # Include Redis priority queues, which have suffixes after the queue name.
    for prefix in ("generation", "celery"):
        for key in redis.scan_iter(match=prefix + "*"):
            if redis.type(key) in (b"list", "list") and redis.llen(key):
                raise RuntimeError("Pending broker deliveries; recovery stopped")
    if redis.hlen("unacked"):
        raise RuntimeError("Unacknowledged broker deliveries; recovery stopped")


def recover_legacy_generation(db, item_ids, *, before, verify_idle):
    """Only explicitly selected old rows; preserve their content and configuration."""
    if before.tzinfo is None or before > datetime.now(timezone.utc) - timedelta(days=7):
        raise ValueError("Recovery cutoff must be at least seven days old")
    verify_idle()
    items = db.scalars(select(models.ContentItem).where(
        models.ContentItem.id.in_(item_ids),
        models.ContentItem.status.in_(["generation_queued", "generating"]),
        models.ContentItem.updated_at < before,
    ).with_for_update()).all()
    verify_idle()
    result = []
    for item in items:
        result.append({"id": item.id, "task_id": item.task_id,
                       "previous_status": item.status, "previous_updated_at": str(item.updated_at)})
        item.status = "system_stopped"
        item.generation_error = (
            "Прерванная историческая генерация: выполнение отсутствует в очереди и у workers. "
            "Содержимое сохранено. Автоматический повтор не выполнялся; можно повторить вручную."
        )
    db.flush()
    for task_id in {item.task_id for item in items}:
        task = db.get(models.GenerationTask, task_id)
        statuses = db.scalars(select(models.ContentItem.status).where(
            models.ContentItem.task_id == task_id)).all()
        if task and task.status == "generating" and not any(
            status in {"generating", "generation_queued"} for status in statuses
        ):
            task.status = "system_stopped"
    db.commit()
    return result
