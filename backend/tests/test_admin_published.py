from datetime import datetime, timezone

from sqlalchemy import select

from app import models
from app.published_content import article_characters
from app.security import require_auth
from test_api_serialization import make_client


def add_items(db):
    site = db.scalar(select(models.Site))
    task = models.GenerationTask(site_id=site.id, title="Task", geo="DE", language="de", created_by_user_id="admin-id", archived_at=datetime.now(timezone.utc))
    db.add(task)
    db.flush()
    for status in ("published", "generated", "publication_pending_confirmation", "deleted"):
        db.add(models.ContentItem(task_id=task.id, site_id=site.id, topic="Topic", slug=f"/{status}/", status=status,
            generated_json={"pages": [{"title": "Actual SEO title", "description": "not counted", "content": {"blocks": [{"type": "paragraph", "data": {"text": "Hello <b>world</b>!"}}]}}]},
            idempotency_key=status, published_at=datetime.now(timezone.utc), publication_author="publisher",
            indexing_status="submitted", indexing_task_id="index-123"))
    db.commit()
    return site.id


def test_admin_published_has_metrics_authors_indexing_and_archived_task():
    client, sessions = make_client()
    with sessions() as db:
        site_id = add_items(db)
    response = client.get("/api/admin/published")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    row = result["items"][0]
    assert row["site_id"] == site_id and row["geo"] == "DE"
    assert row["title"] == "Actual SEO title" and row["characters"] == len("Hello world!")
    assert row["generation_author"] == "admin" and row["publication_author"] == "publisher"
    assert row["indexing_task_id"] == "index-123" and row["published_at"]
    assert client.get("/api/admin/published?offset=1&limit=1").json()["items"] == []
    assert client.get("/api/admin/published?site_id=missing").json()["total"] == 0
    assert client.get("/api/admin/published?offset=-1").status_code == 422


def test_admin_published_denies_regular_users():
    client, _ = make_client()
    client.app.dependency_overrides[require_auth] = lambda: {"id": "user", "username": "editor", "is_admin": False}
    assert client.get("/api/admin/published").status_code == 403


def test_legacy_author_requires_successful_publication_log():
    client, sessions = make_client()
    with sessions() as db:
        add_items(db)
        item = db.scalar(select(models.ContentItem).where(models.ContentItem.status == "published"))
        item.publication_author = None
        db.add(models.PublicationLog(content_item_id=item.id, endpoint_url="https://example.test", response_status=500,
            request_payload={"requested_by": {"username": "wrong"}}))
        db.commit()
        assert client.get("/api/admin/published").json()["items"][0]["publication_author"] is None
        db.add(models.PublicationLog(content_item_id=item.id, endpoint_url="https://example.test", response_status=200,
            request_payload={"requested_by": {"username": "actual-publisher"}}))
        db.commit()
    assert client.get("/api/admin/published").json()["items"][0]["publication_author"] == "actual-publisher"


def test_character_count_includes_nested_lists_and_faq_without_metadata():
    payload = {"pages": [{"title": "Ignored", "content": {"blocks": [
        {"type": "list", "data": {"style": "ordered", "items": [{"content": "One", "meta": {"id": 9}, "items": [{"content": "Two", "items": []}]}]}},
        {"type": "faq", "data": [{"question": "Why?", "answer": "A &amp; B"}]},
    ]}}]}
    assert article_characters(payload) == len("One Two Why? A & B")
