"""Normalize FAQ blocks and republish every affected live page once."""

import argparse
import asyncio
import copy
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.services import normalize_editor_inline_markup, publish_item


REPAIR_PREFIX = "faq-format-"
REPAIR_ACTOR = "system-faq-format-fix"


def payload_has_faq(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return False
    for page in pages:
        content = page.get("content") if isinstance(page, dict) else None
        blocks = content.get("blocks") if isinstance(content, dict) else None
        if isinstance(blocks, list) and any(
            isinstance(block, dict) and block.get("type") == "faq" for block in blocks
        ):
            return True
    return False


def repair_candidate(item: models.ContentItem) -> tuple[dict, bool, bool]:
    normalized = normalize_editor_inline_markup(item.generated_json)
    changed = normalized != item.generated_json
    has_faq = payload_has_faq(normalized)
    already_repaired = item.idempotency_key.startswith(REPAIR_PREFIX)
    retry = already_repaired and item.status in {"publication_pending_confirmation", "publication_failed"}
    should_publish = has_faq and (changed or not already_repaired or retry)
    return normalized, changed, should_publish


async def republish_item(content_item_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        item = db.get(models.ContentItem, content_item_id)
        if not item or item.status not in {"published", "publication_pending_confirmation", "publication_failed"}:
            return {"id": content_item_id, "status": "skipped"}
        normalized, changed, should_publish = repair_candidate(item)
        if not should_publish:
            return {"id": content_item_id, "status": "unchanged"}
        task = db.get(models.GenerationTask, item.task_id)
        site_id = item.site_id or (task.site_id if task else None)
        site = db.get(models.Site, site_id) if site_id else None
        if not site:
            return {"id": content_item_id, "status": "missing_site"}

        if changed:
            previous = copy.deepcopy(item.generated_json)
            now = datetime.now(timezone.utc)
            item.generated_json = normalized
            db.add(models.ContentRevision(
                content_item_id=item.id,
                remarks="Системное преобразование FAQ в Editor.js-блок",
                generate_title=False,
                generation_options={"repair": "faq_format_v1"},
                source_status=item.status,
                is_published_replacement=True,
                status="completed",
                source_json=previous,
                revised_json=copy.deepcopy(normalized),
                source_generated_at=item.generated_at,
                revised_generated_at=now,
            ))
        item.idempotency_key = f"{REPAIR_PREFIX}{item.id}-{uuid.uuid4().hex[:10]}"
        item.status = "approved"
        db.commit()
        await publish_item(db, item, site, initiator_username=REPAIR_ACTOR)
        db.refresh(item)
        return {"id": item.id, "status": item.status, "site": site.name, "topic": item.topic}
    except Exception as error:
        db.rollback()
        return {"id": content_item_id, "status": "error", "error": f"{type(error).__name__}: {error}"[:300]}
    finally:
        db.close()


def find_candidates() -> tuple[dict[str, list[str]], Counter]:
    db = SessionLocal()
    counts: Counter = Counter()
    items_by_site: dict[str, list[str]] = defaultdict(list)
    try:
        items = db.scalars(select(models.ContentItem).where(models.ContentItem.status.in_([
            "published", "publication_pending_confirmation", "publication_failed",
        ]))).all()
        for item in items:
            normalized, changed, should_publish = repair_candidate(item)
            if not should_publish:
                continue
            counts["matched"] += 1
            counts["converted"] += int(changed)
            counts["already_structured"] += int(not changed and payload_has_faq(normalized))
            items_by_site[item.site_id or item.task_id].append(item.id)
    finally:
        db.close()
    return items_by_site, counts


async def main(apply: bool) -> None:
    items_by_site, counts = find_candidates()
    print(dict(counts))
    if not apply:
        print("Dry run only. Pass --apply to save and republish.")
        return

    semaphore = asyncio.Semaphore(4)

    async def republish_site(item_ids: list[str]) -> list[dict[str, str]]:
        async with semaphore:
            results: list[dict[str, str]] = []
            for item_id in item_ids:
                result = await republish_item(item_id)
                results.append(result)
                print(result)
            return results

    grouped = await asyncio.gather(*(republish_site(item_ids) for item_ids in items_by_site.values()))
    result_counts = Counter(result["status"] for results in grouped for result in results)
    print({"requested": counts["matched"], "results": dict(result_counts)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Save normalized JSON and republish matching pages")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.apply))
