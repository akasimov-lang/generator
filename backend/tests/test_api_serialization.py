from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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


def test_admin_site_list_includes_projects_not_in_focus() -> None:
    client, TestingSession = make_client()
    with TestingSession() as db:
        db.add(models.Site(
            name="not-in-focus.example",
            base_url="https://not-in-focus.example",
            publication_endpoint="https://not-in-focus.example/api/content",
            project_status="not_in_focus",
        ))
        db.commit()

    response = client.get("/api/sites")

    assert response.status_code == 200
    assert "not-in-focus.example" in {site["name"] for site in response.json()}
