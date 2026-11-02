"""Verified page backups using the universal admin's native Webdev endpoints."""
from copy import deepcopy
from datetime import datetime, timezone
import time

import httpx
from fastapi import HTTPException

from app import models
from app.core.config import get_settings


class PageBackupError(ValueError):
    pass


def ensure_backup(db, remote, site, project, page, *, actor, operation, defer_verification=False):
    """Caller holds the project lock. Never repeat an uncertain backup POST.

    The backup list contains the complete saved data, so HTTP success alone is
    insufficient. Reuse is allowed only when the full page AND shortcodes match.
    The durable ledger survives worker restarts and lost HTTP responses.
    """
    from app.project_pages import digest

    shortcodes = project.get("shortcodes")
    if not isinstance(shortcodes, list) or page.get("id") is None:
        raise PageBackupError("Не получены полные данные для бекапа. Обработка остановлена.")
    snapshot = {**deepcopy(page), "_shortcodes": deepcopy(shortcodes)}
    fingerprint = digest(snapshot)
    key = "page-backup:" + digest([site.id, fingerprint])
    ledger = db.get(models.AutoReglueConfig, key)

    def listing():
        # This POST only reads the backup list. A transient read failure after
        # creation must not cause another backup write or discard the edit.
        for attempt in range(2):
            try:
                _, result = remote.request("POST", "/projects/backupList", {
                    "folder": site.name, "id": "111", "page": {"slug": page.get("slug")},
                    "initiator": get_settings().project_cache_username,
                    "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                })
                break
            except httpx.HTTPStatusError as error:
                if attempt or error.response.status_code < 500:
                    raise
            except (httpx.RequestError, ValueError):
                if attempt:
                    raise
            time.sleep(0.2)
        if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
            raise PageBackupError("Админка не вернула список бекапов. Обработка остановлена.")
        return result

    def matching(rows):
        return next((row for row in rows if isinstance(row.get("name"), str)
                     and row["name"] and row.get("data") == snapshot), None)

    def record(status, **extra):
        nonlocal ledger
        if ledger is None:
            ledger = models.AutoReglueConfig(key=key, value={})
            db.add(ledger)
        ledger.value = {**(ledger.value or {}), "status": status, "site_id": site.id,
                        "source_hash": fingerprint, "operation": operation, "actor": actor, **extra}
        db.commit()

    def confirmed(row):
        record("confirmed", name=row["name"], confirmed_at=datetime.now(timezone.utc).isoformat())
        return {"name": row["name"], "source_hash": fingerprint}

    if defer_verification:
        # Auto Pilot saves the full source locally before its only backup POST.
        # The remote backup list is checked after the Title/H1 write, not between stages.
        if ledger:
            return {"status": ledger.value.get('status'), "source_hash": fingerprint}
        record('pending', snapshot=snapshot, requested_at=datetime.now(timezone.utc).isoformat())
        page_id = page['id']
        try:
            _, response = remote.request('POST', '/projects/backup', {
                'folder': site.name, 'id': int(page_id) if str(page_id).isdigit() else page_id,
                'page': snapshot, 'initiator': get_settings().project_cache_username,
                'dateTime': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            })
            record('failed' if isinstance(response, dict) and (response.get('success') is False or response.get('error')) else 'pending')
        except (httpx.HTTPError, ValueError):
            record('unknown')
        return {"status": ledger.value['status'], "source_hash": fingerprint}

    try:
        rows = listing()
        existing = matching(rows)
        if existing:
            return confirmed(existing)
        if ledger and ledger.value.get("status") in {"pending", "unknown"}:
            raise PageBackupError("Бекап пока не подтверждён админкой. Повторная отправка не выполняется; обработка остановлена.")
        # The admin names backups to the second. Avoid overwriting a different
        # version made in the same second by another operation on this project.
        now = datetime.now(timezone.utc)
        suffix = now.strftime("-%Y-%m-%d-%H%M%S.json")
        if any(str(row.get("name", "")).endswith(suffix) for row in rows):
            time.sleep(1.01 - now.microsecond / 1_000_000)
        record("pending", requested_at=datetime.now(timezone.utc).isoformat())
        page_id = page["id"]
        try:
            _, response = remote.request("POST", "/projects/backup", {
                "folder": site.name, "id": int(page_id) if str(page_id).isdigit() else page_id,
                "page": snapshot, "initiator": get_settings().project_cache_username,
                "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            })
            if isinstance(response, dict) and (response.get("success") is False or response.get("error")):
                record("failed")
                raise PageBackupError("Админка отклонила создание бекапа. Обработка остановлена.")
        except httpx.HTTPStatusError as error:
            record("failed" if error.response.status_code < 500 else "unknown")
        except (httpx.RequestError, ValueError) as error:
            if isinstance(error, PageBackupError):
                raise
            record("unknown")
        existing = matching(listing())
        if existing:
            return confirmed(existing)
        if ledger.value.get("status") == "pending":
            record("unknown")
        raise PageBackupError("Не удалось подтвердить содержимое бекапа в админке. Обработка остановлена.")
    except (httpx.HTTPError, ValueError) as error:
        if isinstance(error, PageBackupError):
            raise
        raise PageBackupError("Не удалось проверить бекап в админке. Обработка остановлена.") from error


def backup_draft_source(db, draft):
    """Save the exact editor input, including unpublished edits, before processing."""
    from app import project_pages as pages
    try:
        site = pages.site_for(db, draft.site_id)
        with pages.remote_errors(), pages.network_lock(db, site.id), pages.Remote(db, site) as remote:
            project = remote.project()
            page = deepcopy(pages.find_page(project, draft.page_key))
            page["content"] = deepcopy(draft.input_content)
            for field in ("title", "description"):
                if field in (draft.input_metadata or {}):
                    page[field] = draft.input_metadata[field]
            return ensure_backup(db, remote, site, project, page,
                                 actor=draft.requested_by, operation=f"draft:{draft.id}")
    except HTTPException as error:
        raise PageBackupError(f"Не удалось подготовить бекап: {error.detail}") from error
