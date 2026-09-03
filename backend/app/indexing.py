import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings


logger = logging.getLogger(__name__)
INDEXING_TASK_ID_PATTERN = re.compile(r"ID\s+задачи\s*:\s*([^\s.!]+)", re.IGNORECASE)


def _project_origin(site: models.Site) -> str:
    value = str(site.cache_canon or site.base_url or site.name).strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlsplit(value)
    if not parsed.netloc:
        raise ValueError("Не удалось определить MAIN-домен проекта для индексации")
    return urlunsplit((parsed.scheme or "https", parsed.netloc, "", "", "")).rstrip("/")


def content_indexing_urls(site: models.Site, items: list[models.ContentItem]) -> list[str]:
    origin = _project_origin(site)
    origin_parts = urlsplit(origin)
    urls = [f"{origin}/"]
    for item in items:
        source = str(item.published_url or item.slug or "").strip()
        absolute = source if source.startswith(("http://", "https://")) else urljoin(f"{origin}/", source.lstrip("/"))
        parsed = urlsplit(absolute)
        page_url = urlunsplit((origin_parts.scheme, origin_parts.netloc, parsed.path or "/", parsed.query, ""))
        if page_url not in urls:
            urls.append(page_url)
    return urls


def _indexing_task_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    google = payload.get("google")
    if not isinstance(google, dict) or str(google.get("icon") or "").lower() != "success":
        return None
    match = INDEXING_TASK_ID_PATTERN.search(str(google.get("text") or ""))
    return match.group(1) if match else None


def submit_indexing_batch(
    db: Session,
    site: models.Site,
    items: list[models.ContentItem],
    *,
    client: httpx.Client | None = None,
) -> str | None:
    if not items:
        return None
    endpoint = get_settings().indexing_endpoint
    request_payload = {"domains": content_indexing_urls(site, items), "engines": ["google"]}
    requested_at = datetime.now(timezone.utc)
    for item in items:
        item.indexing_status = "submitting"
        item.indexing_requested_at = requested_at
        item.indexing_error = None
    db.commit()

    owns_client = client is None
    active_client = client or httpx.Client(timeout=30.0)
    response_status: int | None = None
    response_body: dict[str, Any] | None = None
    error_message: str | None = None
    task_id: str | None = None
    try:
        response = active_client.post(endpoint, json=request_payload)
        response_status = response.status_code
        try:
            raw_body = response.json()
            response_body = raw_body if isinstance(raw_body, dict) else {"response": raw_body}
        except ValueError:
            response_body = {"raw": response.text[:2000]}
        if not 200 <= response.status_code < 300:
            error_message = f"Indexing endpoint returned HTTP {response.status_code}"
        else:
            task_id = _indexing_task_id(response_body)
            if not task_id:
                error_message = "Indexing endpoint did not return a successful Google task ID"
    except Exception as error:
        error_message = f"{type(error).__name__}: {error}"[:1000]
    finally:
        if owns_client:
            active_client.close()

    for item in items:
        item.indexing_status = "submitted" if task_id else "failed"
        item.indexing_task_id = task_id
        item.indexing_error = error_message
        db.add(models.PublicationLog(
            content_item_id=item.id,
            endpoint_url=endpoint,
            request_payload={**request_payload, "action": "google_indexing"},
            response_status=response_status,
            response_body=response_body,
            error_message=error_message,
        ))
    db.commit()
    if error_message:
        logger.warning("Content indexing failed for site=%s items=%d: %s", site.name, len(items), error_message)
    else:
        logger.info("Content indexing submitted for site=%s items=%d task_id=%s", site.name, len(items), task_id)
    return task_id


def submit_pending_content_indexing(db: Session, limit: int = 100) -> dict[str, int]:
    stale_before = datetime.now(timezone.utc) - timedelta(minutes=5)
    items = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.status == "published")
        .where(models.ContentItem.indexing_task_id.is_(None))
        .where(or_(
            models.ContentItem.indexing_status == "queued",
            (models.ContentItem.indexing_status == "submitting")
            & (models.ContentItem.indexing_requested_at < stale_before),
        ))
        .order_by(models.ContentItem.published_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    claimed_at = datetime.now(timezone.utc)
    for item in items:
        item.indexing_status = "submitting"
        item.indexing_requested_at = claimed_at
    db.commit()
    grouped: dict[str, list[models.ContentItem]] = defaultdict(list)
    failed = 0
    for item in items:
        if not item.site_id:
            item.indexing_status = "failed"
            item.indexing_error = "Проект публикации не указан"
            failed += 1
        else:
            grouped[item.site_id].append(item)
    db.commit()

    submitted = 0
    for site_id, site_items in grouped.items():
        site = db.get(models.Site, site_id)
        if not site:
            for item in site_items:
                item.indexing_status = "failed"
                item.indexing_error = "Проект публикации не найден"
            failed += len(site_items)
            db.commit()
            continue
        if submit_indexing_batch(db, site, site_items):
            submitted += len(site_items)
        else:
            failed += len(site_items)
    return {"processed": len(items), "submitted": submitted, "failed": failed}
