from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import get_site_menu_capabilities
from app.db import Base
from app.project_cache import analyze_menu_templates, sync_project_cache


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_sync_imports_working_project_and_preserves_external_id() -> None:
    with make_session() as db:
        projects = [
            {
                "id": "cache-project-1",
                "name": "asyl-bilim.kz",
                "serverId": "crab-primary",
                "serverIp": "cobra",
                "settings": {"canon": "pin-kz.pinup-2026.it.com", "lang": "ru_RU", "geo": "ru-KZ", "domains": ["one.test", "two.test"]},
                "data": {
                    "menu": {"header": [{"title": "App"}], "footer": [{"title": "About"}]},
                    "pages": [
                        {"slug": "/", "title": "Pin Up Kazakhstan"},
                        {"slug": "/bonus/", "title": "Bonus"},
                    ],
                },
            },
            {
                "id": "not-working",
                "name": "unrelated.example",
                "settings": {"canon": "unrelated.example"},
                "data": {"menu": {"header": [], "footer": []}},
            },
        ]

        result = sync_project_cache(db, projects)
        site = db.scalar(select(models.Site).where(models.Site.external_project_id == "cache-project-1"))
        unrelated_site = db.scalar(select(models.Site).where(models.Site.external_project_id == "not-working"))

        assert result["cache_count"] == 2
        assert result["matched_count"] == 1
        assert result["created_count"] == 2
        assert site is not None
        assert site.external_project_id == "cache-project-1"
        assert site.cache_canon == "pin-kz.pinup-2026.it.com"
        assert site.cache_language == "ru_RU"
        assert site.cache_geo == "ru-KZ"
        assert site.has_menu is True
        assert site.homepage_title == "Pin Up Kazakhstan"
        assert site.internal_pages_count == 1
        assert site.domains_count == 2
        assert site.cache_domains == ["one.test", "two.test"]
        assert site.cache_server_ip == "crab-primary"
        assert site.default_menu["header"][0]["title"] == "App"
        assert site.project_status == "working"
        assert unrelated_site is not None
        assert unrelated_site.project_status == "not_in_focus"


def test_menu_capabilities_are_detected_per_template() -> None:
    capabilities = analyze_menu_templates([
        {"name": "header.hbs", "data": "{{#each headerMenu}}<a>{{title}}</a>{{#if this.children}}{{/if}}{{/each}}"},
        {"name": "footer.hbs", "data": "<footer>Static footer</footer>"},
    ])

    assert capabilities == {
        "header_menu_rendered": True,
        "header_menu_nested": True,
        "footer_menu_rendered": False,
        "footer_menu_nested": False,
    }


def test_scripted_multilevel_menu_is_detected() -> None:
    capabilities = analyze_menu_templates([
        {"name": "header.hbs", "data": "<script>headerMenu.forEach(renderDropdown)</script>"},
        {"name": "footer.hbs", "data": "<footer>Static footer</footer>"},
    ])

    assert capabilities["header_menu_rendered"] is True
    assert capabilities["header_menu_nested"] is True
    assert capabilities["footer_menu_rendered"] is False


def test_static_nav_and_unrelated_iteration_do_not_count_as_project_menu_rendering() -> None:
    capabilities = analyze_menu_templates([
        {
            "name": "header.hbs",
            "data": """
                <nav class="menu"><a class="menu-link" href="#top">Domů</a></nav>
                <script>
                  const headings = document.querySelectorAll('.contentMain h2');
                  headings.forEach((heading) => setAnchor(heading));
                </script>
            """,
        },
        {"name": "footer.hbs", "data": "<ul class='footer-menu'><li>Terms</li></ul>"},
    ])

    assert capabilities == {
        "header_menu_rendered": False,
        "header_menu_nested": False,
        "footer_menu_rendered": False,
        "footer_menu_nested": False,
    }


def test_menu_capabilities_are_fetched_only_once(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch(site: models.Site) -> dict[str, bool]:
        calls.append(site.id)
        return {
            "header_menu_rendered": True,
            "header_menu_nested": False,
            "footer_menu_rendered": True,
            "footer_menu_nested": True,
        }

    monkeypatch.setattr("app.api.fetch_project_menu_capabilities", fake_fetch)
    with make_session() as db:
        site = models.Site(
            name="menu-capabilities.example",
            base_url="https://menu-capabilities.example",
            publication_endpoint="https://menu-capabilities.example/api/content",
            cache_server_ip="cobra",
        )
        db.add(site)
        db.commit()

        first = get_site_menu_capabilities(site.id, None, db)  # type: ignore[arg-type]
        second = get_site_menu_capabilities(site.id, None, db)  # type: ignore[arg-type]

        assert calls == [site.id]
        assert first["header_menu_rendered"] is True
        assert second["footer_menu_nested"] is True


def test_menu_capabilities_can_be_refreshed(monkeypatch) -> None:
    calls: list[bool] = []

    def fake_fetch(site: models.Site, force: bool = False) -> dict[str, bool]:
        calls.append(force)
        return {
            "header_menu_rendered": True,
            "header_menu_nested": True,
            "footer_menu_rendered": False,
            "footer_menu_nested": False,
        }

    monkeypatch.setattr("app.api.fetch_project_menu_capabilities", fake_fetch)
    with make_session() as db:
        site = models.Site(
            name="refresh-menu.example",
            base_url="https://refresh-menu.example",
            publication_endpoint="https://refresh-menu.example/api/content",
            cache_server_ip="cobra",
            menu_capabilities_checked_at=datetime.now(timezone.utc),
            header_menu_rendered=False,
            footer_menu_rendered=False,
        )
        db.add(site)
        db.commit()

        result = get_site_menu_capabilities(site.id, None, db, refresh=True)  # type: ignore[arg-type]

        assert calls == [True]
        assert result["header_menu_rendered"] is True
        assert result["header_menu_nested"] is True


def test_sync_updates_existing_project_without_duplicate() -> None:
    with make_session() as db:
        project = {
            "name": "poland-22bet.com",
            "settings": {"canon": "chimeraprime.com"},
            "data": {"menu": {"header": [{"title": "Start"}], "footer": [{"title": "Terms"}]}},
        }

        first_result = sync_project_cache(db, [project])
        project["data"]["menu"]["header"].append({"title": "Bonus"})
        second_result = sync_project_cache(db, [project])

        assert first_result["created_count"] == 1
        assert second_result["created_count"] == 0
        assert second_result["updated_count"] == 1
        assert len(db.scalars(select(models.Site)).all()) == 1
        assert db.scalar(select(models.Site)).external_project_id == "poland-22bet.com"


def test_sync_marks_every_repeated_cache_name_as_duplicate() -> None:
    with make_session() as db:
        projects = [
            {"name": "duplicate.example", "settings": {"canon": "one.example"}, "data": {"menu": {}, "pages": []}},
            {"name": "duplicate.example", "settings": {"canon": "two.example"}, "data": {"menu": {}, "pages": []}},
        ]

        result = sync_project_cache(db, projects)
        sites = db.scalars(select(models.Site).order_by(models.Site.external_project_id)).all()

        assert result["created_count"] == 2
        assert [site.external_project_id for site in sites] == ["duplicate.example", "duplicate.example#2"]
        assert {site.project_status for site in sites} == {"duplicate"}


def test_sync_marks_project_with_header_only_as_having_menu() -> None:
    with make_session() as db:
        project = {
            "name": "header-only.example",
            "settings": {"canon": "unrelated.example"},
            "data": {"menu": {"header": [{"title": "Home"}], "footer": []}, "pages": []},
        }

        sync_project_cache(db, [project])

        assert db.scalar(select(models.Site)).has_menu is True


def test_sync_confirms_pending_menu_item_found_in_external_menu() -> None:
    with make_session() as db:
        project = {
            "id": "menu-project",
            "name": "menu.example",
            "settings": {"canon": "menu.example"},
            "data": {"menu": {"header": [], "footer": []}, "pages": []},
        }
        sync_project_cache(db, [project])
        site = db.scalar(select(models.Site).where(models.Site.external_project_id == "menu-project"))
        db.add(models.Section(site_id=site.id, external_id="casino-bonuses", name="Casino Bonuses", path="/bonuses/", menu_type="header"))
        db.commit()

        project["data"]["menu"]["header"] = [{"title": "Casino Bonuses", "path": "bonuses"}]
        result = sync_project_cache(db, [project])

        assert result["confirmed_sections_count"] == 1
        section = db.scalar(select(models.Section).where(models.Section.site_id == site.id))
        assert section is not None
        assert section.sync_status == "synced"
        assert section.synced_at is not None
        log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.response_status == 200))
        assert log is not None
        assert log.request_payload["action"] == "menu_item_sync_confirmed"


def test_sync_keeps_pending_menu_item_missing_from_external_menu() -> None:
    with make_session() as db:
        project = {
            "id": "pending-project",
            "name": "pending.example",
            "settings": {"canon": "pending.example"},
            "data": {"menu": {"header": [], "footer": []}, "pages": []},
        }
        sync_project_cache(db, [project])
        site = db.scalar(select(models.Site).where(models.Site.external_project_id == "pending-project"))
        db.add(models.Section(site_id=site.id, external_id="casino-bonuses", name="Casino Bonuses", path="/bonuses/", menu_type="header"))
        db.commit()

        result = sync_project_cache(db, [project])

        assert result["confirmed_sections_count"] == 0
        section = db.scalar(select(models.Section).where(models.Section.site_id == site.id))
        assert section is not None
        assert section.sync_status == "pending"
        assert section.synced_at is None
