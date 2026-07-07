import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.schemas import GenerationTaskCreate, PublicationCampaignCreate


def count_words(payload: dict) -> int:
    content = payload.get("content", {})
    chunks: list[str] = []
    chunks.append(str(content.get("intro", "")))
    for section in content.get("sections", []):
        chunks.append(str(section.get("body", "")))
    for faq in content.get("faq", []):
        chunks.append(str(faq.get("answer", "")))
    return len(re.findall(r"\b[\w'-]+\b", " ".join(chunks), flags=re.UNICODE))


def build_stub_content(topic: str, geo: str, language: str, target_words: int | None = None) -> dict:
    title = topic.strip().title()
    intro = (
        f"This draft was generated for the topic '{topic}' with geo {geo} and language {language}. "
        "It is ready for editorial review before publication."
    )
    return {
        "content": {
            "meta_title": title,
            "meta_description": f"Editorial page about {topic} for {geo}.",
            "h1": title,
            "intro": intro,
            "sections": [
                {
                    "h2": f"Overview of {title}",
                    "body": (
                        f"{title} requires a clear structure, practical details and local context. "
                        f"The final copy should match the selected geo, language and site section."
                    ),
                },
                {
                    "h2": "Key points",
                    "body": (
                        "The article should be useful for users, internally consistent and safe to publish. "
                        "Editors can adjust the tone, facts and calls to action before approval."
                    ),
                },
            ],
            "faq": [
                {
                    "question": f"What should readers know about {topic}?",
                    "answer": (
                        "They should get a concise answer, enough context for a decision and links to relevant pages."
                    ),
                }
            ],
        },
        "generation_meta": {
            "geo": geo,
            "language": language,
            "target_words": target_words,
            "generator": "stub",
        },
    }


def create_generation_task(db: Session, payload: GenerationTaskCreate) -> models.GenerationTask:
    clean_topics = [topic.strip() for topic in payload.topics if topic.strip()]
    task = models.GenerationTask(
        title=payload.title,
        site_id=payload.site_id,
        section_id=payload.section_id,
        ai_provider_id=payload.ai_provider_id,
        geo=payload.geo,
        language=payload.language,
        topics_count=len(clean_topics),
        target_words=payload.target_words,
        prompt_template=payload.prompt_template,
        status="created",
    )
    db.add(task)
    db.flush()

    for index, topic in enumerate(clean_topics, start=1):
        generated_json = build_stub_content(topic, payload.geo, payload.language, payload.target_words)
        generated_json["geo"] = payload.geo
        generated_json["language"] = payload.language
        generated_json["slug"] = slugify(topic)
        generated_json["section_id"] = payload.section_id
        item = models.ContentItem(
            task_id=task.id,
            topic=topic,
            slug=generated_json["slug"],
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
        if item and item.status == "approved":
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
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(site.publication_endpoint, json=item.generated_json, headers=headers)
        response_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text}
        log = models.PublicationLog(
            content_item_id=item.id,
            endpoint_url=site.publication_endpoint,
            request_payload=item.generated_json,
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
                request_payload=item.generated_json,
                error_message=str(exc),
            )
        )
        item.status = "retry_scheduled"
        item.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()

