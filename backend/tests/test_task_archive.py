import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api import archive_task, collect_content_competitors, generate_content, get_task, list_archived_tasks, list_tasks, regenerate_all_task_content, restore_task, start_task_pipeline, update_content, update_task_section
from app.db import Base
from app.schemas import ContentUpdate, GenerationTaskCreate, GenerationTaskRegenerateAll, GenerationTaskSectionUpdate
from app.services import create_generation_task, run_task_pipeline


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


def test_task_pipeline_is_queued_for_all_mutable_items(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    queued_ids: list[str] = []
    monkeypatch.setattr("app.api.run_task_pipeline_job.delay", queued_ids.append)

    with TestingSession() as db:
        task = models.GenerationTask(title="Pipeline", geo="DE", language="de", topics_count=1, collect_competitors=True)
        item = models.ContentItem(task=task, topic="Test topic", slug="/test/", generated_json={}, idempotency_key="pipeline-item")
        db.add(item)
        db.commit()

        response = start_task_pipeline(task.id, {"id": "admin-id", "username": "admin", "is_admin": True}, db)

        assert queued_ids == [task.id]
        assert response.status == "generating"
        assert item.status == "generation_queued"


def test_regenerate_all_updates_task_options_and_uses_one_queue_job(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    queued_ids: list[str] = []
    monkeypatch.setattr("app.api.generate_task_content_job.delay", queued_ids.append)

    with TestingSession() as db:
        task = models.GenerationTask(title="Regenerate", geo="DK", language="da", topics_count=2)
        mutable_item = models.ContentItem(task=task, topic="Mutable", slug="/mutable/", generated_json={}, status="generated", idempotency_key="regenerate-mutable")
        published_item = models.ContentItem(task=task, topic="Published", slug="/published/", generated_json={}, status="published", idempotency_key="regenerate-published")
        db.add_all([task, mutable_item, published_item])
        db.commit()

        result = regenerate_all_task_content(
            task.id,
            GenerationTaskRegenerateAll(
                prompt_template_name="Prompt v7",
                prompt_template="Write a useful page.",
                include_toc=False,
                include_faq=False,
                collect_competitors=False,
                include_casino_rating=True,
            ),
            {"id": "admin-id", "username": "admin", "is_admin": True},
            db,
        )

        assert queued_ids == [task.id]
        assert result.prompt_template_name == "Prompt v7"
        assert result.include_toc is False
        assert result.include_faq is False
        assert result.include_casino_rating is True
        assert mutable_item.status == "generation_queued"
        assert published_item.status == "published"


def test_generation_task_can_be_saved_as_draft() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        task = create_generation_task(
            db,
            GenerationTaskCreate(
                title="Draft task",
                geo="DK",
                language="da",
                topics=["Danske casinoer"],
                collect_competitors=True,
                save_as_draft=True,
            ),
        )

        assert task.status == "draft"
        assert task.items[0].status == "draft"
        assert task.items[0].competitor_research_status == "queries_ready"


def test_task_menu_section_updates_all_mutable_items() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        site = models.Site(name="menu.example", base_url="https://menu.example", publication_endpoint="https://menu.example/api/content")
        db.add(site)
        db.flush()
        section = models.Section(site=site, external_id="games", name="Games", path="/games/", menu_type="header")
        task = models.GenerationTask(title="Menu task", site_id=site.id, geo="DK", language="da", topics_count=1)
        item = models.ContentItem(task=task, site_id=site.id, topic="Games", slug="/games-guide/", generated_json={}, idempotency_key="task-menu-section")
        db.add_all([section, task, item])
        db.commit()

        updated = update_task_section(task.id, GenerationTaskSectionUpdate(section_id=section.id), None, db)  # type: ignore[arg-type]

        assert updated.section_id == section.id
        assert item.section_id == section.id


def test_content_menu_section_is_reflected_in_generation_task() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        site = models.Site(name="menu.example", base_url="https://menu.example", publication_endpoint="https://menu.example/api/content")
        db.add(site)
        db.flush()
        section = models.Section(site=site, external_id="games", name="Games", path="/games/", menu_type="header")
        task = models.GenerationTask(title="Menu task", site_id=site.id, geo="DK", language="da", topics_count=2)
        first = models.ContentItem(task=task, site_id=site.id, topic="First", slug="/first/", generated_json={}, idempotency_key="content-menu-first")
        second = models.ContentItem(task=task, site_id=site.id, topic="Second", slug="/second/", generated_json={}, idempotency_key="content-menu-second")
        db.add_all([section, task, first, second])
        db.commit()

        update_content(first.id, ContentUpdate(section_id=section.id), None, db)  # type: ignore[arg-type]
        assert task.section_id is None

        update_content(second.id, ContentUpdate(section_id=section.id), None, db)  # type: ignore[arg-type]
        assert task.section_id == section.id

        update_content(first.id, ContentUpdate(section_id=None), None, db)  # type: ignore[arg-type]
        assert task.section_id is None


def test_task_pipeline_retries_competitor_failure_before_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    attempts: list[str] = []
    generated: list[str] = []

    async def fake_collect(db, item):
        attempts.append(item.id)
        if len(attempts) == 1:
            raise RuntimeError("temporary competitor error")
        item.competitor_brief = {"competitor_urls": ["https://example.test"]}
        item.competitor_research_status = "brief_ready"
        db.commit()
        return item

    def fake_generate(db, item):
        generated.append(item.id)
        item.status = "generated"
        db.commit()
        return item

    monkeypatch.setattr("app.services.collect_competitor_research_for_item", fake_collect)
    monkeypatch.setattr("app.services.generate_content_item", fake_generate)

    with TestingSession() as db:
        task = models.GenerationTask(title="Retry pipeline", geo="DE", language="de", topics_count=1, collect_competitors=True)
        item = models.ContentItem(task=task, topic="Retry topic", slug="/retry/", generated_json={}, idempotency_key="retry-pipeline-item", competitor_research_status="research_failed")
        db.add(item)
        db.commit()

        result = run_task_pipeline(db, task)

        assert attempts == [item.id, item.id]
        assert generated == [item.id]
        assert result.status == "generated"


def test_task_pipeline_stops_competitor_collection_after_six_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    attempts: list[str] = []

    async def fake_collect(db, item):
        attempts.append(item.id)
        raise RuntimeError("persistent competitor error")

    monkeypatch.setattr("app.services.collect_competitor_research_for_item", fake_collect)

    with TestingSession() as db:
        task = models.GenerationTask(title="Failed retry pipeline", geo="DE", language="de", topics_count=1, collect_competitors=True)
        item = models.ContentItem(task=task, topic="Failed retry topic", slug="/failed-retry/", generated_json={}, idempotency_key="failed-retry-pipeline-item", competitor_research_status="research_failed")
        db.add(item)
        db.commit()

        result = run_task_pipeline(db, task)

        assert attempts == [item.id] * 6
        assert result.status == "generation_failed"
        assert item.competitor_research_status == "research_failed"
        assert item.competitor_research_error.startswith("Attempt 6/6:")
