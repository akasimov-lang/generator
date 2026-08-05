import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.schemas import PublicationCampaignCreate
from app.services import (
    publish_item,
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
            interval_minutes=60,
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


def test_invalid_payload_is_not_sent_by_publication_worker(db: Session) -> None:
    site, item = make_content(db, status="scheduled", payload={"pages": []})

    asyncio.run(publish_item(db, item, site))

    assert item.status == "publication_failed"
    log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.content_item_id == item.id))
    assert log is not None
    assert log.response_status is None
    assert "Content validation failed" in (log.error_message or "")
    assert db.scalar(select(func.count(models.PublicationLog.id))) == 1
