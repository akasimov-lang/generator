from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import _find_project_page, check_site_menu_template_capabilities, enqueue_site_menu_capabilities_check, get_site_menu_capabilities
from app.db import Base
from app.project_cache import analyze_menu_templates, sync_project_cache
from app import project_cache as project_cache_module


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_find_project_page_normalizes_relative_and_absolute_slugs() -> None:
    project = {
        "data": {
            "pages": [
                {"slug": "/", "title": "Home"},
                {"slug": "https://example.com/bonuses/welcome/?ref=menu", "title": "Welcome"},
            ]
        }
    }

    assert _find_project_page(project, "/") == {"slug": "/", "title": "Home"}
    assert _find_project_page(project, "/bonuses/welcome/") == {
        "slug": "https://example.com/bonuses/welcome/?ref=menu",
        "title": "Welcome",
    }
    assert _find_project_page(project, "#") is None


def test_sync_imports_working_project_and_preserves_external_id() -> None:
    with make_session() as db:
        working_prompt = models.PromptTemplate(
            name="Промпт рабочий",
            content="Working prompt content for every synchronized project.",
            is_default=False,
        )
        db.add(working_prompt)
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
        assert site.default_prompt_template_id == working_prompt.id
        assert site.project_status == "working"
        assert unrelated_site is not None
        assert unrelated_site.default_prompt_template_id == working_prompt.id
        assert unrelated_site.project_status == "not_in_focus"


def test_fresh_cache_confirms_requested_page_deletion_only_when_slug_is_absent() -> None:
    with make_session() as db:
        site = models.Site(
            name="delete-confirmation.example",
            base_url="https://delete-confirmation.example",
            publication_endpoint="https://delete-confirmation.example/api/content",
            external_project_id="delete-confirmation",
        )
        db.add(site)
        db.flush()
        task = models.GenerationTask(title="Delete", site_id=site.id, geo="DK", language="da", topics_count=2)
        db.add(task)
        db.flush()
        absent = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Absent page",
            slug="/guides/absent/",
            generated_json={"pages": []},
            status="deletion_pending",
            idempotency_key="delete-absent",
            deletion_requested_at=datetime.now(timezone.utc),
        )
        present = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Present page",
            slug="/guides/present/",
            generated_json={"pages": []},
            status="deletion_pending",
            idempotency_key="delete-present",
            deletion_requested_at=datetime.now(timezone.utc),
        )
        db.add_all([absent, present])
        db.commit()

        sync_project_cache(db, [{
            "id": "delete-confirmation",
            "name": site.name,
            "serverId": "camel",
            "settings": {"canon": site.name},
            "data": {"menu": {"header": [], "footer": []}, "pages": [{"slug": "/guides/present/"}]},
        }])

        db.refresh(absent)
        db.refresh(present)
        assert absent.status == "deleted"
        assert absent.deletion_confirmed_at is not None
        assert present.status == "deletion_pending"
        assert present.deletion_confirmed_at is None


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


def test_static_multilink_navigation_counts_as_rendered_menu() -> None:
    capabilities = analyze_menu_templates([
        {
            "name": "header.hbs",
            "data": """
                <header>
                  <div class="header-inner__menu" id="mainMenu">
                    <div class="menu-item"><a href="/ontario/">Ontario</a></div>
                    <div class="menu-item has-dropdown">
                      <a href="/bonuses/">Bonuses</a>
                      <div class="dropdown"><a href="/bonuses/free-spins/">Free Spins</a></div>
                    </div>
                  </div>
                </header>
            """,
        },
        {"name": "footer.hbs", "data": "<footer>2026 © All rights reserved</footer>"},
    ])

    assert capabilities == {
        "header_menu_rendered": True,
        "header_menu_nested": True,
        "footer_menu_rendered": False,
        "footer_menu_nested": False,
    }


def test_live_visibility_controls_the_rendered_menu_status() -> None:
    capabilities = project_cache_module.combine_menu_capabilities(
        {
            "header_menu_rendered": True,
            "header_menu_nested": True,
            "footer_menu_rendered": False,
            "footer_menu_nested": False,
        },
        {
            "header_menu_rendered": False,
            "footer_menu_rendered": False,
        },
    )

    assert capabilities == {
        "header_menu_template_rendered": True,
        "header_menu_rendered": False,
        "header_menu_nested": False,
        "footer_menu_template_rendered": False,
        "footer_menu_rendered": False,
        "footer_menu_nested": False,
    }


def test_menu_capabilities_are_queued_only_by_manual_action(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.api.check_site_menu_visibility_job.apply_async",
        lambda args, queue: calls.append(args[0]),
    )
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
        queued = enqueue_site_menu_capabilities_check(site.id, None, db)  # type: ignore[arg-type]
        duplicate = enqueue_site_menu_capabilities_check(site.id, None, db)  # type: ignore[arg-type]

        assert first["check_status"] == "not_checked"
        assert second["check_status"] == "not_checked"
        assert len(calls) == 1
        assert queued["check_status"] == "queued"
        assert duplicate["check_id"] == queued["check_id"]


def test_template_menu_check_does_not_queue_chromium(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.fetch_project_template_capabilities",
        lambda site: {
            "header_menu_rendered": True,
            "header_menu_nested": True,
            "footer_menu_rendered": False,
            "footer_menu_nested": False,
        },
    )
    with make_session() as db:
        site = models.Site(
            name="template-check.example",
            base_url="https://template-check.example",
            publication_endpoint="https://template-check.example/api/content",
            cache_server_ip="cobra",
        )
        db.add(site)
        db.commit()

        result = check_site_menu_template_capabilities(site.id, None, db)  # type: ignore[arg-type]

        assert result["check_status"] == "not_checked"
        assert result["checked_at"] is None
        assert result["header_menu_template_rendered"] is True
        assert result["header_menu_rendered"] is None
        assert result["header_menu_nested"] is True
        assert result["footer_menu_template_rendered"] is False
        assert db.scalar(select(models.MenuVisibilityCheck)) is None


def test_menu_capabilities_can_be_refreshed(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.api.check_site_menu_visibility_job.apply_async",
        lambda args, queue: calls.append(queue),
    )
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

        result = enqueue_site_menu_capabilities_check(site.id, None, db)  # type: ignore[arg-type]

        assert calls == ["menu_checks"]
        assert result["check_status"] == "queued"
        assert result["header_menu_rendered"] is False


def test_failed_menu_capability_check_requires_manual_retry(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.api.check_site_menu_visibility_job.apply_async",
        lambda args, queue: calls.append(args[0]),
    )
    with make_session() as db:
        site = models.Site(
            name="failed-check.example",
            base_url="https://failed-check.example",
            publication_endpoint="https://failed-check.example/api/content",
            cache_server_ip="server",
        )
        db.add(site)
        db.commit()
        failed = models.MenuVisibilityCheck(
            site_id=site.id,
            status="failed",
            error_code="LIVE_BROWSER_TIMEOUT",
            error_message="Timed out",
            finished_at=datetime.now(timezone.utc),
        )
        db.add(failed)
        db.commit()

        unchanged = get_site_menu_capabilities(site.id, None, db)  # type: ignore[arg-type]
        retried = enqueue_site_menu_capabilities_check(site.id, None, db)  # type: ignore[arg-type]

        assert unchanged["check_status"] == "failed"
        assert unchanged["check_error_code"] == "LIVE_BROWSER_TIMEOUT"
        assert retried["check_status"] == "queued"
        assert len(calls) == 1


def test_menu_capability_check_reauthenticates_after_unauthorized(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __init__(self, status_code: int, body: dict):
            self.status_code = status_code
            self._body = body

        def json(self) -> dict:
            return self._body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict):
            token = f"token-{sum(1 for method, _ in calls if method == 'POST') + 1}"
            calls.append(("POST", token))
            return FakeResponse(200, {"token": token})

        def get(self, url: str, headers: dict):
            token = headers["Authorization"].removeprefix("Bearer ")
            calls.append(("GET", token))
            if token == "token-1":
                return FakeResponse(401, {})
            return FakeResponse(200, {"shortcodes": []})

    monkeypatch.setattr(project_cache_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        project_cache_module,
        "fetch_live_menu_capabilities",
        lambda site: {"header_menu_rendered": False, "footer_menu_rendered": False},
    )
    site = models.Site(
        name="reauth.example",
        base_url="https://reauth.example",
        publication_endpoint="https://reauth.example/api/content",
        cache_server_ip="crab",
    )

    capabilities = project_cache_module.fetch_project_menu_capabilities(site, force=True)

    assert calls == [
        ("POST", "token-1"),
        ("GET", "token-1"),
        ("POST", "token-2"),
        ("GET", "token-2"),
    ]
    assert capabilities["header_menu_rendered"] is False


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


def test_sync_excludes_identical_repeated_cache_projects() -> None:
    with make_session() as db:
        projects = [
            {"name": "duplicate.example", "settings": {"canon": "one.example"}, "data": {"menu": {}, "pages": []}},
            {"name": "duplicate.example", "settings": {"canon": "two.example"}, "data": {"menu": {}, "pages": []}},
        ]

        result = sync_project_cache(db, projects)
        sites = db.scalars(select(models.Site).order_by(models.Site.external_project_id)).all()

        assert result["created_count"] == 1
        assert result["skipped_duplicate_count"] == 1
        assert [site.external_project_id for site in sites] == ["duplicate.example"]


def test_sync_removes_existing_unlinked_duplicate_rows() -> None:
    with make_session() as db:
        db.add_all([
            models.Site(
                name="cleanup.example",
                base_url="https://cleanup.example",
                publication_endpoint="https://cleanup.example/api/content",
                external_project_id="cleanup.example",
                cache_canon="cleanup.example",
                project_status="duplicate",
            ),
            models.Site(
                name="cleanup.example",
                base_url="https://cleanup.example",
                publication_endpoint="https://cleanup.example/api/content",
                external_project_id="cleanup.example#2",
                cache_canon="cleanup.example",
                project_status="duplicate",
            ),
        ])
        db.commit()

        result = sync_project_cache(db, [{
            "name": "cleanup.example",
            "settings": {"canon": "cleanup.example"},
            "data": {"menu": {}, "pages": []},
        }])
        sites = db.scalars(select(models.Site).where(models.Site.name == "cleanup.example")).all()

        assert result["deleted_duplicate_count"] == 1
        assert len(sites) == 1
        assert sites[0].external_project_id == "cleanup.example"
        assert sites[0].project_status != "duplicate"


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
