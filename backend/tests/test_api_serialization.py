from __future__ import annotations

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api import router
from app.db import Base, get_db
from app.security import require_auth


def make_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        site = models.Site(
            name="DE обзорник",
            base_url="http://example.test",
            publication_endpoint="http://example.test/api/pages",
            payload_mode="simple_page",
        )
        db.add(site)
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
    assert overview_response.status_code == 200
    assert overview_response.json()["site"]["id"] == site_id
    assert tasks_response.status_code == 200
    assert tasks_response.json() == []
    assert content_response.status_code == 200
    assert content_response.json() == []
