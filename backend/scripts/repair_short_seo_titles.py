"""Generate informative titles for published pages whose SEO titles are too short."""

import argparse
import asyncio
import copy
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.services import clean_text, generate_seo_title, publish_item, seo_title_needs_improvement


REPAIR_ACTOR = "system-short-title-fix"


def published_title_needs_repair(value: object) -> bool:
    words = re.findall(r"[^\W_]+", clean_text(value), flags=re.UNICODE)
    return len(words) <= 3


def article_excerpt(payload: dict) -> str:
    pages = payload.get("pages") if isinstance(payload, dict) else []
    page = pages[0] if isinstance(pages, list) and pages and isinstance(pages[0], dict) else {}
    blocks = (page.get("content") or {}).get("blocks") or []
    values: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            text = clean_text(value)
            if text:
                values.append(text)
        elif isinstance(value, list):
            for entry in value:
                collect(entry)
        elif isinstance(value, dict):
            for key, entry in value.items():
                if key not in {"id", "type", "level", "style", "url"}:
                    collect(entry)

    for block in blocks:
        if isinstance(block, dict):
            collect(block.get("data"))
        if sum(map(len, values)) >= 4000:
            break
    return " ".join(values)[:4000]


def candidate_ids() -> dict[str, list[str]]:
    db = SessionLocal()
    try:
        result: dict[str, list[str]] = defaultdict(list)
        for item in db.scalars(select(models.ContentItem).where(models.ContentItem.status == "published")).all():
            pages = item.generated_json.get("pages") if isinstance(item.generated_json, dict) else []
            page = pages[0] if isinstance(pages, list) and pages and isinstance(pages[0], dict) else {}
            if published_title_needs_repair(page.get("title")):
                result[item.site_id or item.task_id].append(item.id)
        return dict(result)
    finally:
        db.close()


async def repair_item(item_id: str, apply: bool) -> dict[str, str]:
    db = SessionLocal()
    try:
        item = db.get(models.ContentItem, item_id)
        if not item or item.status != "published":
            return {"id": item_id, "status": "skipped"}
        task = db.get(models.GenerationTask, item.task_id)
        site = db.get(models.Site, item.site_id) if item.site_id else None
        provider = db.get(models.AiProvider, task.ai_provider_id) if task and task.ai_provider_id else None
        if not provider or not provider.is_active or provider.provider_type != "gemini":
            provider = db.scalar(select(models.AiProvider).where(
                models.AiProvider.is_active.is_(True),
                models.AiProvider.provider_type == "gemini",
            ).order_by(models.AiProvider.updated_at.desc()))
        if not task or not site or not provider:
            return {"id": item_id, "status": "missing_provider"}
        pages = item.generated_json.get("pages") if isinstance(item.generated_json, dict) else []
        page = pages[0] if isinstance(pages, list) and pages and isinstance(pages[0], dict) else None
        if not page or not published_title_needs_repair(page.get("title")):
            return {"id": item_id, "status": "unchanged"}
        old_title = str(page.get("title") or item.topic).strip()
        new_title = await generate_seo_title(
            provider,
            topic=item.topic,
            current_title=old_title,
            geo=task.geo,
            language=task.language,
            homepage_title=site.homepage_title,
            meta_description=page.get("description"),
            article_excerpt=article_excerpt(item.generated_json),
        )
        if not apply:
            return {"id": item.id, "status": "preview", "site": site.name, "old": old_title, "new": new_title}
        previous = copy.deepcopy(item.generated_json)
        revised = copy.deepcopy(item.generated_json)
        revised["pages"][0]["title"] = new_title
        item.generated_json = revised
        item.idempotency_key = f"title-repair-{item.id}-{uuid.uuid4().hex[:10]}"
        item.status = "approved"
        now = datetime.now(timezone.utc)
        db.add(models.ContentRevision(
            content_item_id=item.id,
            remarks="Системная замена слишком короткого SEO-тайтла",
            generate_title=True,
            generation_options={"repair": "short_seo_title_v1", "old_title": old_title, "new_title": new_title},
            source_status="published",
            is_published_replacement=True,
            status="completed",
            source_json=previous,
            revised_json=copy.deepcopy(revised),
            source_generated_at=item.generated_at,
            revised_generated_at=now,
        ))
        db.commit()
        await publish_item(db, item, site, initiator_username=REPAIR_ACTOR)
        db.refresh(item)
        return {"id": item.id, "status": item.status, "site": site.name, "old": old_title, "new": new_title}
    except Exception as error:
        db.rollback()
        return {"id": item_id, "status": "error", "error": f"{type(error).__name__}: {error}"[:300]}
    finally:
        db.close()


async def main(apply: bool) -> None:
    ids_by_site = candidate_ids()
    print({"candidates": sum(map(len, ids_by_site.values())), "projects": len(ids_by_site), "apply": apply})
    semaphore = asyncio.Semaphore(3)

    async def run_site(item_ids: list[str]) -> list[dict[str, str]]:
        async with semaphore:
            results = []
            for item_id in item_ids:
                result = await repair_item(item_id, apply)
                print(result)
                results.append(result)
            return results

    grouped = await asyncio.gather(*(run_site(item_ids) for item_ids in ids_by_site.values()))
    results = [result for group in grouped for result in group]
    print({"results": dict(Counter(result["status"] for result in results))})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
