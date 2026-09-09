"""Reconcile whitbyluckyducks.com content with its authoritative Danish menu."""

import argparse
import asyncio
import copy
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.schemas import MenuStructureGenerationCreate
from app.services import (
    apply_content_section_slug,
    clean_text,
    create_menu_structure_task,
    project_content_language,
    publish_item,
    sync_project_menus,
)
from app.worker import run_task_pipeline_job


SITE_NAME = "whitbyluckyducks.com"
ACTOR = "system-menu-content-reconcile"

# Existing page -> current menu section. menu_page occupies the menu URL itself;
# nested keeps the article leaf below the selected thematic section.
PLACEMENTS = {
    "4c334ecb-e932-410d-ad38-56a85c4b6eae": ("/spilleautomater/", "menu_page"),
    "ae398500-acc5-4a50-a68b-a96045a5d838": ("/spilleautomater/", "nested"),
    "5f959049-261c-4432-b7f7-691e5f03c461": ("/spilleautomater/", "nested"),
    "4d2be4a1-5437-4c75-9725-9fc596d88931": ("/jackpotspil/", "menu_page"),
    "16913699-1110-479f-ad68-d87d725c3224": ("/live-casino/", "nested"),
    "842bf272-3f9d-4849-bb42-dd6dcc6f8d1b": ("/live-casino/", "nested"),
    "61e82946-127b-4fb3-9a11-f94030e43c9a": ("/bordspil/", "nested"),
    "3443b2a1-6713-4f82-9e76-d681fac920c1": ("/gratis-spins/", "menu_page"),
    "c45db30f-50a2-4b23-84a3-71a671fb2671": ("/spilleautomater/", "nested"),
    "4a3936bf-81a6-476b-8256-f3f2bc9b2b4b": ("/spil/", "menu_page"),
    "5a10e0fe-5640-4d32-9f0b-12598c8a9544": ("/bedste-online-casinoer/", "menu_page"),
    "27ef57d3-c95e-460e-b231-d618e194489f": ("/sikkerhed-og-licenser/", "menu_page"),
    "e6a3d69d-309a-4a35-9a10-45caab4f19d5": ("/bonusvilkar/", "menu_page"),
    "b8cd10fd-2e9c-4ac9-be55-e8d769d2c63d": ("/guides/", "nested"),
    "51d31c0e-776b-4b35-b140-96f7dc771152": ("/spilleautomater/", "nested"),
    "f4724a96-7181-4320-b51f-c3c6055ad6cb": ("/guides/", "nested"),
    "2abb63da-79d2-4480-8ab3-4723bdd83b25": ("/ansvarligt-spil/", "menu_page"),
    "0e2d9afa-1ba8-4ee3-bda1-2a79db680224": ("/guides/", "nested"),
    "e0fb649d-1974-4d9f-a5b1-de2e67003e7c": ("/danske-casinoer/", "menu_page"),
    "b973e75e-7e19-420a-802a-365f29b9fe6e": ("/casino-anmeldelser/", "menu_page"),
}

MISSING_MENU_PATHS = {
    "/online-casinoer/", "/nye-casinoer/", "/casinoer-uden-indbetaling/",
    "/casino-bonusser/", "/velkomstbonusser/", "/bonus-uden-indbetaling/",
    "/live-casino/", "/bordspil/", "/betalingsmetoder/", "/mobilepay/",
    "/betalingskort/", "/e-wallets/", "/hurtig-udbetaling/", "/guides/",
    "/sadan-vaelger-du-casino/",
}


def normalized_slug(value: object) -> str:
    path = str(value or "").strip().strip("/")
    return f"/{path}/" if path else "/"


def menu_children(item: dict) -> list[dict]:
    for key in ("children", "items", "submenu", "subMenu"):
        value = item.get(key)
        if isinstance(value, list):
            return value
    return []


def adopt_menu(db, site: models.Site) -> dict[str, models.Section]:
    existing = db.scalars(select(models.Section).where(models.Section.site_id == site.id)).all()
    by_external = {(row.menu_type, row.external_id.casefold()): row for row in existing if row.external_id}
    by_path = {(row.menu_type, normalized_slug(row.path)): row for row in existing}
    result: dict[str, models.Section] = {}

    def walk(items: list, menu_type: str, parent: models.Section | None = None) -> None:
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            name = clean_text(raw.get("title") or raw.get("name"))
            path = normalized_slug(raw.get("slug") or raw.get("path") or raw.get("url"))
            external_id = clean_text(raw.get("external_id") or raw.get("externalId") or raw.get("id"))
            external_id = external_id or f"cached-{menu_type}-{index}-{path.strip('/')}"
            row = by_external.get((menu_type, external_id.casefold())) or by_path.get((menu_type, path))
            if row is None:
                row = models.Section(
                    site_id=site.id,
                    external_id=external_id,
                    name=name,
                    path=path,
                    menu_type=menu_type,
                )
                db.add(row)
                db.flush()
            row.name = name
            row.path = path
            row.parent_id = parent.id if parent else None
            row.is_temporary_parent = False
            row.sync_status = "synced"
            row.synced_at = site.cache_synced_at or datetime.now(timezone.utc)
            by_external[(menu_type, external_id.casefold())] = row
            by_path[(menu_type, path)] = row
            result[path] = row
            walk(menu_children(raw), menu_type, row)

    cached = site.default_menu if isinstance(site.default_menu, dict) else {}
    for menu_type in ("header", "footer"):
        items = cached.get(menu_type)
        if isinstance(items, list):
            walk(items, menu_type)
    db.flush()
    return result


def ensure_blog(db, site: models.Site, sections: dict[str, models.Section]) -> models.Section:
    guides = sections["/guides/"]
    blog = db.scalar(select(models.Section).where(
        models.Section.site_id == site.id,
        models.Section.menu_type == "header",
        models.Section.path == "/blog/",
        models.Section.sync_status != "external_deleted",
    ))
    if blog is None:
        blog = models.Section(
            site_id=site.id,
            external_id=f"blog-{uuid.uuid4().hex[:10]}",
            name="Blog",
            path="/blog/",
            menu_type="header",
        )
        db.add(blog)
    blog.name = "Blog"
    blog.parent_id = guides.id
    blog.is_temporary_parent = False
    blog.sync_status = "pending"
    db.flush()
    sections["/blog/"] = blog
    return blog


async def move_existing_pages(db, site: models.Site, sections: dict[str, models.Section]) -> list[dict]:
    results = []
    for item_id, (section_path, mode) in PLACEMENTS.items():
        item = db.get(models.ContentItem, item_id)
        if not item or item.site_id != site.id:
            raise ValueError(f"Content item is missing from project: {item_id}")
        old_slug = normalized_slug(item.slug)
        section = sections[section_path]
        source_json = copy.deepcopy(item.generated_json)
        item.section_id = section.id
        item.section_content_mode = mode
        item.section_source_slug = old_slug
        new_slug = apply_content_section_slug(item, section)
        if old_slug != new_slug:
            db.add(models.ContentRevision(
                content_item_id=item.id,
                remarks=f"Перенос существующей статьи в релевантный раздел меню {section.name}",
                generate_title=False,
                generation_options={
                    "repair": "menu_content_reconciliation_v1",
                    "old_slug": old_slug,
                    "new_slug": new_slug,
                    "section": section.name,
                    "section_mode": mode,
                },
                source_status=item.status,
                is_published_replacement=True,
                status="completed",
                source_json=source_json,
                revised_json=copy.deepcopy(item.generated_json),
                source_generated_at=item.generated_at,
                revised_generated_at=datetime.now(timezone.utc),
            ))
            item.idempotency_key = f"menu-reconcile-{item.id}-{uuid.uuid4().hex[:10]}"
            item.status = "approved"
            db.commit()
            await publish_item(db, item, site, initiator_username=ACTOR)
            db.refresh(item)
        results.append({"id": item.id, "topic": item.topic, "old": old_slug, "new": new_slug, "status": item.status})
        print({"moved": len(results), **results[-1]}, flush=True)
    return results


def provider_id(db) -> str:
    provider = db.scalar(select(models.AiProvider).where(
        models.AiProvider.is_active.is_(True),
        models.AiProvider.provider_type == "gemini",
    ).order_by(models.AiProvider.updated_at.desc()))
    if not provider:
        raise ValueError("Active Gemini provider not found")
    return provider.id


def create_and_queue_tasks(db, site: models.Site, sections: dict[str, models.Section], blog: models.Section) -> list[str]:
    language = project_content_language(site, "da-DK")
    common = dict(
        geo=site.cache_geo or "da_DK",
        language=language,
        ai_provider_id=provider_id(db),
        include_toc=True,
        include_faq=True,
        generate_title=True,
        menu_types=["header"],
        auto_publish=True,
        save_as_draft=False,
    )
    missing_ids = [sections[path].id for path in sorted(MISSING_MENU_PATHS)]
    landing_task = create_menu_structure_task(db, site, MenuStructureGenerationCreate(
        **common,
        target_words=1800,
        collect_competitors=True,
        section_ids=missing_ids,
        prompt_template=(
            "Write a complete, useful Danish landing page for the exact current menu section. "
            "Follow its breadcrumb and search intent, avoid overlap with sibling sections, and keep every claim accurate."
        ),
    ))

    article_lines = []
    for item_id in PLACEMENTS:
        item = db.get(models.ContentItem, item_id)
        page = (item.generated_json.get("pages") or [{}])[0]
        article_lines.append(f"- {item.topic} | {page.get('slug') or item.slug}")
    blog_prompt = (
        "Create the Danish Blog index page with an original SEO Title of 50-70 characters, a useful Meta Description, "
        "and a clear H1. It must contain exactly 20 visible internal links: one link to every article listed below. "
        "For each entry use a short, informative Danish anchor (normally 2-6 words) and one concise Danish sentence "
        "beside it describing what the reader will learn. Use each exact URL once, do not invent or change URLs. "
        "Group entries into useful thematic sections. Output every linked entry on its own list line exactly as "
        "'- <a href=\"/exact-url/\">Kort anker</a> — Kort beskrivelse.' so the Editor.js renderer receives a real link.\n\n"
        + "\n".join(article_lines)
    )
    blog_task = create_menu_structure_task(db, site, MenuStructureGenerationCreate(
        **common,
        target_words=1200,
        collect_competitors=False,
        section_ids=[blog.id],
        prompt_template=blog_prompt,
    ))

    task_ids = []
    for task in (landing_task, blog_task):
        task.status = "generating"
        for item in task.items:
            item.status = "generation_queued"
            item.generation_progress = 1
            item.generation_error = None
        db.commit()
        run_task_pipeline_job.delay(task.id)
        task_ids.append(task.id)
        print({"queued_task": task.id, "title": task.title, "items": len(task.items)}, flush=True)
    return task_ids


async def run(apply: bool) -> None:
    db = SessionLocal()
    try:
        site = db.scalar(select(models.Site).where(models.Site.name == SITE_NAME))
        if not site:
            raise ValueError(f"Project not found: {SITE_NAME}")
        sections = adopt_menu(db, site)
        blog = ensure_blog(db, site, sections)
        print({
            "site": site.name,
            "canonical_url": site.base_url,
            "language": project_content_language(site, ""),
            "placements": len(PLACEMENTS),
            "new_landing_pages": len(MISSING_MENU_PATHS),
            "new_blog_page": 1,
            "apply": apply,
        }, flush=True)
        if not apply:
            db.rollback()
            return
        db.commit()
        menu_result = await sync_project_menus(db, site, initiator_username=ACTOR)
        print({"menu_sync": menu_result}, flush=True)
        await move_existing_pages(db, site, sections)
        task_ids = create_and_queue_tasks(db, site, sections, blog)
        print({"status": "queued", "task_ids": task_ids}, flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.apply))
