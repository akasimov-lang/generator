"""Durable jobs: commit intent before dispatch, claim once before external I/O."""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, or_, case
from app import models
from app.task_status import refresh_task_status


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
        **({"pilot_internal_pages_job_id": item.generation_context["pilot_internal_pages_job_id"]}
           if (item.generation_context or {}).get("pilot_internal_pages_job_id") else {}),
    }))
    refresh_task_status(db, item.task_id)
    # The dispatcher recovers a broker failure after this commit.
    db.commit()


def dispatch_pending(db, send, inflight_ids=None):
    from app.menu_generation_jobs import expire, recover_interrupted
    from app.job_queues import queue_for
    expire(db)
    recover_interrupted(db)
    now = datetime.now(timezone.utc)
    jobs = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.status == "queued",
        models.BackgroundJob.id.not_in(inflight_ids or []),
        or_(models.BackgroundJob.dispatched_at.is_(None),
            models.BackgroundJob.dispatched_at < now - timedelta(minutes=1)),
    ).order_by(case((models.BackgroundJob.kind == 'auto_pilot_preview', 0), else_=1),
               models.BackgroundJob.created_at).limit(100).with_for_update(skip_locked=True)).all()
    sent = 0
    for job in jobs:
        if job.kind == 'generation_retry':
            from app.generation_retry import due
            from app.queue_maintenance import obsolete_retry
            if obsolete_retry(db, job):
                job.status = 'cancelled'; job.finished_at = now
                job.result = {**(job.result or {}), 'reason': 'Повтор не требуется: текст уже обработан или назначена новая попытка.'}
                continue
            if not due(job): continue
        try:
            send(job.id, queue_for(db, job))
        except Exception:
            continue
        job.dispatched_at = now
        sent += 1
    db.commit()
    return {"dispatched": sent}


def run_job(db, job_id):
    candidate = db.get(models.BackgroundJob, job_id)
    if candidate and candidate.kind == 'pilot_row_replan':
        from app.pilot_row_replan import execute
        return execute(db, job_id)
    if candidate and candidate.kind == 'pilot_content_publication':
        from app.pilot_content_publication import execute
        return execute(db, job_id)
    if candidate and candidate.kind == "menu_generation":
        from app.menu_generation_jobs import execute
        return execute(db, job_id)
    if candidate and candidate.kind == 'publication' and candidate.status == 'queued' and candidate.payload.get('pilot_internal_pages_job_id'):
        from app.pilot_internal_pages import publication_job_ready
        if not publication_job_ready(db, candidate):
            candidate.dispatched_at = None
            db.commit()
            return {'status': 'waiting_reglue'}
    if candidate and candidate.kind == 'pilot_internal_pages':
        from app.pilot_internal_pages import execute_step
        from app.worker import run_task_pipeline_job
        return execute_step(db, job_id, lambda task_id: run_task_pipeline_job.delay(task_id))
    if candidate and candidate.kind == 'pilot_text':
        from app.pilot_text_jobs import execute
        return execute(db, job_id)
    if candidate and candidate.kind == 'network_edit_queue':
        from app.network_edit_queue import execute_step
        return execute_step(db, job_id)
    if candidate and candidate.kind == 'fake_main_queue':
        from app.fake_main_queue import execute_step
        return execute_step(db, job_id)
    if candidate and candidate.kind == 'reserve_membership_refresh':
        from app.reglue_reserve_refresh import execute_step
        return execute_step(db, job_id)
    if candidate and candidate.kind == 'maintenance_report' and candidate.payload.get('repeat'):
        from app.maintenance_repeat import execute_step
        return execute_step(db, job_id)
    if candidate and candidate.kind in {'mass_reglue_list', 'auto_pilot_preview'}:
        from app.mass_reglue_launch import execute_step
        from app.worker import auto_reglue_job
        return execute_step(db, job_id, lambda run_id: auto_reglue_job.delay(run_id), parallel_texts=True)
    job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == job_id).with_for_update())
    if not job or job.status != "queued":
        db.rollback()
        return {"status": "skipped"}
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()  # Duplicated broker deliveries must never repeat remote mutations.
    try:
        if job.kind == 'generation_retry':
            from app.worker import run_content_item_pipeline_job
            result = run_content_item_pipeline_job.run(job.payload['content_id'], job.payload['collect_competitors'])
        elif job.kind == "article_image":
            from app.article_images import retry
            item = db.get(models.ContentItem, job.payload["content_id"])
            if not item:
                raise ValueError("Текст не найден.")
            result = asyncio.run(retry(db, item))
        elif job.kind == "template_knowledge":
            from app.competitor_site_structure import execute
            result = execute(db, job)
        elif job.kind == "transfer_report_check":
            from app.transfer_report_check import execute
            result = execute(db, job)
        elif job.kind == "page_autolink":
            from app.project_page_autolink import execute
            result = execute(db, job)
        elif job.kind == "auto_lb":
            from app.auto_lb import generate
            row = db.get(models.AutoLbGeneration, job.payload["generation_id"])
            if not row:
                raise ValueError("Генерация АвтоЛБ не найдена")
            result = asyncio.run(generate(db, row))
        elif job.kind == "project_page_ai":
            from app.page_content_tools import generate
            row = db.get(models.ProjectPageDraft, job.payload["draft_id"])
            if not row:
                raise ValueError("Черновик не найден")
            if job.payload.get('mass_filter'):
                from app.mass_action_scope import MassActionFilter, matches
                site = db.get(models.Site, row.site_id)
                if not site or not matches(site, MassActionFilter.model_validate(job.payload['mass_filter'])):
                    raise ValueError('Проект больше не соответствует фильтру массового действия. Обработка остановлена.')
            result = asyncio.run(generate(db, row))
        elif job.kind == "site_template":
            from app.site_templates import generate, audit_edited
            row = db.get(models.SiteTemplate, job.payload["template_id"])
            if not row:
                raise ValueError("Шаблон не найден")
            result = asyncio.run(audit_edited(db, row) if job.payload.get("audit") else
                                 generate(db, row, content_only=job.payload.get("stage") == "content",
                                          research_only=job.payload.get("stage") == "research"))
        elif job.kind == "cache_sync":
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
            refresh_task_status(db, item.task_id)
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
        if job.kind == "auto_lb":
            row = db.get(models.AutoLbGeneration, job.payload["generation_id"])
            if row:
                row.status = "failed"
                row.error = (str(error)[:500] if isinstance(error, ValueError) else
                             "Не удалось получить результат Gemini. Проверьте провайдер и повторите генерацию.")
        if job.kind == "project_page_ai":
            row = db.get(models.ProjectPageDraft, job.payload["draft_id"])
            if row:
                row.status = "failed"
                row.error = str(error)[:500] if isinstance(error, ValueError) else "Не удалось завершить обработку Gemini. Исходный контент сохранён."
        if job.kind == "site_template":
            row = db.get(models.SiteTemplate, job.payload["template_id"])
            if row:
                row.status, row.phase = "failed", "Нужна повторная попытка"
                row.error = (str(error)[:700] if isinstance(error, ValueError) else
                             "Не удалось завершить генерацию или визуальную проверку. Проверьте провайдер и повторите.")
        job.finished_at = datetime.now(timezone.utc)
        if job.kind == "publication":
            item = db.get(models.ContentItem, job.payload["content_id"])
            if item and item.status == "publishing":
                item.status = "publication_failed"
                item.generation_error = job.error
        db.commit()
        return {"status": "failed"}
