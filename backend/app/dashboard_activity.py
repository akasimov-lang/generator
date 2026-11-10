"""Live dashboard from durable receipts and jobs. Reading never dispatches work."""
from collections import Counter
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app import models
from app.db import get_db
from app.reglue_history import utc
from app.reglue_journal import confirmed_at, path_change
from app.network_state import domain_name
from app.security import AuthUser

router = APIRouter(prefix="/dashboard-activity", tags=["dashboard"])
TERMINAL = {"completed", "failed", "partial", "cancelled", "skipped"}
PHASES = {
    "prepared": (5, "Подготовка"), "delete_domain": (15, "Перенос доменов"),
    "create_domains": (30, "Добавление доменов"), "create_subdomains": (35, "Создание поддоменов"),
    "subdomain_ready": (40, "Проверка поддоменов"), "create_fake_main": (45, "Замена внутренней страницы"),
    "fake_main_ready": (55, "Проверка внутренней страницы"), "reserve": (60, "Назначение резерва"),
    "reglue": (75, "Смена Main"), "alternates": (90, "Обновление alternate"),
    "title_h1": (95, "Публикация Title/H1"), "paragraphs": (97, "Публикация текста"),
    "internal_pages": (0, "Генерация и публикация внутренних страниц"),
}
STATUSES = {"completed": "Завершено", "failed": "Ошибка", "partial": "Завершено частично",
            "cancelled": "Отменено", "skipped": "Пропущено", "ready": "План готов"}


def stage(phase, status):
    return STATUSES.get(status) or PHASES.get((phase or "").removeprefix("cross_"), (0, "Подготовка"))[1]


def percent(phase, status):
    return 100 if status in TERMINAL else PHASES.get((phase or "").removeprefix("cross_"), (0, ""))[0]


def base(key, kind, at, title, **fields):
    return {"id": key, "kind": kind, "at": utc(at).isoformat(), "title": title,
            "active": False, "status": "completed", **fields}


def project_fields(site):
    return {"project": site.name, "project_url": f"/project-network/{quote(site.name, safe='')}/"}


def legacy_allowed(value, runs, allowed):
    ids = {item.get("site_id") for item in value.get("results", []) + value.get("skipped", [])}
    for item in value.get("results", []):
        ids.add(item.get("source_site_id") or item.get("site_id"))
        run = runs.get(item.get("run_id"))
        if run:
            ids.add((run.plan or {}).get("source_site_id") or run.site_id)
    return allowed is None or ids.issubset(allowed)


def legacy_row(value, runs, updated_at):
    entries = [{**item, **({"status": runs[item["run_id"]].status, "phase": runs[item["run_id"]].phase}
                          if item.get("run_id") in runs else {})} for item in value.get("results", [])]
    for item in entries:
        item.setdefault("status", "failed" if item.get("error") else "queued")
    active = any(item["status"] not in TERMINAL for item in entries)
    status = "running" if active else "partial" if any(item["status"] in {"partial", "failed"} for item in entries) else "completed"
    progress = round(sum(percent(item.get("phase"), item["status"]) for item in entries) / len(entries)) if entries else 0
    phases = Counter(stage(item.get("phase"), item["status"]) for item in entries if item["status"] not in TERMINAL)
    return base("batch:" + value["id"], "mass", updated_at, "Массовые действия · " + " · ".join(
        str(value.get("filter", {}).get(key) or "") for key in ("brand", "geo")),
        active=active, status=status, progress=min(progress, 99) if active else progress,
        stage="; ".join(f"{label}: {count}" for label, count in phases.items()) if active else STATUSES[status],
        total=len(entries), report_url="/dashboard?mass_report=" + quote(value["id"], safe=""))


def job_row(db, job, runs, number):
    from app import maintenance_reports, pilot_internal_pages
    result, payload = job.result or {}, job.payload or {}
    if job.kind == "maintenance_report":
        rows = result.get("entries", [])
        summary = maintenance_reports.summary(job)
        progress = summary["progress"]["percent"]
        active = job.status not in TERMINAL
        phases = Counter(stage(row.get("phase"), row.get("status")) for row in rows
                         if row.get("status") not in TERMINAL)
        title, url = payload.get("name") or "Массовые действия", summary["report_url"]
    else:
        rows = []
        live_child = False
        plans = pilot_internal_pages.plan_options(job)
        for item in result.get("items", {}).values():
            row = dict(item)
            run = runs.get(row.get("run_id"))
            if run:
                row.update(status=run.status, phase=run.phase)
                live_child = live_child or run.status not in TERMINAL
            row["progress"] = percent(row.get("phase"), row.get("status"))
            if job.kind == "mass_reglue_list" and row.get("site_id") in plans:
                state = pilot_internal_pages.snapshot(db, job.id, row["site_id"], plans[row["site_id"]])
                pilot_internal_pages.merge_row(row, state)
                live_child = live_child or bool(state and state["status"] not in TERMINAL | {"planned"})
            rows.append(row)
        preview = job.kind == "auto_pilot_preview"
        active = job.status not in TERMINAL or (not preview and live_child)
        progress = round(sum(row["progress"] for row in rows) / len(rows)) if rows else 0
        if preview and job.status == "completed":
            progress = 100
        phases = Counter(stage(row.get("phase"), row.get("status")) for row in rows
                         if row.get("status") not in TERMINAL | {"ready"})
        title = payload.get("name") or ("Подготовка массовых действий" if preview else "Массовый переклей")
        url = f"/auto-reglue/pilot{'/logs' if not preview else ''}?id={job.id}"
    progress = min(progress, 99) if active else progress
    # A stopped job is not a successful one even if all processing steps finished.
    status = "running" if active else job.status
    if not active and status == "completed" and any(row.get("status") in {"failed", "partial"} for row in rows):
        status = "partial"
    label = "; ".join(f"{label}: {count}" for label, count in phases.items()) if active else STATUSES.get(status, status)
    return base("job:" + job.id, "mass", job.updated_at or job.created_at, title,
                report_url=url, report_number=number, active=active, status=status,
                progress=progress, stage=label or "Подготовка", total=len(rows),
                done=sum(row.get("status") in TERMINAL for row in rows),
                started_at=utc(job.started_at or job.created_at).isoformat())


def feed(db, user, *, before=None, limit=50):
    allowed = user.get("allowed_site_ids")
    sites_query = select(models.Site).options(load_only(models.Site.id, models.Site.name))
    if allowed is not None:
        sites_query = sites_query.where(models.Site.id.in_(allowed))
    sites = {site.id: site for site in db.scalars(sites_query)}
    runs = {run.id: run for run in db.scalars(select(models.AutoReglueRun).where(
        models.AutoReglueRun.site_id.in_(sites)))}
    config_rows = list(db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.startswith("pilot-report-id:") |
        models.AutoReglueConfig.key.startswith("pilot-cancel:") |
        models.AutoReglueConfig.key.startswith("mass-report:"))))
    configs = {row.key: row.value for row in config_rows}
    jobs = []
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind.in_(
            ["mass_reglue_list", "auto_pilot_preview", "maintenance_report"]))):
        # Match report permissions, including donor projects, so every link opens.
        payload, result = job.payload or {}, job.result or {}
        ids = set(payload.get("site_ids", [])) | {p.get("source_site_id", p["site_id"])
            for group in result.get("groups", []) for p in group.get("plans", [])}
        if payload.get("actor") != user["username"] or (allowed is not None and not ids.issubset(allowed)):
            continue
        if configs.get("pilot-cancel:" + job.id, {}).get("deleted"):
            continue
        jobs.append(job)
    mass_run_ids = {item.get("run_id") for job in jobs for item in (job.result or {}).get("items", {}).values()}
    mass_job_ids = {job.id for job in jobs}
    mass_run_ids.update(run.id for run in runs.values() if (run.plan or {}).get("list_launch_id") in mass_job_ids
                        or (run.plan or {}).get("maintenance_repeat_id") in mass_job_ids)
    rows = [job_row(db, job, runs, configs.get("pilot-report-id:" + job.id, {}).get("number")) for job in jobs]
    for config in config_rows:
        if not config.key.startswith("mass-report:"):
            continue
        value = config.value or {}
        run_ids = {item.get("run_id") for item in value.get("results", []) if item.get("run_id")}
        # Auto Pilot creates per-group manifests too; the parent report owns them.
        if run_ids.intersection(mass_run_ids) or not legacy_allowed(value, runs, allowed):
            continue
        rows.append(legacy_row(value, runs, max([utc(config.updated_at)] + [utc(runs[id].updated_at) for id in run_ids if id in runs])))
        mass_run_ids.update(run_ids)
    main_by_run = {}
    for op in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id.in_(sites), models.NetworkOperation.status == "confirmed",
            models.NetworkOperation.action.in_(["reglue", "create_fake_main", "select_fake_main"]))):
        payload = op.request_payload or {}
        run_id = payload.get("auto_run_id")
        if op.action != "reglue":
            old, new = payload.get("journal_before"), payload.get("journal_after")
            if old is not None and new is not None:
                # Turning off the active page and deleting it are also changes.
                before_path = old.get("fake_path", "") if old.get("fake_enabled") else ""
                after_path = new.get("fake_path", "") if new.get("fake_enabled") else ""
                change = {"before": before_path, "after": after_path}
            else:
                change = path_change(op)
            if not change or change["before"] == change["after"]:
                continue
            rows.append(base("op:" + op.id, "internal", confirmed_at(op), "Замена внутренней страницы",
                             **project_fields(sites[op.site_id]), before=change["before"], after=change["after"]))
            continue
        old, new = domain_name(payload.get("source_domain")), domain_name(payload.get("reserve"))
        if not new or old == new:
            continue
        row = base("op:" + op.id, "reglue", confirmed_at(op), "Ручной переклей",
                   **project_fields(sites[op.site_id]), before=old or None, after=new)
        if run_id:
            previous = main_by_run.get(run_id)
            if not previous or row["at"] > previous["at"]:
                main_by_run[run_id] = row
        else:
            rows.append(row)
    for run in runs.values():
        if run.id in mass_run_ids:
            continue  # One summary per mass launch; its report contains Main changes.
        plan = run.plan or {}
        row = main_by_run.get(run.id) or base("run:" + run.id, "reglue", run.updated_at or run.created_at,
                                            "Автопереклей" if plan.get("scheduled") else "Ручной переклей в Автопилоте",
                                            **project_fields(sites[run.site_id]))
        row.update(id="run:" + run.id, active=run.status not in TERMINAL, status=run.status,
                   progress=percent(run.phase, run.status), stage=stage(run.phase, run.status),
                   title="Автопереклей" if plan.get("scheduled") else "Ручной переклей в Автопилоте")
        rows.append(row)
    # Legacy receipts can outlive their run record.
    rows.extend(row for run_id, row in main_by_run.items() if run_id not in runs and run_id not in mass_run_ids)
    rows.sort(key=lambda row: (row["at"], row["id"]), reverse=True)
    active = [row for row in rows if row["active"]]
    history = [row for row in rows if not row["active"] and (before is None or row["at"] + "|" + row["id"] < before)]
    selected = history[:limit]
    return {"active": active, "items": selected,
            "next_before": selected[-1]["at"] + "|" + selected[-1]["id"] if len(history) > limit else None,
            "timezone": "Europe/Moscow"}


@router.get("")
def listing(user: AuthUser, db: Session = Depends(get_db), before: str | None = None,
            limit: int = Query(default=50, ge=1, le=200)):
    return feed(db, user, before=before, limit=limit)


@router.get("/fibery-tasks")
def fibery_tasks(user: AuthUser, db: Session = Depends(get_db), before: str | None = None,
                 q: str = Query(default='', max_length=200), limit: int = Query(default=50, ge=1, le=200),
                 site_id: str | None = Query(default=None, max_length=36)):
    from app.fibery_tasks import feed as tasks_feed
    return tasks_feed(db, user, query=q, before=before, limit=limit, site_id=site_id)


@router.get("/reports/{report_id}")
def legacy_report(report_id: str, user: AuthUser, db: Session = Depends(get_db)):
    from app.mass_action_reports import entry
    config = db.get(models.AutoReglueConfig, "mass-report:" + report_id)
    if config is None:
        raise HTTPException(404, "Отчёт не найден.")
    value = config.value
    ids = [row.get("run_id") for row in value.get("results", []) if row.get("run_id")]
    runs = {run.id: run for run in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.id.in_(ids)))}
    if not legacy_allowed(value, runs, user.get("allowed_site_ids")):
        raise HTTPException(404, "Отчёт не найден.")
    return {**value, "entries": [{**row, **(entry(runs[row["run_id"]]) if row.get("run_id") in runs else {})}
                                 for row in value.get("results", [])]}
