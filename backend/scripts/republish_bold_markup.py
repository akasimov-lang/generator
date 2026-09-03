"""Normalize legacy Markdown bold markers and republish affected live pages."""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.services import normalize_editor_inline_markup, publish_item


async def republish_item(content_item_id: str, semaphore: asyncio.Semaphore) -> dict[str, str]:
    async with semaphore:
        db = SessionLocal()
        try:
            item = db.get(models.ContentItem, content_item_id)
            if not item or item.status != "published":
                return {"id": content_item_id, "status": "skipped"}
            normalized = normalize_editor_inline_markup(item.generated_json)
            if normalized == item.generated_json:
                return {"id": content_item_id, "status": "unchanged"}
            task = db.get(models.GenerationTask, item.task_id)
            site_id = item.site_id or (task.site_id if task else None)
            site = db.get(models.Site, site_id) if site_id else None
            if not site:
                return {"id": content_item_id, "status": "missing_site"}
            item.generated_json = normalized
            item.idempotency_key = f"bold-html-{item.id}-{uuid.uuid4().hex[:10]}"
            item.status = "approved"
            db.commit()
            await publish_item(db, item, site, initiator_username="system-bold-html-fix")
            db.refresh(item)
            return {"id": item.id, "status": item.status, "site": site.name, "topic": item.topic}
        except Exception as error:
            db.rollback()
            return {"id": content_item_id, "status": "error", "error": f"{type(error).__name__}: {error}"[:300]}
        finally:
            db.close()


async def main() -> None:
    db = SessionLocal()
    try:
        published = db.scalars(
            select(models.ContentItem).where(models.ContentItem.status == "published")
        ).all()
        item_ids = [
            item.id
            for item in published
            if normalize_editor_inline_markup(item.generated_json) != item.generated_json
        ]
    finally:
        db.close()

    semaphore = asyncio.Semaphore(4)
    results = await asyncio.gather(*(republish_item(item_id, semaphore) for item_id in item_ids))
    counts: dict[str, int] = {}
    for result in results:
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1
        print(result)
    print({"matched": len(item_ids), "results": counts})


if __name__ == "__main__":
    asyncio.run(main())
