import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api import archive_task, collect_content_competitors, generate_content, get_task, list_archived_tasks, list_tasks, restore_task
from app.db import Base


def test_task_archive_is_admin_only_and_reversible() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        admin = models.User(username="admin", password_hash="hash", is_admin=True, is_active=True)
        task = models.GenerationTask(title="Archive me", geo="DE", language="de", topics_count=0)
        db.add_all([admin, task])
        db.commit()

        admin_user = {"id": admin.id, "username": admin.username, "is_admin": True}
        regular_user = {"id": "editor-id", "username": "editor", "is_admin": False}

        assert [row.id for row in list_tasks(admin_user, db)] == [task.id]

        assert archive_task(task.id, admin_user, db) == {"status": "archived"}
        assert list_tasks(admin_user, db) == []
        assert [row.id for row in list_archived_tasks(admin_user, db)] == [task.id]

        with pytest.raises(HTTPException) as exc:
            get_task(task.id, regular_user, db)
        assert exc.value.status_code == 404
        assert get_task(task.id, admin_user, db)["task"].id == task.id

        restored = restore_task(task.id, admin_user, db)
        assert restored.archived_at is None
        assert [row.id for row in list_tasks(admin_user, db)] == [task.id]


def test_competitor_collection_is_queued_without_waiting_for_http(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    queued_ids: list[str] = []
    monkeypatch.setattr("app.api.collect_competitor_research_job.delay", queued_ids.append)

    with TestingSession() as db:
        task = models.GenerationTask(title="Research", geo="DE", language="de", topics_count=1)
        item = models.ContentItem(
            task=task,
            topic="Beste Online Casinos Deutschland",
            slug="/beste-online-casinos/",
            generated_json={},
            idempotency_key="queued-research-item",
        )
        db.add(item)
        db.commit()

        response = collect_content_competitors(
            item.id,
            {"id": "admin-id", "username": "admin", "is_admin": True},
            db,
        )

        assert queued_ids == [item.id]
        assert response["status"] == "queued"
        assert response["progress"] == 1


def test_content_generation_is_queued_with_initial_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    queued_ids: list[str] = []
    monkeypatch.setattr("app.api.generate_content_item_job.delay", queued_ids.append)

    with TestingSession() as db:
        task = models.GenerationTask(title="Generate", geo="DE", language="de", topics_count=1)
        item = models.ContentItem(
            task=task,
            topic="Beste Online Casinos Deutschland",
            slug="/beste-online-casinos/",
            generated_json={},
            idempotency_key="queued-generation-item",
        )
        db.add(item)
        db.commit()

        response = generate_content(
            item.id,
            {"id": "admin-id", "username": "admin", "is_admin": True},
            db,
        )

        assert queued_ids == [item.id]
        assert response.status == "generation_queued"
        assert response.generation_progress == 1
