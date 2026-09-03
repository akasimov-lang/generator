from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.indexing import content_indexing_urls, submit_indexing_batch


class FakeResponse:
    status_code = 200
    text = ""

    def json(self) -> dict:
        return {
            "google": {
                "type": "Link",
                "icon": "success",
                "title": "Link Indexing",
                "text": "ID задачи: 1948027. Задача создана успешно!",
            }
        }


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, *, json: dict) -> FakeResponse:
        self.calls.append((url, json))
        return FakeResponse()


class FailedClient:
    def post(self, url: str, *, json: dict) -> FakeResponse:
        raise RuntimeError("indexing unavailable")


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def make_published_item(db: Session, site: models.Site, slug: str, key: str) -> models.ContentItem:
    task = models.GenerationTask(title=key, site_id=site.id, geo="PL", language="pl", topics_count=1)
    db.add(task)
    db.flush()
    item = models.ContentItem(
        task=task,
        site_id=site.id,
        topic=key,
        slug=slug,
        generated_json={"pages": []},
        status="published",
        published_at=datetime.now(timezone.utc),
        indexing_status="queued",
        idempotency_key=key,
    )
    db.add(item)
    db.commit()
    return item


def test_content_indexing_urls_use_main_project_domain() -> None:
    with make_session() as db:
        site = models.Site(
            name="project-name.example",
            base_url="https://old-domain.example",
            cache_canon="main-project.example",
            publication_endpoint="https://old-domain.example/api/content",
        )
        db.add(site)
        db.flush()
        item = make_published_item(db, site, "/casino/review/", "url-test")
        item.published_url = "https://other-host.example/casino/review/"

        assert content_indexing_urls(site, [item]) == [
            "https://main-project.example/",
            "https://main-project.example/casino/review/",
        ]


def test_successful_indexing_saves_task_id_and_log() -> None:
    with make_session() as db:
        site = models.Site(
            name="indexing.example",
            base_url="https://indexing.example",
            cache_canon="indexing.example",
            publication_endpoint="https://indexing.example/api/content",
        )
        db.add(site)
        db.flush()
        first = make_published_item(db, site, "/first/", "first-index")
        second = make_published_item(db, site, "/second/", "second-index")
        client = FakeClient()

        task_id = submit_indexing_batch(db, site, [first, second], client=client)

        assert task_id == "1948027"
        assert client.calls[0][1] == {
            "domains": [
                "https://indexing.example/",
                "https://indexing.example/first/",
                "https://indexing.example/second/",
            ],
            "engines": ["google"],
        }
        db.refresh(first)
        db.refresh(second)
        assert first.indexing_status == "submitted"
        assert first.indexing_task_id == "1948027"
        assert second.indexing_task_id == "1948027"
        log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.content_item_id == first.id))
        assert log is not None
        assert log.request_payload["action"] == "google_indexing"


def test_indexing_failure_does_not_undo_publication() -> None:
    with make_session() as db:
        site = models.Site(
            name="failed-indexing.example",
            base_url="https://failed-indexing.example",
            publication_endpoint="https://failed-indexing.example/api/content",
        )
        db.add(site)
        db.flush()
        item = make_published_item(db, site, "/published-page/", "failed-index")

        assert submit_indexing_batch(db, site, [item], client=FailedClient()) is None

        db.refresh(item)
        assert item.status == "published"
        assert item.published_at is not None
        assert item.indexing_status == "failed"
        assert item.indexing_task_id is None
        assert "indexing unavailable" in (item.indexing_error or "")
