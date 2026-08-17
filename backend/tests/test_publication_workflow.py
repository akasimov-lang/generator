import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.schemas import PublicationCampaignCreate
from app.services import (
    approve_and_schedule_item,
    build_campaign_publication_bundle,
    publish_item,
    refresh_campaign_status,
    schedule_campaign,
    update_campaign_status,
    validate_content_for_publication,
)


def valid_payload() -> dict:
    return {
        "menu": {"header": [], "footer": []},
        "pages": [
            {
                "slug": "/test/",
                "title": "Test page",
                "content": {
                    "blocks": [
                        {"type": "header", "data": {"text": "Test page", "level": 1}},
                        {"type": "header", "data": {"text": "Details", "level": 2}},
                        {"type": "paragraph", "data": {"text": "Reviewed publication content."}},
                    ]
                },
            }
        ],
    }


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSession() as session:
        yield session


def make_content(db: Session, *, status: str = "approved", payload: dict | None = None) -> tuple[models.Site, models.ContentItem]:
    site = models.Site(
        name="Test site",
        base_url="https://example.test",
        publication_endpoint="https://example.test/api/pages",
        payload_mode="simple_page",
    )
    db.add(site)
    db.flush()
    task = models.GenerationTask(title="Test task", site_id=site.id, geo="DE", language="de", topics_count=1)
    item = models.ContentItem(
        task=task,
        site_id=site.id,
        topic="Test topic",
        slug="/test/",
        generated_json=payload if payload is not None else valid_payload(),
        status=status,
        idempotency_key=f"test-{status}-{id(site)}",
    )
    db.add_all([task, item])
    db.commit()
    return site, item


def test_publication_validation_rejects_invalid_payload_and_state(db: Session) -> None:
    _, invalid_payload_item = make_content(db, status="generated", payload={"pages": []})
    with pytest.raises(ValueError, match="Content validation failed"):
        validate_content_for_publication(invalid_payload_item)

    _, draft_item = make_content(db, status="draft")
    with pytest.raises(ValueError, match="cannot be approved or published"):
        validate_content_for_publication(draft_item)


def test_campaign_pause_resume_and_stop_updates_queued_content(db: Session) -> None:
    site, item = make_content(db)
    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Daily publication",
            site_id=site.id,
            content_item_ids=[item.id],
            start_at=datetime.now(timezone.utc),
            interval_minutes=720,
            items_per_run=1,
        ),
    )

    assert campaign.status == "active"
    assert item.status == "scheduled"
    assert item.publication_campaign_id == campaign.id

    update_campaign_status(db, campaign, "pause")
    assert campaign.status == "paused"
    assert item.status == "publication_paused"

    update_campaign_status(db, campaign, "resume")
    assert campaign.status == "active"
    assert item.status == "scheduled"

    update_campaign_status(db, campaign, "stop")
    assert campaign.status == "stopped"
    assert item.status == "approved"
    assert item.scheduled_at is None


def test_campaign_preserves_topic_order_and_alternates_menu_sections(db: Session) -> None:
    site = models.Site(
        name="Round robin site",
        base_url="https://round-robin.test",
        publication_endpoint="https://round-robin.test/api/pages",
        payload_mode="simple_page",
    )
    db.add(site)
    db.flush()
    task = models.GenerationTask(title="Ordered topics", site_id=site.id, geo="DK", language="da", topics_count=4)
    first_section = models.Section(site=site, external_id="casino", name="Casino", path="/casino/")
    second_section = models.Section(site=site, external_id="bonus", name="Bonus", path="/bonus/")
    db.add_all([task, first_section, second_section])
    db.flush()
    created_at = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    items = [
        models.ContentItem(task=task, site_id=site.id, section_id=first_section.id, topic="Casino 1", slug="/casino-1/", generated_json=valid_payload(), status="approved", idempotency_key="casino-1", created_at=created_at),
        models.ContentItem(task=task, site_id=site.id, section_id=first_section.id, topic="Casino 2", slug="/casino-2/", generated_json=valid_payload(), status="approved", idempotency_key="casino-2", created_at=created_at + timedelta(seconds=1)),
        models.ContentItem(task=task, site_id=site.id, section_id=second_section.id, topic="Bonus 1", slug="/bonus-1/", generated_json=valid_payload(), status="approved", idempotency_key="bonus-1", created_at=created_at + timedelta(seconds=2)),
        models.ContentItem(task=task, site_id=site.id, section_id=second_section.id, topic="Bonus 2", slug="/bonus-2/", generated_json=valid_payload(), status="approved", idempotency_key="bonus-2", created_at=created_at + timedelta(seconds=3)),
    ]
    db.add_all(items)
    db.commit()
    start_at = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)

    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Alternating menu sections",
            site_id=site.id,
            content_item_ids=[item.id for item in reversed(items)],
            start_at=start_at,
            interval_minutes=1440,
            items_per_run=1,
        ),
    )

    queued = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.publication_campaign_id == campaign.id)
        .order_by(models.ContentItem.scheduled_at.asc())
    ).all()
    assert [item.topic for item in queued] == ["Casino 1", "Bonus 1", "Casino 2", "Bonus 2"]


def test_approve_and_schedule_item_creates_immediate_campaign(db: Session) -> None:
    site, item = make_content(db, status="generated")
    section = models.Section(site_id=site.id, external_id="news", name="News", path="/news/")
    db.add(section)
    db.flush()
    item.section_id = section.id
    db.commit()

    campaign = approve_and_schedule_item(db, item)

    assert campaign.status == "active"
    assert item.status == "scheduled"
    assert item.publication_campaign_id == campaign.id
    assert item.scheduled_at is not None


def test_invalid_payload_is_not_sent_by_publication_worker(db: Session) -> None:
    site, item = make_content(db, status="scheduled", payload={"pages": []})

    asyncio.run(publish_item(db, item, site))

    assert item.status == "publication_failed"
    log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.content_item_id == item.id))
    assert log is not None
    assert log.response_status is None
    assert "Content validation failed" in (log.error_message or "")
    assert db.scalar(select(func.count(models.PublicationLog.id))) == 1


def test_campaign_bundle_contains_project_actor_and_ordered_changes(db: Session) -> None:
    site, item = make_content(db)
    site.cache_canon = "main.example.test"
    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Bulk publication",
            site_id=site.id,
            content_item_ids=[item.id],
            start_at=datetime.now(timezone.utc),
            interval_minutes=1440,
            items_per_run=1,
        ),
    )

    payload = build_campaign_publication_bundle(
        db,
        campaign,
        site,
        [item],
        {"id": "user-1", "username": "Арсений"},
    )

    assert payload["action"] == "campaign_publish_all"
    assert payload["requested_by"] == {"id": "user-1", "username": "Арсений"}
    assert payload["project"]["name"] == "Test site"
    assert payload["project"]["main"] == "main.example.test"
    assert payload["campaign"]["id"] == campaign.id
    assert payload["changes"][0]["content_item_id"] == item.id
    assert payload["changes"][0]["payload"]["pages"][0]["slug"] == "/test/"


def test_campaign_completion_time_is_fixed_when_queue_finishes(db: Session) -> None:
    site, item = make_content(db)
    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Finished campaign",
            site_id=site.id,
            content_item_ids=[item.id],
            start_at=datetime.now(timezone.utc),
            interval_minutes=1440,
            items_per_run=1,
        ),
    )
    item.status = "published"
    item.published_at = datetime.now(timezone.utc)
    refresh_campaign_status(db, campaign.id)

    assert campaign.status == "completed"
    assert campaign.completed_at is not None
