"""Attach exact internal URLs to the 20 generated entries on the Whitby Blog page."""

import argparse
import asyncio
import copy
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.services import publish_item
from scripts.reconcile_whitby_menu_content import ACTOR, PLACEMENTS, SITE_NAME


def attach_links(payload: dict, urls: list[str]) -> tuple[dict, int]:
    revised = copy.deepcopy(payload)
    page = revised["pages"][0]
    blocks = page["content"]["blocks"]
    in_directory = False
    candidates: list[tuple[dict, int, str]] = []
    for block in blocks:
        data = block.get("data")
        if block.get("type") == "header" and isinstance(data, dict):
            heading = re.sub(r"<[^>]+>", "", str(data.get("text") or "")).casefold()
            if "artikler og vejledninger" in heading:
                in_directory = True
                continue
            if in_directory:
                break
        if in_directory and block.get("type") == "list" and isinstance(data, dict):
            for index, value in enumerate(data.get("items") or []):
                candidates.append((data, index, str(value)))
    if len(candidates) != len(urls):
        raise ValueError(f"Blog directory has {len(candidates)} entries; expected {len(urls)}")
    for (data, index, value), url in zip(candidates, urls, strict=True):
        if " — " not in value:
            raise ValueError(f"Blog entry has no anchor/description separator: {value[:80]}")
        anchor, description = value.split(" — ", 1)
        anchor = re.sub(r"<[^>]+>", "", anchor).strip()
        data["items"][index] = f'<a href="{url}">{anchor}</a> — {description.strip()}'
    return revised, len(candidates)


async def run(apply: bool) -> None:
    db = SessionLocal()
    try:
        site = db.scalar(select(models.Site).where(models.Site.name == SITE_NAME))
        if not site:
            raise ValueError(f"Project not found: {SITE_NAME}")
        blog = db.scalar(select(models.ContentItem).where(
            models.ContentItem.site_id == site.id,
            models.ContentItem.slug == "/blog/",
            models.ContentItem.status.in_(["published", "publication_pending_confirmation"]),
        ).order_by(models.ContentItem.created_at.desc()))
        if not blog:
            raise ValueError("Published Blog page not found")
        urls = []
        for item_id in PLACEMENTS:
            item = db.get(models.ContentItem, item_id)
            urls.append(str(item.generated_json["pages"][0].get("slug") or item.slug))
        revised, links = attach_links(blog.generated_json, urls)
        page = revised["pages"][0]
        print({
            "blog_id": blog.id,
            "title": page.get("title"),
            "title_chars": len(str(page.get("title") or "")),
            "description": page.get("description"),
            "links": links,
            "unique_urls": len(set(urls)),
            "apply": apply,
        }, flush=True)
        if not apply:
            return
        source = copy.deepcopy(blog.generated_json)
        blog.generated_json = revised
        blog.idempotency_key = f"blog-links-{blog.id}-{uuid.uuid4().hex[:10]}"
        previous_status = blog.status
        blog.status = "approved"
        now = datetime.now(timezone.utc)
        db.add(models.ContentRevision(
            content_item_id=blog.id,
            remarks="Добавлены 20 точных внутренних ссылок к сгенерированным анкорам и описаниям страницы Blog",
            generate_title=False,
            generation_options={"repair": "blog_internal_links_v1", "links": links},
            source_status=previous_status,
            is_published_replacement=True,
            status="completed",
            source_json=source,
            revised_json=copy.deepcopy(revised),
            source_generated_at=blog.generated_at,
            revised_generated_at=now,
        ))
        db.commit()
        await publish_item(db, blog, site, initiator_username=ACTOR)
        db.refresh(blog)
        print({"status": blog.status, "slug": blog.slug}, flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.apply))
