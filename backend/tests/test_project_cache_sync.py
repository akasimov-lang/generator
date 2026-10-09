from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import _find_project_page, check_site_menu_template_capabilities, enqueue_site_menu_capabilities_check, get_site_menu_capabilities
from app.db import Base
from app.project_cache import analyze_menu_templates, reconcile_pending_publications, sync_project_cache
from app import project_cache as project_cache_module


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_server_refresh_recovers_project_omitted_from_aggregate_cache(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="associacaojorgepina.pt",
            base_url="https://casinos.associacaojorgepina.pt",
            publication_endpoint="https://casinos.associacaojorgepina.pt/api/content",
            cache_server_ip="bear",
        )
        db.add(site)
        db.commit()
        direct_project = {
            "settings": {
                "canon": "casinos-pt.terrasdafeira.pt",
                "domains": ["associacaojorgepina.pt", "casinos-pt.terrasdafeira.pt"],
                "geo": "pt_PT",
                "lang": "pt-PT",
            },
            "data": {"menu": {"header": [], "footer": []}, "pages": [{"slug": "/", "title": "Portugal"}]},
        }
        monkeypatch.setattr(project_cache_module, "fetch_project_cache", lambda names: (_ for _ in ()).throw(AssertionError("cache must not be queried after serverId succeeds")))
        monkeypatch.setattr(project_cache_module, "_fetch_project_from_known_server", lambda target: direct_project)

        assert project_cache_module.refresh_project_server_id(db, site) == "bear"
        assert site.cache_server_ip == "bear"
        assert site.cache_canon == "casinos-pt.terrasdafeira.pt"
        assert site.cache_domains == ["associacaojorgepina.pt", "casinos-pt.terrasdafeira.pt"]
        assert site.base_url == "https://casinos-pt.terrasdafeira.pt"
        assert site.cache_language == "pt-PT"
        assert site.cache_geo == "pt_PT"


def test_direct_project_recovery_requires_network_membership_and_sends_origin(monkeypatch) -> None:
    settings = SimpleNamespace(
        project_cache_url="https://webdev.test",
        project_cache_username="publisher",
        project_cache_password="secret",
        app_public_url="https://panel.test/",
        alfan_url="servers.test",
    )
    monkeypatch.setattr(project_cache_module, "get_settings", lambda: settings)
    seen_origins: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            seen_origins.append(request.headers["Origin"])
            return httpx.Response(200, json={"token": "fresh-token"})
        assert request.url.host == "bear.servers.test"
        assert request.url.path == "/projects/one/associacaojorgepina.pt"
        assert request.headers["Authorization"] == "Bearer fresh-token"
        return httpx.Response(200, json={"settings": {"canon": "current.test", "domains": ["unrelated.test"]}})

    real_client = httpx.Client
    monkeypatch.setattr(
        project_cache_module.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    site = models.Site(name="associacaojorgepina.pt", cache_server_ip="bear")

    assert project_cache_module._fetch_project_from_known_server(site) is None
    assert seen_origins == ["https://panel.test"]


def test_inventory_accepts_real_webdev_project_after_original_domain_left_network(monkeypatch) -> None:
    settings = SimpleNamespace(
        project_cache_url="https://webdev.test",
        project_cache_username="publisher",
        project_cache_password="secret",
        app_public_url="https://panel.test/",
        alfan_url="servers.test",
    )
    monkeypatch.setattr(project_cache_module, "get_settings", lambda: settings)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"token": "fresh-token"})
        assert request.url == "https://bear.servers.test/projects/one/old-project.example"
        return httpx.Response(200, json={
            "settings": {"canon": "current.example", "domains": ["current.example"]},
            "data": {"menu": {"header": [], "footer": []}},
        })

    real_client = httpx.Client
    monkeypatch.setattr(
        project_cache_module.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )

    project = project_cache_module._fetch_project_from_server_id("bear", "old-project.example")

    assert project is not None
    assert project["settings"]["canon"] == "current.example"


def test_server_refresh_uses_cache_only_when_saved_server_does_not_confirm(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="moved.example",
            base_url="https://moved.example",
            publication_endpoint="https://moved.example/api/content",
            cache_server_ip="old-server",
        )
        db.add(site)
        db.commit()
        monkeypatch.setattr(project_cache_module, "_fetch_project_from_known_server", lambda target: None)
        monkeypatch.setattr(
            project_cache_module,
            "fetch_project_cache",
            lambda names: [{"name": "moved.example", "serverId": "new-server"}],
        )

        assert project_cache_module.refresh_project_server_id(db, site) == "new-server"
        assert site.cache_server_ip == "new-server"


def test_server_inventory_imports_only_unique_missing_names_without_duplicates(monkeypatch) -> None:
    with make_session() as db:
        existing = models.Site(
            name="existing.example",
            base_url="https://existing.example",
            publication_endpoint="https://existing.example/api/content",
            cache_server_ip="bear",
            cache_domains=["existing.example", "moved.example"],
            external_project_id="existing",
        )
        db.add(existing)
        db.commit()
        monkeypatch.setattr(
            project_cache_module,
            "fetch_project_cache",
            lambda names=None: [{"id": "existing", "name": "existing.example", "serverId": "bear"}],
        )
        monkeypatch.setattr(
            project_cache_module,
            "fetch_server_project_inventories",
            lambda server_ids: (
                {
                    "bear": {"existing.example", "new.example", "moved.example", "ambiguous.example"},
                    "zebra": {"existing.example", "ambiguous.example", "template-sample"},
                },
                {"fox": "HTTP 502"},
            ),
        )

        def direct(server_id: str, name: str) -> dict | None:
            assert server_id == "bear"
            if name == "moved.example":
                return None
            assert name == "new.example"
            return {
                "settings": {
                    "canon": "www.new.example",
                    "domains": ["new.example", "www.new.example"],
                    "geo": "en_US",
                    "lang": "en-US",
                },
                "data": {"menu": {"header": [], "footer": []}, "pages": []},
            }

        monkeypatch.setattr(project_cache_module, "_fetch_project_from_server_id", direct)

        result = project_cache_module.reconcile_server_project_inventory(db)

        sites = db.scalars(select(models.Site).order_by(models.Site.name)).all()
        assert [site.name for site in sites] == ["existing.example", "new.example"]
        imported = next(site for site in sites if site.name == "new.example")
        assert imported.cache_server_ip == "bear"
        assert imported.cache_domains == ["new.example", "www.new.example"]
        assert imported.network_state["domains"] == ["new.example", "www.new.example"]
        assert result["imported_projects"] == ["new.example"]
        assert result["imported_count"] == 1
        assert result["deleted_count"] == 0
        assert result["rejected_missing"] == {"ambiguous.example": "ambiguous servers: bear, zebra"}
        assert result["transferred_domains"] == {"moved.example": ["existing.example"]}
        assert result["failed_servers"] == {"fox": "HTTP 502"}


def test_network_audit_replaces_stale_domains_with_saved_server_snapshot(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="network.example",
            base_url="https://old.example",
            publication_endpoint="https://old.example/api/content",
            cache_server_ip="bear",
            cache_canon="old.example",
            cache_domains=["old.example", "removed.example"],
            network_state={"domains": ["old.example", "removed.example"]},
        )
        db.add(site)
        db.commit()
        settings = SimpleNamespace(
            project_cache_url="https://webdev.test",
            project_cache_username="publisher",
            project_cache_password="secret",
            app_public_url="https://panel.test/",
            alfan_url="servers.test",
        )
        monkeypatch.setattr(project_cache_module, "get_settings", lambda: settings)

        def respond(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/auth/login"
            return httpx.Response(200, json={"token": "audit-token"})

        real_client = httpx.Client
        monkeypatch.setattr(
            project_cache_module.httpx,
            "Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
        )
        monkeypatch.setattr(
            project_cache_module,
            "_fetch_server_network_snapshots",
            lambda server_id, names, token: (
                {
                    "network.example": {
                        "settings": {
                            "canon": "current.example",
                            "domains": ["network.example", "current.example"],
                        },
                        "data": {"menu": {"header": [], "footer": []}, "pages": []},
                    }
                },
                {},
            ),
        )

        result = project_cache_module.reconcile_all_project_networks(db)

        db.refresh(site)
        assert site.cache_canon == "current.example"
        assert site.cache_domains == ["network.example", "current.example"]
        assert site.network_state["domains"] == ["network.example", "current.example"]
        assert "removed.example" not in site.cache_domains
        assert [snapshot["domains"] for snapshot in site.network_snapshot_history] == [
            ["old.example", "removed.example"],
            ["network.example", "current.example"],
        ]
        assert result["projects_confirmed"] == 1
        assert result["projects_unconfirmed"] == 0


def test_domain_transfer_resets_destination_role_memory() -> None:
    source = models.Site(
        id="source",
        name="source.example",
        cache_domains=["moved.example"],
    )
    destination = models.Site(
        id="destination",
        name="destination.example",
        cache_domains=["destination.example"],
        main_domain_history=["moved.example", "destination.example"],
        alternate_domain_history=["moved.example"],
        x_default_history=["moved.example"],
        domain_types={"moved.example": "amp", "destination.example": "main"},
    )
    owners = project_cache_module._domain_owners([source, destination])

    reset_count = project_cache_module._reset_newly_transferred_domain_memory(
        destination,
        ["destination.example", "moved.example"],
        owners,
    )

    assert reset_count == 1
    assert destination.main_domain_history == ["destination.example"]
    assert destination.alternate_domain_history == []
    assert destination.x_default_history == []
    assert destination.domain_types == {"destination.example": "main"}


def test_main_history_survives_canon_changes_and_removed_domains() -> None:
    with make_session() as db:
        project = {"id": "history-project", "name": "history.test", "settings": {"canon": "first.test", "domains": ["first.test", "second.test"]}}
        sync_project_cache(db, [project])
        site = db.scalar(select(models.Site).where(models.Site.external_project_id == "history-project"))
        assert site.main_domain_history == ["first.test"]
        project["settings"] = {"canon": "SECOND.test", "domains": ["second.test"]}
        sync_project_cache(db, [project])
        sync_project_cache(db, [project])
        assert site.main_domain_history == ["first.test", "second.test"]
        assert site.cache_domains == ["second.test"]
        assert site.cache_canon == "second.test"
        project["settings"]["canon"] = "first.test"
        sync_project_cache(db, [project])
        assert site.main_domain_history == ["first.test", "second.test"]


def test_main_history_preserves_existing_canon_on_first_sync() -> None:
    with make_session() as db:
        site = models.Site(name="legacy.test", base_url="https://old.test", publication_endpoint="https://old.test/api/content", cache_canon="old.test", external_project_id="legacy-history")
        db.add(site)
        db.commit()
        sync_project_cache(db, [{"id": "legacy-history", "name": "legacy.test", "settings": {"canon": "new.test"}}])
        assert site.main_domain_history == ["old.test", "new.test"]


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


def test_fresh_cache_confirms_publication_only_when_slug_is_present() -> None:
    with make_session() as db:
        site = models.Site(
            name="publication-confirmation.example",
            base_url="https://publication-confirmation.example",
            publication_endpoint="https://publication-confirmation.example/api/content",
            external_project_id="publication-confirmation",
        )
        db.add(site)
        db.flush()
        task = models.GenerationTask(title="Publish", site_id=site.id, geo="LV", language="lv", topics_count=3)
        db.add(task)
        db.flush()
        absent = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Absent page",
            slug="/guides/absent/",
            generated_json={"pages": []},
            status="publication_pending_confirmation",
            idempotency_key="publish-absent",
            last_publication_status_code=201,
        )
        present = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Present page",
            slug="/guides/present/",
            generated_json={"pages": []},
            status="publication_pending_confirmation",
            idempotency_key="publish-present",
            last_publication_status_code=201,
        )
        failed_but_present = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Failed response, present page",
            slug="/guides/failed-but-present/",
            generated_json={"pages": []},
            status="publication_failed",
            generation_error="Previous publication failure",
            idempotency_key="publish-failed-but-present",
        )
        db.add_all([absent, present, failed_but_present])
        db.commit()

        result = sync_project_cache(db, [{
            "id": "publication-confirmation",
            "name": site.name,
            "serverId": "camel",
            "settings": {"canon": site.name},
            "data": {"menu": {"header": [], "footer": []}, "pages": [
                {"slug": "/guides/present/"},
                {"slug": "/guides/failed-but-present/"},
            ]},
        }])

        db.refresh(absent)
        db.refresh(present)
        db.refresh(failed_but_present)
        db.refresh(task)
        assert result["confirmed_publications_count"] == 2
        assert absent.status == "publication_pending_confirmation"
        assert absent.published_at is None
        assert present.status == "published"
        assert present.published_at is not None
        assert present.published_url == "https://publication-confirmation.example/guides/present/"
        assert present.indexing_status == "queued"
        assert failed_but_present.status == "published"
        assert failed_but_present.generation_error is None
        assert failed_but_present.published_at is not None
        assert task.status != "published"
        confirmation_log = db.scalar(
            select(models.PublicationLog).where(
                models.PublicationLog.content_item_id == present.id,
                models.PublicationLog.response_status == 200,
            )
        )
        assert confirmation_log is not None
        assert confirmation_log.request_payload["action"] == "content_publication_confirmed"

        final_result = sync_project_cache(db, [{
            "id": "publication-confirmation",
            "name": site.name,
            "serverId": "camel",
            "settings": {"canon": site.name},
            "data": {
                "menu": {"header": [], "footer": []},
                "pages": [{"slug": "/guides/absent/"}, {"slug": "/guides/present/"}],
            },
        }])

        db.refresh(task)
        assert final_result["confirmed_publications_count"] == 1
        assert task.status == "published"


def test_periodic_reconciliation_recovers_confirmation_missed_by_stream(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="missed-event.example",
            base_url="https://missed-event.example",
            publication_endpoint="https://missed-event.example/api/content",
            external_project_id="missed-event",
        )
        db.add(site)
        db.flush()
        task = models.GenerationTask(
            title="Recovered publish",
            site_id=site.id,
            geo="CZ",
            language="cs",
            topics_count=1,
            status="publishing",
        )
        db.add(task)
        db.flush()
        item = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Free spiny dnes",
            slug="/akce-a-spiny/free-spiny-dnes/",
            generated_json={"pages": []},
            status="publication_pending_confirmation",
            idempotency_key="missed-stream-event",
            last_publication_status_code=201,
            updated_at=datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc),
        )
        db.add(item)
        db.commit()

        requested_names: list[list[str]] = []

        def fake_fetch(names: list[str] | None = None) -> list[dict]:
            requested_names.append(list(names or []))
            return [{
                "id": "missed-event",
                "name": site.name,
                "serverId": "bear",
                "data": {
                    "menu": {"header": [], "footer": []},
                    "pages": [{"slug": "/akce-a-spiny/free-spiny-dnes/"}],
                },
            }]

        monkeypatch.setattr(project_cache_module, "_fetch_project_from_known_server", lambda target: None)
        monkeypatch.setattr(project_cache_module, "fetch_project_cache", fake_fetch)
        result = reconcile_pending_publications(db, min_age_seconds=0)

        db.refresh(item)
        db.refresh(task)
        assert requested_names == [[site.name]]
        assert result == {
            "checked_projects": 1,
            "checked_items": 1,
            "confirmed": 1,
            "remaining": 0,
            "missing_projects": 0,
            "reconciled_tasks": 0,
        }
        assert item.status == "published"
        assert item.indexing_status == "queued"
        assert item.published_at is not None
        assert task.status == "published"


def test_periodic_reconciliation_uses_saved_server_when_aggregate_cache_omits_project(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="omitted.example",
            base_url="https://current.example",
            publication_endpoint="https://current.example/api/content",
            cache_server_ip="bear",
            external_project_id="omitted",
        )
        db.add(site)
        db.flush()
        task = models.GenerationTask(
            title="Direct confirmation",
            site_id=site.id,
            geo="PT",
            language="pt",
            topics_count=1,
            status="publishing",
        )
        db.add(task)
        db.flush()
        item = models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Privacidade",
            slug="/privacidade/",
            generated_json={"pages": []},
            status="publication_pending_confirmation",
            idempotency_key="direct-confirmation",
            last_publication_status_code=201,
            updated_at=datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc),
        )
        db.add(item)
        db.commit()

        direct_project = {
            "settings": {"canon": "current.example", "domains": ["omitted.example", "current.example"]},
            "data": {"menu": {"header": [], "footer": []}, "pages": [{"slug": "/privacidade/"}]},
        }
        monkeypatch.setattr(project_cache_module, "_fetch_project_from_known_server", lambda target: direct_project)
        monkeypatch.setattr(
            project_cache_module,
            "fetch_project_cache",
            lambda names: (_ for _ in ()).throw(AssertionError(f"aggregate cache must not be queried: {names}")),
        )

        result = reconcile_pending_publications(db, min_age_seconds=0)

        db.refresh(item)
        db.refresh(task)
        assert result["checked_projects"] == 1
        assert result["missing_projects"] == 0
        assert result["confirmed"] == 1
        assert item.status == "published"
        assert task.status == "published"


def test_periodic_reconciliation_skips_recent_pending_items(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="recent-publish.example",
            base_url="https://recent-publish.example",
            publication_endpoint="https://recent-publish.example/api/content",
            external_project_id="recent-publish",
        )
        db.add(site)
        db.flush()
        task = models.GenerationTask(title="Recent", site_id=site.id, geo="CZ", language="cs", topics_count=1)
        db.add(task)
        db.flush()
        db.add(models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Recent page",
            slug="/recent/",
            generated_json={"pages": []},
            status="publication_pending_confirmation",
            idempotency_key="recent-publish",
        ))
        db.commit()

        def unexpected_fetch(names: list[str] | None = None) -> list[dict]:
            raise AssertionError(f"fresh pending publication must not be fetched: {names}")

        monkeypatch.setattr(project_cache_module, "fetch_project_cache", unexpected_fetch)
        result = reconcile_pending_publications(db, min_age_seconds=30)

        assert result == {
            "checked_projects": 0,
            "checked_items": 0,
            "confirmed": 0,
            "remaining": 0,
            "missing_projects": 0,
            "reconciled_tasks": 0,
        }


def test_periodic_reconciliation_repairs_stale_aggregate_task_status(monkeypatch) -> None:
    with make_session() as db:
        site = models.Site(
            name="aggregate-race.example",
            base_url="https://aggregate-race.example",
            publication_endpoint="https://aggregate-race.example/api/content",
            external_project_id="aggregate-race",
        )
        db.add(site)
        db.flush()
        task = models.GenerationTask(
            title="Already published",
            site_id=site.id,
            geo="CZ",
            language="cs",
            topics_count=1,
            status="publishing",
        )
        db.add(task)
        db.flush()
        db.add(models.ContentItem(
            task=task,
            site_id=site.id,
            topic="Published page",
            slug="/published/",
            generated_json={"pages": []},
            status="published",
            idempotency_key="aggregate-race",
            published_at=datetime.now(timezone.utc),
        ))
        db.commit()

        def unexpected_fetch(names: list[str] | None = None) -> list[dict]:
            raise AssertionError(f"no pending page should be fetched: {names}")

        monkeypatch.setattr(project_cache_module, "fetch_project_cache", unexpected_fetch)
        result = reconcile_pending_publications(db)

        db.refresh(task)
        assert result["reconciled_tasks"] == 1
        assert result["checked_items"] == 0
        assert task.status == "published"


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


def test_template_capabilities_fall_back_to_live_site_on_server_error(monkeypatch) -> None:
    monkeypatch.setattr(
        project_cache_module,
        "fetch_project_template_capabilities",
        lambda site: (_ for _ in ()).throw(
            project_cache_module.ProjectCacheError(
                "Project template request returned HTTP 500",
                "PROJECT_TEMPLATE_HTTP_500",
            )
        ),
    )
    monkeypatch.setattr(
        project_cache_module,
        "fetch_live_menu_capabilities",
        lambda site: {"header_menu_rendered": True, "footer_menu_rendered": False},
    )

    capabilities = project_cache_module.fetch_project_template_capabilities_resilient(
        models.Site(
            name="folder.example",
            base_url="https://public.example",
            publication_endpoint="https://public.example/api/content",
            cache_server_ip="bear",
        )
    )

    assert capabilities == {
        "header_menu_rendered": True,
        "header_menu_nested": False,
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
        "app.api.fetch_project_template_capabilities_resilient",
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

        def post(self, url: str, json: dict, headers: dict | None = None):
            assert headers == {"Origin": "https://ai-seo-content-panel.site"}
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


def test_sync_confirms_nested_menu_item_only_under_its_parent() -> None:
    with make_session() as db:
        project = {
            "id": "nested-menu-project",
            "name": "nested-menu.example",
            "settings": {"canon": "nested-menu.example"},
            "data": {"menu": {"header": [], "footer": []}, "pages": []},
        }
        sync_project_cache(db, [project])
        site = db.scalar(select(models.Site).where(models.Site.external_project_id == "nested-menu-project"))
        parent = models.Section(
            site_id=site.id,
            external_id="reviews",
            name="Reviews",
            path="/reviews/",
            menu_type="header",
            sync_status="synced",
        )
        db.add(parent)
        db.flush()
        child = models.Section(
            site_id=site.id,
            external_id="vox",
            name="Vox Casino",
            path="/vox-casino/",
            menu_type="header",
            parent_id=parent.id,
            sync_status="synced",
        )
        db.add(child)
        db.commit()

        project["data"]["menu"]["header"] = [
            {"title": "Reviews", "slug": "/reviews/"},
            {"title": "Vox Casino", "slug": "/vox-casino/"},
        ]
        flat_result = sync_project_cache(db, [project])
        db.refresh(child)

        assert flat_result["confirmed_sections_count"] == 0
        assert child.sync_status == "pending"

        project["data"]["menu"]["header"] = [{
            "title": "Reviews",
            "slug": "/reviews/",
            "children": [{"title": "Vox Casino", "slug": "/vox-casino/"}],
        }]
        nested_result = sync_project_cache(db, [project])
        db.refresh(child)

        assert nested_result["confirmed_sections_count"] == 1
        assert child.sync_status == "synced"


def test_adopted_nested_node_repairs_missing_parent_and_confirms_status():
    with make_session() as db:
        project = {"id": "repair", "name": "repair.example", "data": {"menu": {"header": [{"id": 1, "title": "Reviews", "slug": "/reviews/", "submenu": [{"id": 2, "title": "Brand", "slug": "/reviews/brand/"}]}], "footer": []}, "pages": []}}
        sync_project_cache(db, [project])
        site = db.scalar(select(models.Site).where(models.Site.name == "repair.example"))
        child = models.Section(site_id=site.id, external_id="2", name="Brand", path="/reviews/brand/", menu_type="header", sync_status="pending", is_review=True)
        db.add(child)
        db.commit()
        sync_project_cache(db, [project])
        assert child.parent_id and child.sync_status == "synced" and child.is_review
        assert db.get(models.Section, child.parent_id).path == "/reviews/"
        child.name = "Changed locally"
        db.commit()
        sync_project_cache(db, [project])
        assert child.sync_status == "pending"
