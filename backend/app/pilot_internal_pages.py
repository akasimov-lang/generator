"""Durable menu/content branch of an Auto Pilot run, independent of domain moves."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

from pydantic import Field
from sqlalchemy import or_, select

from app import models
from app.project_network import NetworkConflict, Remote, network_lock
from app.schemas import MenuStructurePreviewRequest
from app.pilot_scope import country_key

KIND = "pilot_internal_pages"
TERMINAL = {"completed", "failed", "partial", "skipped", "cancelled"}
FAILED_ITEMS = {"generation_failed", "publication_failed", "system_stopped", "deleted", "deletion_pending"}


class InternalMenuPreviewRequest(MenuStructurePreviewRequest):
    # The mass-action program deliberately uses a smaller 3–6 item menu.
    top_level_count: int = Field(ge=3, le=6)


def identifier(parent_id, site_id):
    return str(uuid5(UUID(parent_id), "internal-pages:" + site_id))


def enqueue(db, parent, user):
    """Commit alongside the parent launch; never enqueue during preview."""
    if parent.kind != "mass_reglue_list":
        return
    for group in (parent.result or {}).get("groups", []):
        for plan in group.get("plans", []):
            options = plan.get("internal_pages")
            if not options or options.get("enabled") is not True:
                continue
            count = options.get("count")
            if not isinstance(count, int) or isinstance(count, bool) or not 3 <= count <= 6:
                raise ValueError("Для внутренних страниц нужно от 3 до 6 пунктов меню.")
            job_id = identifier(parent.id, plan["site_id"])
            if db.get(models.BackgroundJob, job_id):
                continue
            db.add(models.BackgroundJob(id=job_id, kind=KIND, status="queued", payload={
                "parent_job_id": parent.id, "site_id": plan["site_id"],
                "actor": user["username"], "actor_id": user.get("id"),
                "allowed": sorted(user["allowed_site_ids"]) if user.get("allowed_site_ids") is not None else None,
                "plan": deepcopy(options),
            }, result={"phase": "planned", "count": count}))


def _task(db, job):
    task_id = (job.result or {}).get("task_id")
    if task_id:
        return db.get(models.GenerationTask, task_id)
    # create_menu_structure_task commits internally. Recover that commit even
    # if a worker exits before it records task_id on the durable branch job.
    return db.scalar(select(models.GenerationTask).where(
        models.GenerationTask.site_id == job.payload["site_id"],
        models.GenerationTask.prompt_template_name == "Auto Pilot inner pages: " + job.id,
        models.GenerationTask.generation_mode == "menu_structure",
    ))


def _latest(values):
    return max((value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
                for value in values if value), default=None)


def matches_owned_page_additions(db, parent_id, site_id, expected, actual):
    """Only confirmed pages from THIS launch may extend a captured network guard."""
    if not parent_id or not expected or not actual:
        return False
    if {k: v for k, v in expected.items() if k != 'content_page_paths'} != {
            k: v for k, v in actual.items() if k != 'content_page_paths'}:
        return False
    before, after = set(expected.get('content_page_paths') or []), set(actual.get('content_page_paths') or [])
    if not before <= after or not after - before:
        return False
    parent = db.get(models.BackgroundJob, parent_id)
    if not parent or parent.kind != 'mass_reglue_list':
        return False
    branch = db.get(models.BackgroundJob, identifier(parent_id, site_id))
    if not branch or branch.payload.get('parent_job_id') != parent_id or branch.payload.get('site_id') != site_id:
        return False
    task = _task(db, branch)
    if not task or task.archived_at or task.site_id != site_id:
        return False
    normalize = lambda value: '/' + str(value or '').strip('/') + '/'
    owned = {normalize(item.slug) for item in task.items if item.status == 'published' and item.published_at
             and (item.site_id is None or item.site_id == site_id)}
    return {normalize(path) for path in after - before} <= owned


def snapshot(db, parent_id, site_id, plan=None):
    job = db.get(models.BackgroundJob, identifier(parent_id, site_id))
    if not job:
        return {**deepcopy(plan), "status": "planned", "progress": 0} if plan and plan.get("enabled") is True else None
    result = job.result or {}
    output = {"count": result.get("count", job.payload["plan"]["count"]),
              "menu": result.get("menu", []), "status": job.status,
              "reason": job.error, "progress": result.get("progress", 0),
              "generated": 0, "published": 0, "failed": 0}
    task = _task(db, job)
    if task:
        items = task.items
        output.update(task_id=task.id,
                      generated=sum(bool(item.generated_at) for item in items),
                      published=sum(item.status == "published" and bool(item.published_at) for item in items),
                      failed=sum(item.status in FAILED_ITEMS for item in items))
        if task.archived_at:
            output.update(status="cancelled", reason="Задание генерации удалено. Повтор автоматически не запускается.")
        elif items and output["published"] == len(items):
            output.update(status="completed", progress=100)
        elif items and all(item.status in FAILED_ITEMS or item.status == "published" for item in items):
            output.update(status="partial" if output["published"] else "failed", progress=100,
                          reason="Не все внутренние страницы опубликованы. Подробности — в задании генерации.")
        elif job.status not in TERMINAL:
            publishing = any(item.status in {"publishing", "publication_pending_confirmation", "published"} for item in items)
            progress = 25 + round(60 * sum(min(100, item.generation_progress or 0) for item in items) / max(1, len(items)) / 100)
            output.update(status="publishing" if publishing else "generating",
                          progress=min(99, progress + round(15 * output["published"] / max(1, len(items)))))
            if not task.auto_publish and any(item.status == "generated" for item in items) and not any(item.status in {"draft", "generation_queued", "generating"} for item in items):
                output.update(status="waiting_reglue", reason="Тексты подготовлены. Публикация начнётся после завершения переклея и связанных переносов доменов.")
        output["updated_at"] = _latest([job.updated_at, task.updated_at, *(item.updated_at for item in items)])
        output["finished_at"] = _latest([job.finished_at, *(item.published_at or item.updated_at for item in items)]) if output["status"] in TERMINAL else None
    elif job.status == "queued":
        output["status"] = "running" if job.started_at else "queued"
    output.setdefault("updated_at", job.updated_at)
    output.setdefault("finished_at", job.finished_at)
    return output


def plan_options(parent):
    return {plan["site_id"]: plan["internal_pages"]
            for group in (parent.result or {}).get("groups", []) for plan in group.get("plans", [])
            if (plan.get("internal_pages") or {}).get("enabled") is True}


def report_metadata(db, parent):
    """No extra DB reads for old plans or a zero-percent selection."""
    metadata = {"status": parent.status, "finished_at": parent.finished_at, "updated_at": parent.updated_at}
    if not plan_options(parent):
        return metadata
    jobs = db.scalars(select(models.BackgroundJob).where(
        models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload["parent_job_id"].as_string() == parent.id,
    )).all()
    states = [snapshot(db, parent.id, job.payload["site_id"]) for job in jobs]
    statuses = [state["status"] for state in states]
    if any(status not in TERMINAL for status in statuses):
        metadata["status"] = "running"
    elif parent.status == "completed" and any(status != "completed" for status in statuses):
        metadata["status"] = "partial"
    elif parent.status in TERMINAL and parent.status != "completed" and "completed" in statuses:
        metadata["status"] = "partial"
    metadata["finished_at"] = _latest([parent.finished_at, *(state.get("finished_at") for state in states)]) if metadata["status"] in TERMINAL else None
    metadata["updated_at"] = _latest([parent.updated_at, *(state.get("updated_at") for state in states)])
    return metadata


def report_status(db, parent):
    return report_metadata(db, parent)["status"]


def merge_row(row, state):
    """Preserve the domain-move outcome while showing the whole project workflow."""
    if not state or state.get("status") == "planned":
        return
    original = row.get("reglue_status", row["status"])
    row["reglue_status"] = original
    original_progress = row.get("reglue_progress", row.get("progress", 100 if original in TERMINAL else 0))
    row["reglue_progress"] = original_progress
    row["internal_pages"] = state
    content_done = state["status"] in TERMINAL
    row["progress"] = round((original_progress + (100 if content_done else state.get("progress", 0))) / 2)
    if not content_done:
        row["status"] = "running"
        if original in TERMINAL:
            row["reglue_phase"] = row.get("reglue_phase", row.get("phase"))
            row["phase"] = "internal_pages"
    elif original in TERMINAL:
        if original == state["status"] == "completed":
            row["status"] = "completed"
        elif original == "completed" or state["status"] == "completed" or state.get("published", 0):
            row["status"] = "partial"
        elif original == "failed" or state["status"] == "failed":
            row["status"] = "failed"


def _project(db, site):
    with Remote(db, site) as remote:
        return remote.project()


def _require_scope(site, job):
    before = job.payload["plan"].get("eligibility") or {}
    from app.mass_action_scope import brand_key
    from app.pilot_scope import country_key
    if ((before.get("brand") is not None and brand_key(before["brand"]) != brand_key(site.brand))
            or (before.get("geo") is not None and country_key(before["geo"]) != country_key(site.cache_geo))
            or (before.get("language") is not None and before["language"].casefold().replace("_", "-") != str(site.cache_language).casefold().replace("_", "-"))):
        raise ValueError("Бренд, GEO или язык проекта изменились после планирования внутренних страниц.")


def publication_ready(db, parent, site_id):
    """New page paths must not invalidate any in-flight source/target guard."""
    participant = or_(models.AutoReglueRun.site_id == site_id,
                      models.AutoReglueRun.plan["source_site_id"].as_string() == site_id)
    active = db.scalar(select(models.AutoReglueRun.id).where(
        participant, models.AutoReglueRun.status.not_in(["completed", "failed", "cancelled"]),
    ).limit(1))
    pending = db.scalar(select(models.NetworkOperation.id).join(models.AutoReglueRun,
        models.NetworkOperation.request_payload["auto_run_id"].as_string() == models.AutoReglueRun.id,
    ).where(participant, models.NetworkOperation.status.in_(["pending", "unknown"])).limit(1))
    if active or pending:
        return False
    for group in (parent.result or {}).get("groups", []):
        for plan in group.get("plans", []):
            if site_id not in {plan["site_id"], plan.get("source_site_id", plan["site_id"])}:
                continue
            row = (parent.result or {}).get("items", {}).get(plan["site_id"], {})
            run_id = row.get("run_id") or str(uuid5(UUID(parent.id), plan["site_id"]))
            run = db.get(models.AutoReglueRun, run_id)
            if run:
                # Partial/waiting runs may continue and still use their saved guards.
                if run.status not in {"completed", "failed", "cancelled"}:
                    return False
                pending = db.scalar(select(models.NetworkOperation.id).where(
                    models.NetworkOperation.status.in_(["pending", "unknown"]),
                    models.NetworkOperation.request_payload["auto_run_id"].as_string() == run.id,
                ).limit(1))
                if pending:
                    return False
            elif row.get("status") not in {"failed", "cancelled", "skipped"} and not (
                    group.get("status") == "done" or parent.status in {"completed", "failed", "cancelled"}):
                return False
    return True


def publication_job_ready(db, publication):
    owner_id = publication.payload.get("pilot_internal_pages_job_id")
    if not owner_id:
        return True
    owner = db.get(models.BackgroundJob, owner_id)
    parent = db.get(models.BackgroundJob, owner.payload["parent_job_id"]) if owner else None
    return bool(parent and publication_ready(db, parent, owner.payload["site_id"]))


def _menu_confirmed(project, expected):
    from app.project_cache import _project_menu
    actual = _project_menu(project)["header"]
    def path(value):
        return "/" + str(value or "").strip("/") + "/"
    return all(sum(isinstance(row, dict) and path(row.get("slug")) == path(item["slug"])
                   and row.get("title") == item["title"] and not row.get("children")
                   for row in actual) == 1 for item in expected)


def _owned_sections(db, site, menu, expected):
    """Adopt only the confirmed branch paths, including recovery after a timeout."""
    wanted = {row["slug"] for row in expected}
    ids = []
    for row in menu["header"]:
        if row.get("slug") not in wanted:
            continue
        section = db.scalar(select(models.Section).where(
            models.Section.site_id == site.id, models.Section.menu_type == "header",
            models.Section.path == row["slug"],
        ))
        if not section:
            section = models.Section(site_id=site.id, path=row["slug"], menu_type="header")
            db.add(section)
        section.name = row["title"]
        section.external_id = str(row.get("id") or "pilot-" + row["slug"].strip("/"))
        section.parent_id = None
        section.is_temporary_parent = False
        section.sync_status = "synced"
        section.synced_at = datetime.now(timezone.utc)
        db.flush()
        ids.append(section.id)
    if len(ids) != len(wanted):
        raise ValueError("Не удалось подтвердить все пункты меню для генерации.")
    return ids


def execute_step(db, job_id, send):
    """Resume the same menu and task; uncertain remote writes are never repeated."""
    with network_lock(db, "pilot-internal-pages:" + job_id):
        job = db.get(models.BackgroundJob, job_id)
        if not job or job.kind != KIND or job.status != "queued":
            return {"status": "skipped"}
        job.started_at = job.started_at or datetime.now(timezone.utc)
        db.commit()
        try:
            site = db.get(models.Site, job.payload["site_id"])
            parent = db.get(models.BackgroundJob, job.payload["parent_job_id"])
            allowed = job.payload.get("allowed")
            if not site or not site.is_active or not parent or parent.kind != "mass_reglue_list" or (allowed is not None and site.id not in allowed):
                raise ValueError("Проект или запущенный план больше недоступен.")
            _require_scope(site, job)
            task = _task(db, job)
            if (job.result or {}).get("task_id") and not task:
                raise ValueError("Задание генерации удалено. Новое задание автоматически не создаётся.")
            if not task:
                from app.pilot_internal_pages_policy import require_eligible
                from app.project_cache import _project_menu
                from app import services
                from app.schemas import MenuStructureGenerationCreate

                project = _project(db, site)
                require_eligible(db, site, project)
                result = dict(job.result or {})
                if not result.get("menu"):
                    provider = db.scalar(select(models.AiProvider).where(
                        models.AiProvider.provider_type == "gemini", models.AiProvider.is_active.is_(True),
                    ).order_by(models.AiProvider.created_at.desc()).limit(1))
                    if not provider:
                        raise ValueError("Для генерации внутренних страниц нужен активный Gemini provider.")
                    site.default_menu = _project_menu(project)
                    result.update(phase="generating_menu", progress=5)
                    job.result = result; db.commit()
                    preview = asyncio.run(services.generate_menu_structure_preview(db, provider, site,
                        InternalMenuPreviewRequest(menu_type="header", levels=1, top_level_count=result["count"], mode="thematic")))
                    menu = preview["items"]
                    if (len(menu) != result["count"] or any(item.get("children") or not item.get("slug") for item in menu)
                            or len({item["slug"] for item in menu}) != len(menu)):
                        raise ValueError("Сгенерированное меню не соответствует плану: нужны 3–6 пунктов одного уровня.")
                    result.update(menu=menu, provider_id=provider.id, phase="menu_ready", progress=10)
                    job.result = result; db.commit()
                # A crash after Webdev accepted the menu must recover it, not append it again.
                with network_lock(db, site.id):
                    db.refresh(site)
                    _require_scope(site, job)
                    project = _project(db, site)
                    require_eligible(db, site, project)
                    confirmed = _menu_confirmed(project, result["menu"])
                    if result.get("phase") == "applying_menu" and not confirmed:
                        raise ValueError("Сохранение меню не подтверждено. Проверьте меню проекта перед повтором; дубликат не отправлен.")
                    if not confirmed:
                        site.default_menu = _project_menu(project)
                        result.update(phase="applying_menu", progress=15)
                        job.result = result; db.commit()
                        applied = asyncio.run(services.apply_generated_menu_structure(
                            db, site, "header", 1, result["count"], "thematic", result["menu"],
                            initiator_username=job.payload["actor"]))
                        if not applied.get("success") or applied.get("rolled_back"):
                            raise ValueError("Меню не сохранено. Генерация внутренних страниц не запущена.")
                        project = _project(db, site)
                        if not _menu_confirmed(project, result["menu"]):
                            raise ValueError("Webdev не подтвердил сохранённые пункты меню.")
                    site.default_menu = _project_menu(project)
                    result.update(phase="menu_confirmed", progress=20)
                    job.result = result; db.commit()
                    section_ids = _owned_sections(db, site, site.default_menu, result["menu"])
                    task = services.create_menu_structure_task(db, site, MenuStructureGenerationCreate(
                        geo=country_key(site.cache_geo), language=site.cache_language,
                        ai_provider_id=result["provider_id"], menu_types=["header"], section_ids=section_ids,
                        prompt_template_name="Auto Pilot inner pages: " + job.id,
                        # Generation runs immediately. Enable auto-publication only
                        # after every source/target guard using this site is finished.
                        collect_competitors=True, homepage_interlinking=True, auto_publish=False,
                    ), created_by_user_id=job.payload.get("actor_id"))
                    result.update(task_id=task.id, phase="generation", progress=25)
                    job.result = result; db.commit()
            elif (job.result or {}).get("task_id") != task.id:
                job.result = {**(job.result or {}), "task_id": task.id}
                db.commit()
            if task.archived_at:
                job.status = "cancelled"
                job.error = "Задание генерации удалено. Повтор автоматически не запускается."
            else:
                expected = {row["slug"] for row in (job.result or {}).get("menu", [])}
                if task.site_id != site.id or {item.slug for item in task.items} != expected:
                    raise ValueError("Состав задания внутренних страниц не совпадает с сохранённым планом.")
                for item in task.items:
                    if (item.generation_context or {}).get("pilot_internal_pages_job_id") != job.id:
                        item.generation_context = {**(item.generation_context or {}), "pilot_internal_pages_job_id": job.id}
                db.commit()
                if not task.auto_publish and publication_ready(db, parent, site.id):
                    task.auto_publish = True
                    job.result = {**job.result, "phase": "publication_enabled"}
                    # Publish already-generated items through the existing idempotent pipeline.
                    job.result.pop("pipeline_sent_at", None)
                    db.commit()
                draft_items = [item for item in task.items if item.status == "draft"]
                for item in draft_items:
                    item.status = "generation_queued"
                    item.generation_progress = 1
                    item.generation_error = None
                if draft_items:
                    task.status = "generating"
                    db.commit()
                state = snapshot(db, parent.id, site.id)
                if state["status"] in TERMINAL:
                    job.status = state["status"]
                    job.error = state.get("reason")
                else:
                    last_sent = (job.result or {}).get("pipeline_sent_at")
                    due = not last_sent or datetime.fromisoformat(last_sent) < datetime.now(timezone.utc) - timedelta(minutes=1)
                    if due and any(item.status == "generation_queued" or (task.auto_publish and item.status == "generated") for item in task.items):
                        try:
                            send(task.id)
                        except Exception:
                            job.error = "Очередь временно недоступна. Отправка будет повторена."
                        else:
                            job.result = {**job.result, "pipeline_sent_at": datetime.now(timezone.utc).isoformat()}
                            job.error = None
            if job.status in TERMINAL:
                job.finished_at = datetime.now(timezone.utc)
            else:
                job.dispatched_at = None
            db.commit()
            return {"status": job.status}
        except NetworkConflict as error:
            db.rollback()
            job = db.get(models.BackgroundJob, job_id)
            job.error = str(error)[:1000]
            job.dispatched_at = None
            db.commit()
            return {"status": "waiting"}
        except Exception as error:
            db.rollback()
            job = db.get(models.BackgroundJob, job_id)
            job.status = "failed"
            job.error = str(error)[:1000]
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed"}
