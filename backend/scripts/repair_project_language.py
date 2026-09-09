"""Regenerate every published page of one project in its authoritative project language."""

import argparse
import asyncio
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.services import project_content_language, publish_item, revise_content_item


REPAIR_ACTOR = "system-project-language-fix"


def candidate_ids(site_name: str) -> tuple[str, list[str]]:
    db = SessionLocal()
    try:
        site = db.scalar(select(models.Site).where(models.Site.name == site_name))
        if not site:
            raise ValueError(f"Project not found: {site_name}")
        language = project_content_language(site, "")
        if not language:
            raise ValueError(f"Project language is not configured: {site_name}")
        ids = list(db.scalars(
            select(models.ContentItem.id)
            .where(models.ContentItem.site_id == site.id, models.ContentItem.status == "published")
            .order_by(models.ContentItem.published_at.asc(), models.ContentItem.id.asc())
        ).all())
        return language, ids
    finally:
        db.close()


def repair_item(item_id: str, language: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        item = db.get(models.ContentItem, item_id)
        if not item or item.status != "published":
            return {"id": item_id, "status": "skipped"}
        task = db.get(models.GenerationTask, item.task_id)
        site = db.get(models.Site, item.site_id) if item.site_id else None
        if not task or not site:
            return {"id": item_id, "status": "missing_context"}
        task.language = language
        source = copy.deepcopy(item.generated_json)
        revision = models.ContentRevision(
            content_item_id=item.id,
            remarks=(
                f"Rewrite the complete page in the authoritative project language {language}. "
                "Every public field must use that language: SEO title, meta description, H1, headings, "
                "paragraphs, lists, tables, captions, FAQ questions and answers. Preserve the topic, "
                "useful verified facts, page purpose and exact URL. Do not leave English sentences or mixed-language copy."
            ),
            generate_title=True,
            generation_options={
                "repair": "project_language_v1",
                "project_language": language,
                "target_words": task.target_words,
                "include_toc": task.include_toc,
                "include_faq": task.include_faq,
                "use_competitor_brief": True,
            },
            source_status="published",
            is_published_replacement=True,
            status="queued",
            source_json=source,
            source_generated_at=item.generated_at,
            created_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.commit()
        revise_content_item(db, item, revision)
        item = db.get(models.ContentItem, item_id)
        item.status = "approved"
        db.commit()
        asyncio.run(publish_item(db, item, site, initiator_username=REPAIR_ACTOR))
        db.refresh(item)
        page = item.generated_json["pages"][0]
        return {
            "id": item.id,
            "status": item.status,
            "site": site.name,
            "slug": str(page.get("slug") or item.slug),
            "title": str(page.get("title") or ""),
        }
    except Exception as error:
        db.rollback()
        return {"id": item_id, "status": "error", "error": f"{type(error).__name__}: {error}"[:500]}
    finally:
        db.close()


def main(site_name: str, apply: bool) -> None:
    language, ids = candidate_ids(site_name)
    print({"site": site_name, "project_language": language, "candidates": len(ids), "apply": apply})
    if not apply:
        print({"ids": ids})
        return
    results = []
    for index, item_id in enumerate(ids, start=1):
        result = repair_item(item_id, language)
        results.append(result)
        print({"progress": f"{index}/{len(ids)}", **result})
    print({"completed": sum(result["status"] != "error" for result in results),
           "errors": [result for result in results if result["status"] == "error"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    main(args.site, args.apply)
