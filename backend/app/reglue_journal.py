"""Read-only journal built from confirmed PagePilot receipts, never current cache."""
from collections import defaultdict
from datetime import date, datetime, time, timezone
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.network_state import alternate_links, domain_name
from app.reglue_history import MOSCOW, utc
from app.security import AuthUser

router = APIRouter(prefix="/reglue-journal", tags=["reglue-journal"])


def snapshot(state):
    return {"main": state.get("canon"), "fake_path": state.get("fake_main_current") or "",
            "fake_enabled": bool(state.get("fake_main_enabled"))}


def confirmed_at(operation):
    # updated_at is the legacy fallback only; new receipts keep confirmation time.
    return utc((operation.request_payload or {}).get("confirmed_at")) or utc(operation.updated_at)


def main_operations(db, user):
    query = select(models.NetworkOperation, models.Site.name, models.Site.brand, models.Site.cache_geo).join(
        models.Site, models.Site.id == models.NetworkOperation.site_id).where(
        models.NetworkOperation.action == "reglue", models.NetworkOperation.status == "confirmed",
        models.NetworkOperation.initiator == user["username"])
    allowed = user.get("allowed_site_ids")
    if allowed is not None:
        query = query.where(models.NetworkOperation.site_id.in_(allowed))
    return [(op, name, brand, geo) for op, name, brand, geo in db.execute(query)
            if domain_name((op.request_payload or {}).get("source_domain"))
            != domain_name((op.request_payload or {}).get("reserve"))
            and domain_name((op.request_payload or {}).get("reserve"))]


def markup_path(markup):
    """Only an unambiguous historical internal path; missing data stays unknown."""
    paths = set()
    for link in alternate_links(markup or ""):
        try:
            path = urlsplit(link["href"]).path
        except ValueError:
            continue
        if path and path != "/" and "{{" not in path:
            paths.add(path)
    return next(iter(paths)) if len(paths) == 1 else None


def path_change(operation):
    payload = operation.request_payload or {}
    alternate = payload.get("alternate") or {}
    if not alternate.get("enableDynamicRoutes", True):
        return None
    after = alternate.get("currentFakeMain")
    if not after:
        return None  # Creating an inactive spare path is not a path change.
    before = payload.get("journal_before", {}).get("fake_path")
    if before is None:
        before = markup_path(payload.get("head_before", {}).get("alternateMarkup"))
    return {"before": before, "after": after, "at": confirmed_at(operation).isoformat()}


def entries(db, user, rows):
    site_ids = {op.site_id for op, *_ in rows}
    paths_by_site = defaultdict(list)
    if site_ids:
        for op in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id.in_(site_ids), models.NetworkOperation.status == "confirmed",
            models.NetworkOperation.action.in_(["create_fake_main", "select_fake_main"]),
            models.NetworkOperation.initiator == user["username"])):
            paths_by_site[op.site_id].append(op)
    result, previous_main_at = [], {}
    for op, project, brand, geo in sorted(rows, key=lambda row: (confirmed_at(row[0]), row[0].id)):
        payload, at = op.request_payload or {}, confirmed_at(op)
        run_id = payload.get("auto_run_id")
        day_start = datetime.combine(at.astimezone(MOSCOW).date(), time.min, MOSCOW).astimezone(timezone.utc)
        previous = previous_main_at.get(op.site_id)
        changes = []
        for path_op in sorted(paths_by_site[op.site_id], key=lambda item: (confirmed_at(item), item.id)):
            path_at = confirmed_at(path_op)
            path_run = (path_op.request_payload or {}).get("auto_run_id")
            # A run owns its own preparation, even across midnight. Manual changes
            # are shown only for this day, before this Main change, once per entry.
            belongs = path_run == run_id if run_id else not path_run and day_start <= path_at
            if belongs and path_at <= at and (previous is None or path_at > previous):
                change = path_change(path_op)
                if change:
                    changes.append(change)
        previous_main_at[op.site_id] = at
        before = payload.get("journal_before", {}).get("fake_path")
        after = payload.get("journal_after", {}).get("fake_path")
        if before is None:
            before = markup_path(payload.get("_indexing", {}).get("alternateMarkup"))
        if after is None:
            after = before
        if changes:
            before, after = changes[0]["before"], changes[-1]["after"]
        result.append({"id": op.id, "site_id": op.site_id, "project": project,
            "project_url": f"/project-network/{quote(project, safe='')}/", "brand": brand, "geo": geo,
            "at": at.isoformat(), "date": at.astimezone(MOSCOW).date().isoformat(),
            "old_main": domain_name(payload.get("source_domain")) or None,
            "new_main": domain_name(payload.get("reserve")), "old_path": before, "new_path": after,
            "path_changes": changes, "mode": "Массовый / автопереклей" if run_id else "Ручной переклей"})
    return sorted(result, key=lambda row: (row["at"], row["id"]), reverse=True)


def journal(db, user, *, now=None, before=None, days=14):
    today = (utc(now) or datetime.now(timezone.utc)).astimezone(MOSCOW).date().isoformat()
    rows = main_operations(db, user)
    today_count = sum(confirmed_at(op).astimezone(MOSCOW).date().isoformat() == today for op, *_ in rows)
    dates = sorted({confirmed_at(op).astimezone(MOSCOW).date().isoformat() for op, *_ in rows
                    if before is None or confirmed_at(op).astimezone(MOSCOW).date() < before}, reverse=True)
    selected = dates[:days]
    # Include preceding Main receipts in reconstruction so preparation is never
    # attributed to two operations, then paginate whole dates (not partial days).
    items = entries(db, user, rows)
    return {"today": today, "today_count": today_count, "total": len(rows), "timezone": "Europe/Moscow",
            "days": [{"date": day, "items": [item for item in items if item["date"] == day]} for day in selected],
            "next_before": selected[-1] if len(dates) > days else None}


def latest_for_site(db, site):
    """Last confirmed change by any actor, including receipts beyond the UI's 20 rows."""
    operations = list(db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id, models.NetworkOperation.action == "reglue",
        models.NetworkOperation.status == "confirmed")))
    operations = [op for op in operations if domain_name((op.request_payload or {}).get("reserve"))
                  and domain_name((op.request_payload or {}).get("source_domain"))
                  != domain_name((op.request_payload or {}).get("reserve"))]
    if not operations:
        return None
    latest = max(operations, key=lambda op: (confirmed_at(op), op.id))
    rows = [(op, site.name, site.brand, site.cache_geo) for op in operations]
    entry = entries(db, {"username": latest.initiator}, rows)[0]
    return {key: entry[key] for key in ("at", "old_main", "new_main", "old_path", "new_path")}


def recent_for_site(db, site, limit=7):
    """Confirmed Main and active fake-path changes by any actor, newest first."""
    operations = db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.status == 'confirmed',
        models.NetworkOperation.action.in_(['reglue', 'create_fake_main', 'select_fake_main']))).all()
    items = []
    for op in operations:
        payload = op.request_payload or {}
        before, after = payload.get('journal_before') or {}, payload.get('journal_after') or {}
        if op.action == 'reglue':
            old_main, new_main = domain_name(payload.get('source_domain')), domain_name(payload.get('reserve'))
            if not new_main or old_main == new_main:
                continue
            items.append({'id': op.id, 'kind': 'reglue', 'at': confirmed_at(op).isoformat(),
                          'old_main': old_main or None, 'new_main': new_main,
                          'old_path': before.get('fake_path'), 'new_path': after.get('fake_path')})
        else:
            change = path_change(op)
            if not change or change['before'] == change['after']:
                continue
            items.append({'id': op.id, 'kind': 'fake_path', 'at': change['at'],
                          'old_main': before.get('main'), 'new_main': after.get('main') or before.get('main'),
                          'old_path': change['before'], 'new_path': change['after']})
    return sorted(items, key=lambda item: (utc(item['at']), item['id']), reverse=True)[:limit]


@router.get("/summary")
def summary(user: AuthUser, db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).astimezone(MOSCOW).date().isoformat()
    rows = main_operations(db, user)
    return {"today": today, "today_count": sum(
        confirmed_at(op).astimezone(MOSCOW).date().isoformat() == today for op, *_ in rows)}


@router.get("")
def listing(user: AuthUser, db: Session = Depends(get_db), before: date | None = None,
            days: int = Query(default=14, ge=1, le=31)):
    return journal(db, user, before=before, days=days)
