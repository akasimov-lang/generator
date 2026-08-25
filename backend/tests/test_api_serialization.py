from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import api as api_module
from app import models
from app.api import router
from app.core.config import get_settings
from app.db import Base, get_db
from app.security import require_auth


def make_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        user = models.User(id="admin-id", username="admin", password_hash="test", is_admin=True, is_active=True)
        site = models.Site(
            name="DE обзорник",
            base_url="http://example.test",
            publication_endpoint="http://example.test/api/pages",
            payload_mode="simple_page",
            cache_server_ip="crab",
        )
        db.add_all([user, site])
        db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def override_get_db() -> Generator[Session, None, None]:
        with TestingSession() as db:
            yield db

    def override_auth() -> dict:
        return {"id": "admin-id", "username": "admin", "is_admin": True}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_auth
    return TestClient(app), TestingSession


def test_orm_list_endpoints_serialize_json() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site_id = db.query(models.Site.id).scalar()

    sites_response = client.get("/api/sites")
    overview_response = client.get(f"/api/sites/{site_id}/overview")
    tasks_response = client.get(f"/api/sites/{site_id}/tasks")
    content_response = client.get(f"/api/sites/{site_id}/content")

    assert sites_response.status_code == 200
    assert sites_response.json()[0]["name"] == "DE обзорник"
    assert sites_response.json()[0]["cache_server_host"] == f"crab.{get_settings().alfan_url}"
    assert overview_response.status_code == 200
    assert overview_response.json()["site"]["id"] == site_id
    assert tasks_response.status_code == 200
    assert tasks_response.json() == []
    assert content_response.status_code == 200
    assert content_response.json() == []


def test_project_content_and_overview_exclude_archived_task_items() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site = db.query(models.Site).one()
        active_task = models.GenerationTask(title="Active", site_id=site.id, geo="CA", language="en", topics_count=1)
        archived_task = models.GenerationTask(
            title="Archived",
            site_id=site.id,
            geo="AU",
            language="en",
            topics_count=1,
            archived_at=datetime.now(timezone.utc),
        )
        active_item = models.ContentItem(
            task=active_task,
            site_id=site.id,
            topic="Current topic",
            slug="/current-topic/",
            generated_json={"pages": []},
            status="generated",
            idempotency_key="active-content-item",
        )
        archived_item = models.ContentItem(
            task=archived_task,
            site_id=site.id,
            topic="Old topic",
            slug="/old-topic/",
            generated_json={"pages": []},
            status="generated",
            idempotency_key="archived-content-item",
        )
        db.add_all([active_task, archived_task, active_item, archived_item])
        db.commit()
        site_id = site.id

    content_response = client.get(f"/api/sites/{site_id}/content")
    overview_response = client.get(f"/api/sites/{site_id}/overview")

    assert content_response.status_code == 200
    assert [item["topic"] for item in content_response.json()] == ["Current topic"]
    assert overview_response.status_code == 200
    assert overview_response.json()["stats"]["generated"] == 1
    assert [item["topic"] for item in overview_response.json()["recent_content"]] == ["Current topic"]


def test_approve_rejects_invalid_payload() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site = db.query(models.Site).one()
        section = models.Section(site_id=site.id, external_id="main", name="Main", path="/")
        db.add(section)
        db.flush()
        task = models.GenerationTask(title="Test", site_id=site.id, geo="DE", language="de", topics_count=1)
        item = models.ContentItem(
            task=task,
            site_id=site.id,
            section_id=section.id,
            topic="Invalid",
            slug="/invalid/",
            generated_json={"pages": []},
            status="generated",
            idempotency_key="invalid-approve",
        )
        db.add_all([task, item])
        db.commit()
        item_id = item.id

    response = client.post(f"/api/content/{item_id}/approve")

    assert response.status_code == 400
    assert "Content validation failed" in response.json()["detail"]


def test_regular_user_can_approve_valid_content_without_menu_item() -> None:
    client, TestingSession = make_client()
    client.app.dependency_overrides[require_auth] = lambda: {
        "id": "regular-user-id",
        "username": "Vitalina",
        "is_admin": False,
    }
    with TestingSession() as db:
        site = db.query(models.Site).one()
        task = models.GenerationTask(title="Test", site_id=site.id, geo="LV", language="lv", topics_count=1)
        item = models.ContentItem(
            task=task,
            site_id=site.id,
            section_id=None,
            topic="Valid",
            slug="/valid/",
            generated_json={
                "pages": [{
                    "slug": "/valid/",
                    "title": "Valid",
                    "content": {"blocks": [
                        {"type": "header", "data": {"text": "Valid", "level": 1}},
                        {"type": "header", "data": {"text": "Details", "level": 2}},
                        {"type": "paragraph", "data": {"text": "Reviewed content."}},
                    ]},
                }],
            },
            status="generated",
            idempotency_key="regular-user-valid-approve",
        )
        db.add_all([task, item])
        db.commit()
        item_id = item.id

    response = client.post(f"/api/content/{item_id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["section_id"] is None


def test_regular_user_can_publish_content(monkeypatch: pytest.MonkeyPatch) -> None:
    client, TestingSession = make_client()
    client.app.dependency_overrides[require_auth] = lambda: {
        "id": "regular-user-id",
        "username": "Vitalina",
        "is_admin": False,
    }
    with TestingSession() as db:
        site = db.query(models.Site).one()
        section = models.Section(site_id=site.id, external_id="main", name="Main", path="/")
        db.add(section)
        db.flush()
        task = models.GenerationTask(title="Test", site_id=site.id, geo="LV", language="lv", topics_count=1)
        item = models.ContentItem(
            task=task,
            site_id=site.id,
            section_id=section.id,
            topic="Publishable",
            slug="/publishable/",
            generated_json={
                "pages": [{
                    "slug": "/publishable/",
                    "title": "Publishable",
                    "content": {"blocks": [
                        {"type": "header", "data": {"text": "Publishable", "level": 1}},
                        {"type": "header", "data": {"text": "Details", "level": 2}},
                        {"type": "paragraph", "data": {"text": "Reviewed content."}},
                    ]},
                }],
            },
            status="approved",
            idempotency_key="regular-user-publish",
        )
        db.add_all([task, item])
        db.commit()
        item_id = item.id

    async def fake_publish_item(db: Session, item: models.ContentItem, site: models.Site, *, initiator_username: str = "system") -> None:
        assert initiator_username == "Vitalina"
        item.status = "published"

    monkeypatch.setattr(api_module, "publish_item", fake_publish_item)

    response = client.post(f"/api/content/{item_id}/publish-immediately")

    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_user_can_manage_personal_favorite_sites() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site_id = db.query(models.Site.id).scalar()

    assert client.get("/api/me/favorite-sites").json() == {"site_ids": []}

    added_response = client.put(f"/api/me/favorite-sites/{site_id}")
    assert added_response.status_code == 200
    assert added_response.json() == {"site_ids": [site_id]}
    assert client.get("/api/me/favorite-sites").json() == {"site_ids": [site_id]}

    removed_response = client.delete(f"/api/me/favorite-sites/{site_id}")
    assert removed_response.status_code == 200
    assert removed_response.json() == {"site_ids": []}


def test_regular_user_site_list_includes_all_project_statuses() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        db.add_all([
            models.Site(
                name="not-in-focus.example",
                base_url="https://not-in-focus.example",
                publication_endpoint="https://not-in-focus.example/api/content",
                project_status="not_in_focus",
            ),
            models.Site(
                name="duplicate.example",
                base_url="https://duplicate.example",
                publication_endpoint="https://duplicate.example/api/content",
                project_status="duplicate",
            ),
        ])
        db.commit()
    client.app.dependency_overrides[require_auth] = lambda: {
        "id": "regular-user-id",
        "username": "regular-user",
        "is_admin": False,
    }

    response = client.get("/api/sites")

    assert response.status_code == 200
    assert {"DE обзорник", "not-in-focus.example", "duplicate.example"} <= {
        site["name"] for site in response.json()
    }


def test_regular_user_can_delete_menu_item_with_unpublished_content() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site = db.query(models.Site).one()
        section = models.Section(
            site_id=site.id,
            external_id="unused-menu-item",
            name="Unused menu item",
            path="/unused-menu-item/",
            menu_type="header",
        )
        db.add(section)
        db.flush()
        task = models.GenerationTask(
            title="Regular user task",
            site_id=site.id,
            section_id=section.id,
            geo="LV",
            language="lv",
            topics_count=1,
        )
        db.add(task)
        db.flush()
        item = models.ContentItem(
            task_id=task.id,
            site_id=site.id,
            section_id=section.id,
            topic="Generated text",
            slug="/unused-menu-item/generated-text/",
            generated_json={"pages": [{"slug": "/unused-menu-item/generated-text/"}]},
            status="generated",
            idempotency_key="regular-user-menu-delete",
            section_source_slug="/generated-text/",
        )
        db.add(item)
        db.commit()
        site_id = site.id
        section_id = section.id
        task_id = task.id
        item_id = item.id

    client.app.dependency_overrides[require_auth] = lambda: {
        "id": "regular-user-id",
        "username": "Vitalina",
        "is_admin": False,
    }

    response = client.delete(f"/api/sites/{site_id}/sections/{section_id}")

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    with TestingSession() as db:
        assert db.get(models.Section, section_id) is None
        assert db.get(models.GenerationTask, task_id).section_id is None
        unassigned_item = db.get(models.ContentItem, item_id)
        assert unassigned_item.section_id is None
        assert unassigned_item.slug == "/generated-text/"
        log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.content_item_id.is_(None)))
        assert log is not None
        assert log.request_payload["action"] == "menu_item_delete"
        assert log.request_payload["username"] == "Vitalina"


def test_regular_user_can_send_menu_item_to_project(monkeypatch: pytest.MonkeyPatch) -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site = db.query(models.Site).one()
        section = models.Section(
            site_id=site.id,
            external_id="footer-contact",
            name="Contact",
            path="/contact/",
            menu_type="footer",
        )
        db.add(section)
        db.commit()
        site_id = site.id
        section_id = section.id

    client.app.dependency_overrides[require_auth] = lambda: {
        "id": "regular-user-id",
        "username": "Vitalina",
        "is_admin": False,
    }
    received: dict[str, object] = {}

    async def fake_sync_project_menus(
        db: Session,
        site: models.Site,
        initiator_username: str | None = None,
        menu_types: tuple[str, ...] = ("header", "footer"),
    ) -> dict:
        received.update(username=initiator_username, menu_types=menu_types, site_id=site.id)
        return {
            "success": True,
            "status_codes": [200],
            "last_status_code": 200,
            "results": [{"type": "footer", "status_code": 200, "success": True}],
        }

    monkeypatch.setattr(api_module, "sync_project_menus", fake_sync_project_menus)

    response = client.post(f"/api/sites/{site_id}/sections/{section_id}/sync")

    assert response.status_code == 200
    assert response.json()["section_id"] == section_id
    assert received == {"username": "Vitalina", "menu_types": ("footer",), "site_id": site_id}


def test_regular_user_can_create_and_manage_generation_tasks() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        site_id = db.query(models.Site.id).scalar()
        user = models.User(id="regular-user-id", username="regular-user", password_hash="test", is_admin=False, is_active=True)
        db.add(user)
        db.commit()
    client.app.dependency_overrides[require_auth] = lambda: {
        "id": "regular-user-id",
        "username": "regular-user",
        "is_admin": False,
    }

    section = client.post(f"/api/sites/{site_id}/sections", json={
        "external_id": "guides",
        "name": "Guides",
        "path": "/guides/",
        "menu_type": "header",
    })
    assert section.status_code == 200

    created = client.post("/api/tasks", json={
        "geo": "DK",
        "language": "da",
        "topics": ["Danske online casinoer"],
        "site_id": site_id,
        "save_as_draft": True,
    })

    assert created.status_code == 200
    task_id = created.json()["id"]
    assert client.get("/api/tasks").status_code == 200
    assert client.delete(f"/api/tasks/{task_id}").status_code == 200
    assert client.get(f"/api/tasks/{task_id}").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/restore").status_code == 200
    assert client.get("/api/publication-content").status_code == 200
    assert client.get("/api/publication-campaigns").status_code == 200
    assert client.get("/api/publication-logs").status_code == 200
    assert client.post("/api/content/missing/publish-now").status_code == 404
