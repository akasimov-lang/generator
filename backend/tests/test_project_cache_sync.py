from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.project_cache import sync_project_cache


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
                "settings": {"canon": "pin-kz.pinup-2026.it.com", "domains": ["one.test", "two.test"]},
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
        assert site.has_menu is True
        assert site.homepage_title == "Pin Up Kazakhstan"
        assert site.internal_pages_count == 1
        assert site.domains_count == 2
        assert site.default_menu["header"][0]["title"] == "App"
        assert site.project_status == "working"
        assert unrelated_site is not None
        assert unrelated_site.project_status == "not_in_focus"


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
