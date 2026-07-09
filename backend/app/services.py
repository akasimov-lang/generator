import copy
import html
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.schemas import GenerationTaskCreate, PublicationCampaignCreate

SIMPLE_PAGE = "simple_page"
FULL_SITE = "full_site"
SITE_DEFAULT = "site_default"
DEFAULT_EDITOR_VERSION = "2.31.0"


def now_payload_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def make_block_id() -> str:
    return uuid.uuid4().hex[:10]


def normalize_slug(topic: str) -> str:
    slug = slugify(topic) or uuid.uuid4().hex[:8]
    return f"/{slug}/"


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def count_words(payload: dict) -> int:
    if "pages" in payload:
        chunks: list[str] = []
        for page in payload.get("pages", []):
            page_content = page.get("content", {}) if isinstance(page, dict) else {}
            for block in page_content.get("blocks", []):
                chunks.extend(extract_block_text(block))
        return len(re.findall(r"\b[\w'-]+\b", clean_text(" ".join(chunks)), flags=re.UNICODE))

    content = payload.get("content", {})
    chunks: list[str] = []
    chunks.append(str(content.get("intro", "")))
    for section in content.get("sections", []):
        chunks.append(str(section.get("body", "")))
    for faq in content.get("faq", []):
        chunks.append(str(faq.get("answer", "")))
    return len(re.findall(r"\b[\w'-]+\b", clean_text(" ".join(chunks)), flags=re.UNICODE))


def extract_block_text(block: dict) -> list[str]:
    data = block.get("data")
    block_type = block.get("type")
    if block_type in {"header", "paragraph"} and isinstance(data, dict):
        return [data.get("text", "")]
    if block_type == "list" and isinstance(data, dict):
        return [str(item) for item in data.get("items", [])]
    if block_type == "table" and isinstance(data, dict):
        return [str(cell) for row in data.get("content", []) for cell in row]
    if block_type == "faq" and isinstance(data, list):
        return [str(item.get("answer", "")) for item in data if isinstance(item, dict)]
    if block_type == "quote" and isinstance(data, dict):
        return [data.get("quote", "")]
    if block_type == "plusMinus" and isinstance(data, dict):
        values = []
        for item in data.get("values", []):
            values.extend([item.get("plus", ""), item.get("minus", "")])
        return values
    return []


def build_stub_content(
    topic: str,
    geo: str,
    language: str,
    target_words: int | None = None,
    site: models.Site | None = None,
    payload_mode: str = SITE_DEFAULT,
    shortcode: str | None = None,
    include_toc: bool = True,
    include_faq: bool = True,
) -> dict:
    resolved_mode = resolve_payload_mode(site, payload_mode)
    page = build_editor_page(
        topic=topic,
        geo=geo,
        language=language,
        target_words=target_words,
        site=site,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    menu = copy.deepcopy(site.default_menu) if site and site.default_menu else {"header": [], "footer": []}
    payload = {
        "menu": menu,
        "pages": [page],
        "generation_meta": {
            "geo": geo,
            "language": language,
            "target_words": target_words,
            "payload_mode": resolved_mode,
            "generator": "stub_editorjs",
        },
    }
    if resolved_mode == FULL_SITE and site and site.showcase_payload:
        payload["casinos"] = site.showcase_payload.get("casinos", site.showcase_payload)
    return payload


def resolve_payload_mode(site: models.Site | None, requested_mode: str) -> str:
    if requested_mode in {SIMPLE_PAGE, FULL_SITE}:
        return requested_mode
    if site and site.payload_mode in {SIMPLE_PAGE, FULL_SITE}:
        return site.payload_mode
    return SIMPLE_PAGE


def build_editor_page(
    topic: str,
    geo: str,
    language: str,
    target_words: int | None,
    site: models.Site | None,
    shortcode: str | None,
    include_toc: bool,
    include_faq: bool,
) -> dict:
    title = topic.strip().title()
    slug = normalize_slug(topic)
    description = f"Useful guide about {topic} for {geo} readers in {language}."
    headings = [
        title,
        f"What to know about {title}",
        f"How to choose the right option in {geo}",
        "Key comparison points",
        "FAQ",
    ]
    blocks: list[dict] = [header_block(headings[0], 1)]
    if include_toc:
        blocks.append(toc_block(headings))
    blocks.extend(
        [
            paragraph_block(
                f"This page is a generated editorial draft for <strong>{html.escape(topic)}</strong>. "
                f"It is prepared for geo {html.escape(geo)} and language {html.escape(language)} and should be reviewed before publication."
            ),
            header_block(headings[1], 2),
            paragraph_block(
                f"The content explains the topic, gives practical context and keeps the structure compatible with the site's Editor.js renderer."
            ),
            header_block(headings[2], 2),
            list_block(
                "unordered",
                [
                    "Check the offer, limits and conditions before publishing.",
                    "Keep local geo and language details consistent across title, H1 and body.",
                    "Use shortcode blocks only when the target site already supports them.",
                ],
            ),
            header_block(headings[3], 2),
            table_block(
                [
                    ["Page topic", title],
                    ["Geo", geo],
                    ["Language", language],
                    ["Target words", str(target_words or "Not specified")],
                ]
            ),
        ]
    )
    if include_faq:
        blocks.extend(
            [
                header_block(headings[4], 2),
                faq_block(
                    [
                        {
                            "question": f"What is this page about?",
                            "answer": f"It is an editorial page about {topic}, prepared for {geo} and {language}.",
                        },
                        {
                            "question": "Can this content be published automatically?",
                            "answer": "It should be validated and approved in the admin panel before the publication worker sends it to the endpoint.",
                        },
                    ]
                ),
            ]
        )
    if shortcode:
        blocks.append(shortcode_block(shortcode))

    published = now_payload_time()
    editor_version = site.editor_version if site and site.editor_version else DEFAULT_EDITOR_VERSION
    banners = site.default_banners if site and site.default_banners is not None else []
    return {
        "id": uuid.uuid4().hex[:8],
        "slug": slug,
        "title": title,
        "publishedTime": published,
        "description": description,
        "updatedTime": published,
        "breadcrumb": title,
        "content": {
            "time": int(datetime.now(timezone.utc).timestamp() * 1000),
            "blocks": blocks,
            "version": editor_version,
        },
        "head": [breadcrumb_schema_block(slug, title)],
        "banners": banners,
    }


def header_block(text: str, level: int) -> dict:
    return {"id": make_block_id(), "type": "header", "data": {"text": text, "level": level}}


def paragraph_block(text: str) -> dict:
    return {"id": make_block_id(), "type": "paragraph", "data": {"text": text}}


def list_block(style: str, items: list[str]) -> dict:
    return {"id": make_block_id(), "type": "list", "data": {"style": style, "items": items}}


def table_block(rows: list[list[str]]) -> dict:
    return {"id": make_block_id(), "type": "table", "data": {"withHeadings": False, "stretched": False, "content": rows}}


def faq_block(items: list[dict]) -> dict:
    return {"id": make_block_id(), "type": "faq", "data": items}


def toc_block(headings: list[str]) -> dict:
    return {"id": make_block_id(), "type": "toc", "data": [{"heading": heading, "checked": True} for heading in headings]}


def shortcode_block(shortcode: str) -> dict:
    return {"id": make_block_id(), "type": "shortcode", "data": {"shortcode": shortcode}}


def breadcrumb_schema_block(slug: str, title: str) -> dict:
    data = {
        "@context": "http://www.schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "item": {"@type": "WebPage", "@id": "/", "name": "Startseite"}},
            {"@type": "ListItem", "position": 2, "item": {"@type": "WebPage", "@id": slug, "name": title}},
        ],
    }
    return {"type": "universal", "data": json.dumps(data, ensure_ascii=False, indent=2)}


def create_generation_task(db: Session, payload: GenerationTaskCreate) -> models.GenerationTask:
    clean_topics = [topic.strip() for topic in payload.topics if topic.strip()]
    task = models.GenerationTask(
        title=payload.title,
        site_id=payload.site_id,
        section_id=payload.section_id,
        ai_provider_id=payload.ai_provider_id,
        geo=payload.geo,
        language=payload.language,
        payload_mode=payload.payload_mode,
        topics_count=len(clean_topics),
        target_words=payload.target_words,
        prompt_template=payload.prompt_template,
        status="created",
    )
    db.add(task)
    db.flush()

    for index, topic in enumerate(clean_topics, start=1):
        site = db.get(models.Site, payload.site_id) if payload.site_id else None
        generated_json = build_stub_content(
            topic,
            payload.geo,
            payload.language,
            payload.target_words,
            site=site,
            payload_mode=payload.payload_mode,
            shortcode=payload.shortcode,
            include_toc=payload.include_toc,
            include_faq=payload.include_faq,
        )
        page = generated_json["pages"][0]
        item = models.ContentItem(
            task_id=task.id,
            site_id=task.site_id,
            topic=topic,
            slug=page["slug"],
            generated_json=generated_json,
            status="draft",
            word_count=count_words(generated_json),
            section_id=payload.section_id,
            idempotency_key=f"{payload.geo.lower()}-{payload.language.lower()}-{slugify(topic)}-{index}-{uuid.uuid4().hex[:8]}",
        )
        db.add(item)

    db.commit()
    db.refresh(task)
    return task


def generate_task_items(db: Session, task: models.GenerationTask) -> models.GenerationTask:
    task.status = "generating"
    db.flush()
    for item in task.items:
        item.status = "generated"
    task.status = "generated"
    db.commit()
    db.refresh(task)
    return task


def schedule_campaign(db: Session, payload: PublicationCampaignCreate) -> models.PublicationCampaign:
    campaign = models.PublicationCampaign(
        name=payload.name,
        site_id=payload.site_id,
        start_at=payload.start_at,
        interval_minutes=payload.interval_minutes,
        items_per_run=payload.items_per_run,
        status="active",
    )
    db.add(campaign)
    for index, item_id in enumerate(payload.content_item_ids):
        item = db.get(models.ContentItem, item_id)
        if item and item.status == "approved" and item.site_id == payload.site_id:
            item.status = "scheduled"
            item.scheduled_at = payload.start_at + timedelta(minutes=payload.interval_minutes * index)
    db.commit()
    db.refresh(campaign)
    return campaign


def get_dashboard(db: Session) -> dict:
    total_tasks = db.scalar(select(func.count(models.GenerationTask.id))) or 0
    generated = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status.in_(["generated", "approved", "scheduled", "published"]))) or 0
    awaiting_approve = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status == "generated")) or 0
    scheduled = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status == "scheduled")) or 0
    published = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status == "published")) or 0
    errors = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status.in_(["publication_failed", "generation_failed"]))) or 0

    next_item = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.status == "scheduled")
        .order_by(models.ContentItem.scheduled_at.asc())
        .limit(1)
    ).first()

    active_tasks = db.scalars(select(models.GenerationTask).order_by(models.GenerationTask.created_at.desc()).limit(6)).all()
    queue = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.status.in_(["scheduled", "publishing"]))
        .order_by(models.ContentItem.scheduled_at.asc())
        .limit(8)
    ).all()
    recent_errors = db.scalars(select(models.PublicationLog).where(models.PublicationLog.error_message.is_not(None)).order_by(models.PublicationLog.created_at.desc()).limit(5)).all()

    return {
        "stats": {
            "total_tasks": total_tasks,
            "generated": generated,
            "awaiting_approve": awaiting_approve,
            "scheduled": scheduled,
            "published": published,
            "errors": errors,
            "next_publication_at": next_item.scheduled_at if next_item else None,
        },
        "active_tasks": [
            {
                "id": task.id,
                "title": task.title,
                "geo": task.geo,
                "language": task.language,
                "topics_count": task.topics_count,
                "status": task.status,
                "created_at": task.created_at,
            }
            for task in active_tasks
        ],
        "publication_queue": [
            {
                "id": item.id,
                "topic": item.topic,
                "status": item.status,
                "scheduled_at": item.scheduled_at,
                "slug": item.slug,
            }
            for item in queue
        ],
        "recent_errors": [
            {
                "id": log.id,
                "error_message": log.error_message,
                "endpoint_url": log.endpoint_url,
                "created_at": log.created_at,
            }
            for log in recent_errors
        ],
    }


async def publish_item(db: Session, item: models.ContentItem, site: models.Site) -> None:
    item.status = "publishing"
    db.commit()
    headers = {"Content-Type": "application/json", "Idempotency-Key": item.idempotency_key}
    if site.api_token:
        headers["Authorization"] = f"Bearer {site.api_token}"

    try:
        request_payload = build_publication_payload(db, item)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(site.publication_endpoint, json=request_payload, headers=headers)
        response_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text}
        log = models.PublicationLog(
            content_item_id=item.id,
            endpoint_url=site.publication_endpoint,
            request_payload=request_payload,
            response_status=response.status_code,
            response_body=response_body,
        )
        db.add(log)
        if response.status_code in (200, 201):
            item.status = "published"
            item.published_at = datetime.now(timezone.utc)
            item.published_url = response_body.get("url")
        elif response.status_code in (429, 500, 502, 503):
            item.status = "retry_scheduled"
            item.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        else:
            item.status = "publication_failed"
        db.commit()
    except Exception as exc:
        db.add(
            models.PublicationLog(
                content_item_id=item.id,
                endpoint_url=site.publication_endpoint,
                request_payload=build_publication_payload(db, item),
                error_message=str(exc),
            )
        )
        item.status = "retry_scheduled"
        item.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()


def build_publication_payload(db: Session, item: models.ContentItem) -> dict:
    payload = copy.deepcopy(item.generated_json)
    if not item.section_id:
        return payload

    section = db.get(models.Section, item.section_id)
    if not section:
        return payload

    publication_target = {
        "section_id": section.external_id,
        "section_name": section.name,
        "section_path": section.path,
    }
    payload["publication_target"] = publication_target
    for page in payload.get("pages", []):
        if isinstance(page, dict):
            page["sectionId"] = section.external_id
            page["sectionPath"] = section.path
    return payload
