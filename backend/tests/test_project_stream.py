from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import adopt_cached_section_for_content, refresh_site_cache, restore_externally_deleted_section
from app.db import Base
from app.project_cache import sync_project_data_update
from app.project_stream import TOKEN_QUERY_PATTERN, iter_sse_events
from app.schemas import SectionCreate
from app.services import build_project_menu_payload


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_sse_parser_reads_ids_and_multiline_data() -> None:
    events = list(iter_sse_events([
        ": heartbeat",
        "id: 41",
        "event: project",
        'data: {"projectName":',
        'data: "example.com"}',
        "",
        "id: 42",
        'data: {"projectName":"second.example"}',
        "",
    ]))

    assert [(event.event_id, event.event, event.data) for event in events] == [
        ("41", "project", '{"projectName":\n"example.com"}'),
        ("42", "message", '{"projectName":"second.example"}'),
    ]


def test_stream_token_is_redacted_from_errors() -> None:
    message = "GET https://example.test/projects/stream?token=secret-value failed"

    assert TOKEN_QUERY_PATTERN.sub(r"\1[redacted]", message) == (
        "GET https://example.test/projects/stream?token=[redacted] failed"
    )


def test_stream_update_tracks_external_menu_deletions() -> None:
    with make_session() as db:
        site = models.Site(
            name="changed.example",
            base_url="https://changed.example",
            publication_endpoint="https://changed.example/api/content",
            cache_server_ip="old-server",
            default_menu={"header": [{"title": "Removed", "slug": "/removed/"}], "footer": []},
        )
        removed = models.Section(
            site=site,
            external_id="removed",
            name="Removed",
            path="/removed/",
            menu_type="header",
            sync_status="synced",
        )
        pending = models.Section(
            site=site,
            external_id="pending",
            name="Pending",
            path="/pending/",
            menu_type="header",
            sync_status="pending",
        )
        db.add_all([site, removed, pending])
        db.commit()

        updated = sync_project_data_update(
            db,
            site.name,
            {"name": site.name, "data": {"menu": {"header": [], "footer": []}}},
            server_host="bear.slf-hostesting.com",
        )

        assert updated == 1
        assert site.default_menu == {"header": [], "footer": []}
        assert site.cache_server_ip == "bear"
        assert site.has_menu is False
        assert removed.sync_status == "external_deleted"
        assert pending.sync_status == "pending"

        payload = build_project_menu_payload(db, site, "header")
        assert [item["slug"] for item in payload["list"]] == ["/pending/"]


def test_stream_update_restores_section_when_it_reappears() -> None:
    with make_session() as db:
        site = models.Site(
            name="restored.example",
            base_url="https://restored.example",
            publication_endpoint="https://restored.example/api/content",
        )
        section = models.Section(
            site=site,
            external_id="restored",
            name="Restored",
            path="/restored/",
            menu_type="header",
            sync_status="external_deleted",
        )
        db.add_all([site, section])
        db.commit()

        sync_project_data_update(
            db,
            site.name,
            {"name": site.name, "data": {"menu": {"header": [{"title": "Restored", "slug": "/restored/"}], "footer": []}}},
        )

        assert section.sync_status == "synced"


def test_externally_deleted_section_can_be_queued_for_restore() -> None:
    with make_session() as db:
        site = models.Site(
            name="restore-button.example",
            base_url="https://restore-button.example",
            publication_endpoint="https://restore-button.example/api/content",
            cache_server_ip="bear",
        )
        section = models.Section(
            site=site,
            external_id="restore-me",
            name="Restore me",
            path="/restore-me/",
            menu_type="header",
            sync_status="external_deleted",
        )
        db.add_all([site, section])
        db.commit()

        restored = restore_externally_deleted_section(
            site.id,
            section.id,
            {"id": "user-id", "username": "editor", "is_admin": False},
            db,
        )

        assert restored.sync_status == "pending"
        log = db.query(models.PublicationLog).one()
        assert log.request_payload["action"] == "menu_item_restore"
        assert log.request_payload["username"] == "editor"


def test_opening_project_refreshes_current_cache(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="opened.example",
            base_url="https://opened.example",
            publication_endpoint="https://opened.example/api/content",
            external_project_id="opened-id",
            cache_server_ip="old-server",
            default_menu={"header": [{"title": "Removed", "slug": "/removed/"}], "footer": []},
        )
        removed = models.Section(
            site=site,
            external_id="removed",
            name="Removed",
            path="/removed/",
            menu_type="header",
            sync_status="synced",
        )
        db.add_all([site, removed])
        db.commit()

        monkeypatch.setattr(
            "app.api.fetch_project_cache",
            lambda names: [{
                "id": "opened-id",
                "name": "opened.example",
                "serverId": "new-server",
                "settings": {"canon": "opened.example", "lang": "en", "geo": "au"},
                "data": {"menu": {"header": [], "footer": []}, "pages": []},
            }],
        )

        result = refresh_site_cache(site.id, {"id": "user", "username": "editor", "is_admin": False}, db)

        assert result["updated_count"] == 1
        assert site.cache_server_ip == "new-server"
        assert site.default_menu == {"header": [], "footer": []}
        assert removed.sync_status == "external_deleted"


def test_cached_menu_item_can_be_selected_as_content_target() -> None:
    with make_session() as db:
        site = models.Site(
            name="content-target.example",
            base_url="https://content-target.example",
            publication_endpoint="https://content-target.example/api/content",
            default_menu={"header": [{"title": "Casinos", "slug": "/casinos/"}], "footer": []},
        )
        db.add(site)
        db.commit()

        result = adopt_cached_section_for_content(
            site.id,
            SectionCreate(**{
                "external_id": "casinos",
                "name": "Casinos",
                "path": "/casinos/",
                "menu_type": "header",
                "parent_id": None,
            }),
            {"id": "user", "username": "editor", "is_admin": False},
            db,
        )

        assert result["created"] is True
        assert result["section"].sync_status == "synced"
        assert result["section"].is_temporary_parent is False
