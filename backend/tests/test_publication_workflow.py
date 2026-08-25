import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app import api as api_module
from app import project_cache as project_cache_module
from app import services as service_module
from app.db import Base
from app.schemas import PublicationCampaignCreate
from app.services import (
    approve_and_schedule_item,
    build_project_menu_payload,
    build_project_page_payload,
    build_nested_page_slug,
    build_campaign_publication_bundle,
    publish_item,
    delete_published_item,
    refresh_campaign_status,
    reschedule_campaign,
    schedule_campaign,
    sync_project_menus,
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


def test_delete_published_item_targets_current_server_and_waits_for_cache_confirmation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    site, item = make_content(db, status="published")
    site.name = "manual-delete.example"
    site.cache_server_ip = "stale"
    item.published_at = datetime.now(timezone.utc)
    db.add(models.PublicationLog(
        content_item_id=item.id,
        endpoint_url="https://old.example/projects/create",
        request_payload={"id": 1725000000000, "page": {"id": "published-page-id", "slug": "/test/"}},
        response_status=201,
        response_body={"ok": True},
    ))
    db.commit()
    calls: list[dict] = []

    def fake_refresh_server_id(_db: Session, target_site: models.Site) -> str:
        target_site.cache_server_ip = "camel"
        _db.commit()
        return "camel"

    class FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json() -> dict:
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict, headers: dict | None = None):
            calls.append({"url": url, "json": json, "headers": headers or {}})
            return FakeResponse()

    monkeypatch.setattr(service_module, "refresh_project_server_id", fake_refresh_server_id)
    monkeypatch.setattr(service_module, "refresh_project_server_token", lambda client: asyncio.sleep(0, result="fresh-token"))
    monkeypatch.setattr(service_module.httpx, "AsyncClient", FakeAsyncClient)

    asyncio.run(delete_published_item(db, item, site, initiator_username="editor"))

    assert item.status == "deletion_pending"
    assert item.deletion_requested_at is not None
    assert item.deletion_confirmed_at is None
    assert calls[0]["url"] == "https://camel.slf-hostesting.com/projects/delete"
    assert calls[0]["json"]["folder"] == "manual-delete.example"
    assert calls[0]["json"]["id"] == 1725000000000
    assert calls[0]["json"]["pageId"] == "published-page-id"
    assert calls[0]["json"]["slug"] == "/test/"
    assert calls[0]["headers"]["Authorization"] == "Bearer fresh-token"
    deletion_log = db.scalar(
        select(models.PublicationLog)
        .where(models.PublicationLog.content_item_id == item.id)
        .order_by(models.PublicationLog.created_at.desc())
    )
    assert deletion_log.request_payload["action"] == "content_delete"
    assert deletion_log.request_payload["token"] == "[redacted]"


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


def test_campaign_accepts_generated_content_as_ready_for_publication(db: Session) -> None:
    site, item = make_content(db, status="generated")
    section = models.Section(site=site, external_id="guides", name="Guides", path="/guides/")
    db.add(section)
    db.flush()
    item.section_id = section.id
    db.commit()

    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Generated content publication",
            site_id=site.id,
            content_item_ids=[item.id],
            start_at=datetime.now(timezone.utc),
            interval_minutes=1440,
            items_per_run=1,
        ),
    )

    assert campaign.status == "active"
    assert item.status == "scheduled"
    assert item.publication_campaign_id == campaign.id
    assert item.scheduled_at is not None


def test_campaign_mode_change_replaces_remaining_queue_and_counts_today_publications(db: Session) -> None:
    site = models.Site(name="Reschedule site", base_url="https://reschedule.test", publication_endpoint="https://reschedule.test/api/pages", payload_mode="simple_page")
    db.add(site)
    db.flush()
    task = models.GenerationTask(title="Reschedule topics", site_id=site.id, geo="DK", language="da", topics_count=5)
    section = models.Section(site=site, external_id="guides", name="Guides", path="/guides/")
    db.add_all([task, section])
    db.flush()
    items = [
        models.ContentItem(task=task, site_id=site.id, section_id=section.id, topic=f"Topic {index}", slug=f"/topic-{index}/", generated_json=valid_payload(), status="approved", idempotency_key=f"reschedule-{index}")
        for index in range(1, 6)
    ]
    db.add_all(items)
    db.commit()
    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Change publication mode",
            site_id=site.id,
            content_item_ids=[item.id for item in items],
            start_at=datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc),
            interval_minutes=1440,
            items_per_run=1,
        ),
    )
    items[0].status = "published"
    items[0].published_at = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)
    items[1].status = "published"
    items[1].published_at = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)
    old_schedule = [item.scheduled_at for item in items[2:]]
    db.commit()

    reschedule_campaign(db, campaign, 3, now=datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc))

    assert campaign.interval_minutes == 420
    assert items[0].published_at == datetime(2026, 8, 16, 8, 0)
    assert items[1].published_at == datetime(2026, 8, 17, 8, 0)
    assert [item.scheduled_at for item in items[2:]] != old_schedule
    assert [item.scheduled_at for item in items[2:]] == [
        datetime(2026, 8, 17, 15, 0),
        datetime(2026, 8, 17, 22, 0),
        datetime(2026, 8, 18, 5, 0),
    ]


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


def test_project_menu_payload_appends_new_items_after_existing_order(db: Session) -> None:
    site = models.Site(
        name="nauchi52.ru",
        base_url="https://nauchi52.ru",
        publication_endpoint="https://legacy.example/content",
        cache_server_ip="crab",
        default_menu={
            "header": [
                {"id": 1787216707470 + index, "title": f"Existing {index + 1}", "slug": f"/existing-{index + 1}/", "order": index}
                for index in range(6)
            ],
            "footer": [],
        },
    )
    db.add(site)
    db.flush()
    section = models.Section(site=site, external_id="test", name="test", path="/test/", menu_type="header", sync_status="pending")
    db.add(section)
    db.commit()

    payload = build_project_menu_payload(db, site, "header", datetime(2026, 8, 20, 9, 17, 4, 551000, tzinfo=timezone.utc))

    assert payload["type"] == "header"
    assert payload["folder"] == "nauchi52.ru"
    assert payload["list"][-1] == {
        "id": 1787217424557,
        "title": "test",
        "slug": "/test/",
        "order": 7,
    }


def test_project_page_payload_matches_receiver_dto(db: Session) -> None:
    site, item = make_content(db)
    site.name = "nauchi52.ru"
    moment = datetime(2026, 8, 20, 9, 17, 4, 551000, tzinfo=timezone.utc)

    payload = build_project_page_payload(item, site, "fresh-token", moment)

    assert payload["folder"] == "nauchi52.ru"
    assert payload["id"] == 1787217424551
    assert isinstance(payload["id"], int)
    assert payload["page"]["id"] == "Thu Aug 20 2026 12:17:04 GMT+0300 (Москва, стандартное время)"
    assert payload["page"]["title"] == "Test page"
    assert payload["page"]["slug"] == "/test/"
    assert payload["page"]["publishedTime"] == "2026-08-20 09:17:04"
    assert payload["page"]["content"]["time"] == "2026-08-20T09:17:04.551Z"
    assert payload["token"] == "fresh-token"
    assert payload["dateTime"] == "2026-08-20 09:17:04"


def test_nested_page_slug_uses_full_parent_path_without_duplication() -> None:
    assert build_nested_page_slug("/best-casinos/", "/online-casino-bonus-terms-in/") == "/best-casinos/online-casino-bonus-terms-in/"
    assert build_nested_page_slug("/best-casinos/", "/best-casinos/online-casino-bonus-terms-in/") == "/best-casinos/online-casino-bonus-terms-in/"
    assert build_nested_page_slug("/casino/guides/", "/article/") == "/casino/guides/article/"


def test_project_page_payload_uses_assigned_menu_path(db: Session) -> None:
    site, item = make_content(db)
    section = models.Section(site=site, external_id="best-casinos", name="Best Casinos", path="/best-casinos/")
    db.add(section)
    db.flush()
    item.section_id = section.id

    payload = build_project_page_payload(item, site, "fresh-token", section=section)

    assert payload["page"]["slug"] == "/best-casinos/test/"


def test_project_page_payload_can_update_the_menu_page_itself(db: Session) -> None:
    site, item = make_content(db)
    section = models.Section(site=site, external_id="best-casinos", name="Best Casinos", path="/best-casinos/")
    db.add(section)
    db.flush()
    item.section_id = section.id
    item.section_content_mode = "menu_page"
    item.section_source_slug = item.slug

    payload = build_project_page_payload(item, site, "fresh-token", section=section)

    assert payload["page"]["slug"] == "/best-casinos/"


def test_project_server_requests_refresh_token_and_store_status_codes(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    server_lookups: list[list[str] | None] = []
    fake_settings = SimpleNamespace(
        project_cache_url="https://auth.example",
        project_cache_username="anton",
        project_cache_password="test-password",
        alfan_url="slf-hostesting.com",
    )
    monkeypatch.setattr(project_cache_module, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(service_module, "get_settings", lambda: fake_settings)

    def fake_fetch_project_cache(names: list[str] | None = None) -> list[dict]:
        server_lookups.append(names)
        return [{"name": "nauchi52.ru", "serverIp": "bear"}]

    monkeypatch.setattr(project_cache_module, "fetch_project_cache", fake_fetch_project_cache)
    monkeypatch.setattr(
        service_module,
        "fetch_project_template_capabilities",
        lambda site, force=False: {
            "header_menu_rendered": True,
            "header_menu_nested": True,
            "footer_menu_rendered": True,
            "footer_menu_nested": True,
        },
    )

    class FakeResponse:
        def __init__(self, status_code: int, body: dict):
            self.status_code = status_code
            self._body = body
            self.headers = {"content-type": "application/json"}
            self.text = ""

        def json(self) -> dict:
            return self._body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict, headers: dict | None = None):
            calls.append({"url": url, "json": json, "headers": headers or {}})
            if url.endswith("/auth/login"):
                return FakeResponse(200, {"token": "fresh-token"})
            return FakeResponse(201, {"ok": True})

    monkeypatch.setattr(service_module.httpx, "AsyncClient", FakeAsyncClient)
    site, item = make_content(db)
    site.name = "nauchi52.ru"
    site.cache_server_ip = "stale-server"
    section = models.Section(site=site, external_id="test", name="test", path="/test/", menu_type="header", sync_status="pending")
    db.add(section)
    db.commit()

    menu_result = asyncio.run(sync_project_menus(db, site))
    asyncio.run(publish_item(db, item, site))

    auth_calls = [call for call in calls if call["url"].endswith("/auth/login")]
    menu_calls = [call for call in calls if call["url"].endswith("/projects/menu")]
    page_calls = [call for call in calls if call["url"].endswith("/projects/create")]
    assert [call["url"].rsplit("/", 1)[-1] for call in calls] == [
        "login",
        "menu",
        "login",
        "menu",
        "login",
        "create",
    ]
    assert len(auth_calls) == 3
    assert len(menu_calls) == 2
    assert len(page_calls) == 1
    assert server_lookups == [["nauchi52.ru"], ["nauchi52.ru"]]
    assert site.cache_server_ip == "bear"
    assert all(call["url"].startswith("https://bear.slf-hostesting.com/") for call in [*menu_calls, *page_calls])
    assert all(call["headers"]["Authorization"] == "Bearer fresh-token" for call in [*menu_calls, *page_calls])
    assert all("token" not in call["json"] for call in menu_calls)
    assert page_calls[0]["json"]["token"] == "fresh-token"
    assert menu_result["status_codes"] == [201, 201]
    assert menu_result["last_status_code"] == 201
    assert section.sync_status == "synced"
    assert item.status == "published"
    assert page_calls[0]["json"]["id"] != page_calls[0]["json"]["page"]["id"]
    page_log = db.scalar(
        select(models.PublicationLog)
        .where(models.PublicationLog.content_item_id == item.id)
        .order_by(models.PublicationLog.created_at.desc())
    )
    assert page_log is not None
    assert page_log.endpoint_url == "https://bear.slf-hostesting.com/projects/create"
    assert page_log.response_status == 201
    assert page_log.request_payload["token"] == "[redacted]"


def test_menu_sync_blocks_nested_items_when_template_has_one_level(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    site, _ = make_content(db)
    site.cache_server_ip = "bear"
    parent = models.Section(
        site=site,
        external_id="parent",
        name="Parent",
        path="/parent/",
        menu_type="header",
        sync_status="synced",
    )
    db.add(parent)
    db.flush()
    child = models.Section(
        site=site,
        external_id="child",
        name="Child",
        path="/parent/child/",
        menu_type="header",
        parent_id=parent.id,
        sync_status="pending",
    )
    db.add(child)
    db.commit()
    monkeypatch.setattr(service_module, "refresh_project_server_id", lambda db, site: "bear")
    monkeypatch.setattr(
        service_module,
        "fetch_project_template_capabilities",
        lambda site, force=False: {
            "header_menu_rendered": True,
            "header_menu_nested": False,
            "footer_menu_rendered": True,
            "footer_menu_nested": False,
        },
    )

    with pytest.raises(project_cache_module.ProjectCacheError, match="веб-разработчику"):
        asyncio.run(sync_project_menus(db, site))


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
    assert payload["project"]["server_id"] == site.cache_server_ip
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


def test_manual_publication_bypasses_queue_and_records_actual_time(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    site, item = make_content(db)
    section = models.Section(site=site, external_id="guides", name="Guides", path="/guides/")
    db.add(section)
    db.flush()
    item.section_id = section.id
    campaign = schedule_campaign(
        db,
        PublicationCampaignCreate(
            name="Queued publication",
            site_id=site.id,
            content_item_ids=[item.id],
            start_at=datetime.now(timezone.utc) + timedelta(days=5),
            interval_minutes=1440,
            items_per_run=1,
        ),
    )
    planned_at = item.scheduled_at
    actual_at = datetime.now(timezone.utc)

    async def fake_publish_item(
        session: Session,
        queued_item: models.ContentItem,
        queued_site: models.Site,
        initiator_username: str | None = None,
    ) -> None:
        assert queued_item.status == "scheduled"
        assert queued_item.scheduled_at == planned_at
        assert queued_site.id == site.id
        assert initiator_username == "admin"
        queued_item.status = "published"
        queued_item.published_at = actual_at
        queued_item.published_url = "https://example.test/guides/test/"
        session.commit()

    monkeypatch.setattr(api_module, "publish_item", fake_publish_item)

    result = asyncio.run(api_module.publish_content_immediately(item.id, {"username": "admin"}, db))

    assert result.status == "published"
    assert result.scheduled_at is None
    assert result.published_at is not None
    assert result.published_at.replace(tzinfo=timezone.utc) == actual_at.replace(tzinfo=timezone.utc)
    assert result.published_url == "https://example.test/guides/test/"
    db.refresh(campaign)
    assert campaign.status == "completed"
    assert campaign.completed_at is not None
