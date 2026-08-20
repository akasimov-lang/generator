from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import apply_menu_template, adopt_cached_section, create_menu_library_item, create_section, create_sections_bulk, delete_section, list_admin_request_logs, release_adopted_section, update_menu_library_item, update_section
from app.menu_templates import DE_CASINO_REVIEW_HEADER_TEMPLATE
from app.db import Base
from app.schemas import MenuLibraryItemCreate, MenuLibraryItemUpdate, SectionCreate, SectionsBulkCreate, SectionUpdate


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_menu_create_is_logged_and_old_request_logs_are_removed() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
        )
        db.add(site)
        db.flush()
        db.add(
            models.PublicationLog(
                endpoint_url="https://old.example/api",
                response_status=200,
                created_at=datetime.now(timezone.utc) - timedelta(days=8),
            )
        )
        db.commit()

        create_section(
            site.id,
            SectionCreate(external_id="bonuses", name="Bonusy", path="/bonuses/", menu_type="header"),
            None,  # type: ignore[arg-type]
            db,
        )
        logs = list_admin_request_logs(None, db)  # type: ignore[arg-type]

        assert len(logs) == 1
        assert logs[0]["project_name"] == "review.example"
        assert logs[0]["action"] == "Добавление пункта меню"
        assert logs[0]["method"] == "POST"
        assert logs[0]["result"] == "Ожидает ответа"
        db.refresh(site)
        assert site.menu_library == [{"name": "Bonusy", "path": "/bonuses/", "external_id": "bonuses", "russian_name": ""}]


def test_project_menu_library_stores_custom_items_without_duplicates() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
        )
        db.add(site)
        db.commit()
        payload = MenuLibraryItemCreate(name="VIP Bonus", path="/vip-bonus/", external_id="vip-bonus")

        first = create_menu_library_item(site.id, payload, None, db)  # type: ignore[arg-type]
        second = create_menu_library_item(site.id, payload, None, db)  # type: ignore[arg-type]

        db.refresh(site)
        assert first == second
        assert len(site.menu_library) == 1


def test_cached_menu_item_can_be_adopted_and_used_as_parent() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
            default_menu={"header": [{"title": "Casinos", "path": "/casinos/"}], "footer": []},
            header_menu_nested=True,
        )
        db.add(site)
        db.commit()

        adopted = adopt_cached_section(
            site.id,
            SectionCreate(external_id="casinos", name="Casinos", path="/casinos/", menu_type="header"),
            None,  # type: ignore[arg-type]
            db,
        )
        parent = adopted["section"]
        child = create_section(
            site.id,
            SectionCreate(external_id="new-casinos", name="New Casinos", path="/new-casinos/", menu_type="header", parent_id=parent.id),
            None,  # type: ignore[arg-type]
            db,
        )

        assert parent.sync_status == "synced"
        assert adopted["created"] is True
        assert parent.is_temporary_parent is False
        assert child.parent_id == parent.id
        assert child.sync_status == "pending"


def test_menu_items_can_be_nested_at_any_depth_before_template_check() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
            header_menu_nested=False,
        )
        db.add(site)
        db.commit()

        root = create_section(
            site.id,
            SectionCreate(external_id="casino", name="Casino", path="/casino/", menu_type="header"),
            None,  # type: ignore[arg-type]
            db,
        )
        child = create_section(
            site.id,
            SectionCreate(external_id="live", name="Live", path="/casino/live/", menu_type="header", parent_id=root.id),
            None,  # type: ignore[arg-type]
            db,
        )
        grandchild = create_section(
            site.id,
            SectionCreate(external_id="roulette", name="Roulette", path="/casino/live/roulette/", menu_type="header", parent_id=child.id),
            None,  # type: ignore[arg-type]
            db,
        )

        assert grandchild.parent_id == child.id


def test_canceling_child_form_removes_only_new_temporary_parent() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
            default_menu={"header": [{"title": "Payments", "path": "/payments/"}], "footer": []},
            header_menu_nested=True,
        )
        db.add(site)
        db.commit()

        adopted = adopt_cached_section(
            site.id,
            SectionCreate(external_id="payments", name="Payments", path="/payments/", menu_type="header"),
            None,  # type: ignore[arg-type]
            db,
        )
        parent_id = adopted["section"].id

        result = release_adopted_section(site.id, parent_id, None, db)  # type: ignore[arg-type]

        assert result == {"deleted": True}
        assert db.get(models.Section, parent_id) is None
        assert db.scalar(select(func.count(models.PublicationLog.id))) == 0


def test_menu_library_edit_is_scoped_to_selected_project() -> None:
    with make_session() as db:
        first_site = models.Site(name="first.example", base_url="https://first.example", publication_endpoint="https://first.example/api/content")
        second_site = models.Site(name="second.example", base_url="https://second.example", publication_endpoint="https://second.example/api/content")
        db.add_all([first_site, second_site])
        db.commit()

        result = update_menu_library_item(
            first_site.id,
            "casino-reviews",
            MenuLibraryItemUpdate(name="Lokale anmeldelser", path="lokale-anmeldelser", russian_name="Местные обзоры"),
            None,  # type: ignore[arg-type]
            db,
        )

        db.refresh(first_site)
        db.refresh(second_site)
        assert result["path"] == "/lokale-anmeldelser/"
        assert first_site.menu_library == [{
            "name": "Lokale anmeldelser",
            "path": "/lokale-anmeldelser/",
            "external_id": "casino-reviews",
            "russian_name": "Местные обзоры",
        }]
        assert second_site.menu_library == []


def test_bulk_create_sections_skips_existing_external_ids() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
        )
        db.add(site)
        db.flush()
        db.add(models.Section(site_id=site.id, external_id="bonuses", name="Bonusy", path="/bonuses/", menu_type="header"))
        db.commit()

        result = create_sections_bulk(
            site.id,
            SectionsBulkCreate(
                items=[
                    SectionCreate(external_id="bonuses", name="Bonusy", path="/bonuses/", menu_type="header"),
                    SectionCreate(external_id="reviews", name="Recenze", path="/reviews/", menu_type="footer"),
                ]
            ),
            None,  # type: ignore[arg-type]
            db,
        )

        assert result["created_count"] == 1
        assert result["skipped_count"] == 1
        assert len(db.scalars(select(models.Section).where(models.Section.site_id == site.id)).all()) == 2


def test_de_casino_review_template_creates_complete_three_level_header_once() -> None:
    with make_session() as db:
        site = models.Site(
            name="casino-review.de",
            base_url="https://casino-review.de",
            publication_endpoint="https://casino-review.de/api/content",
            cache_language="de-DE",
        )
        db.add(site)
        db.commit()

        first = apply_menu_template(
            site.id,
            DE_CASINO_REVIEW_HEADER_TEMPLATE["id"],
            None,  # type: ignore[arg-type]
            db,
        )
        second = apply_menu_template(
            site.id,
            DE_CASINO_REVIEW_HEADER_TEMPLATE["id"],
            None,  # type: ignore[arg-type]
            db,
        )

        sections = db.scalars(select(models.Section).where(models.Section.site_id == site.id)).all()
        by_external_id = {section.external_id: section for section in sections}
        assert first["created_count"] == len(DE_CASINO_REVIEW_HEADER_TEMPLATE["items"]) == 96
        assert first["skipped_count"] == 0
        assert second["created_count"] == 0
        assert second["skipped_count"] == 96
        assert len(sections) == 96
        assert sum(section.parent_id is None for section in sections) == 7
        assert by_external_id["de-live-roulette"].parent_id == by_external_id["de-live-casino"].id
        assert by_external_id["de-live-casino"].parent_id == by_external_id["de-casino-games"].id
        assert all(section.menu_type == "header" for section in sections)
        db.refresh(site)
        assert len(site.menu_library) == 96
        oasis = next(item for item in site.menu_library if item["external_id"] == "de-casinos-without-oasis")
        assert oasis["name"] == "Casinos ohne OASIS"
        assert "english_name" not in oasis
        assert "russian_name" not in oasis


def test_menu_item_can_be_edited_and_returns_to_pending_sync() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
            menu_library=[{"name": "Bonusy", "path": "/bonuses/", "external_id": "bonuses", "russian_name": ""}],
        )
        section = models.Section(
            site=site,
            external_id="bonuses",
            name="Bonusy",
            path="/bonuses/",
            menu_type="header",
            sync_status="synced",
            synced_at=datetime.now(timezone.utc),
        )
        db.add_all([site, section])
        db.commit()

        updated = update_section(
            site.id,
            section.id,
            SectionUpdate(name="Casino bonus", path="casino-bonus"),
            None,  # type: ignore[arg-type]
            db,
        )

        assert updated.name == "Casino bonus"
        assert updated.path == "/casino-bonus/"
        assert updated.sync_status == "pending"
        assert updated.synced_at is None
        db.refresh(site)
        assert site.menu_library[0]["name"] == "Casino bonus"
        assert site.menu_library[0]["path"] == "/casino-bonus/"


def test_added_menu_item_can_be_deleted() -> None:
    with make_session() as db:
        site = models.Site(
            name="review.example",
            base_url="https://review.example",
            publication_endpoint="https://review.example/api/content",
        )
        section = models.Section(site=site, external_id="bonuses", name="Bonusy", path="/bonuses/", menu_type="header")
        db.add_all([site, section])
        db.commit()

        result = delete_section(site.id, section.id, None, db)  # type: ignore[arg-type]

        assert result == {"deleted": True}
        assert db.scalar(select(models.Section).where(models.Section.id == section.id)) is None
        log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.endpoint_url == site.base_url))
        assert log is not None
        assert log.request_payload["action"] == "menu_item_delete"
