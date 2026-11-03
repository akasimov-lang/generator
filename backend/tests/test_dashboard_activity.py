from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, dashboard_activity as activity, pilot_internal_pages
from app.db import Base

NOW = datetime(2026, 11, 3, 10, tzinfo=timezone.utc)
USER = {"username": "anton", "allowed_site_ids": None}


@pytest.fixture
def env():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name="example.test", base_url="https://example.test", publication_endpoint="https://example.test/api")
        db.add(site); db.commit()
        yield db, site
    engine.dispose()


def receipt(db, site, action="select_fake_main", **payload):
    op = models.NetworkOperation(id=str(uuid4()), site_id=site.id, action=action, status="confirmed",
        initiator="ai_seo_419", request_payload={"confirmed_at": NOW.isoformat(), **payload}, created_at=NOW, updated_at=NOW)
    db.add(op); db.commit()
    return op


def run(db, site, status="running", phase="cross_reglue", **plan):
    value = models.AutoReglueRun(id=str(uuid4()), site_id=site.id, initiator="anton", status=status, phase=phase,
                                plan=plan, created_at=NOW, updated_at=NOW)
    db.add(value); db.commit()
    return value


def job(db, site, status="queued", **payload):
    value = models.BackgroundJob(id=str(uuid4()), kind="mass_reglue_list", status=status,
        payload={"actor": "anton", "site_ids": [site.id], **payload},
        result={"items": {site.id: {"site_id": site.id, "status": "pending"}}, "groups": []},
        created_at=NOW, updated_at=NOW)
    db.add(value); db.commit()
    return value


def test_standalone_internal_change_includes_service_actor_and_historical_paths(env):
    db, site = env
    receipt(db, site, journal_before={"fake_path": "/old/", "fake_enabled": True},
            journal_after={"fake_path": "/new/", "fake_enabled": True})
    site.cache_canon = "later.test"; db.commit()
    row, = activity.feed(db, USER)["items"]
    assert (row["before"], row["after"]) == ("/old/", "/new/")
    assert row["project_url"] == "/project-network/example.test/"


def test_spare_creation_and_unchanged_paths_are_not_changes(env):
    db, site = env
    receipt(db, site, "create_fake_main", journal_before={"fake_path": "/same/", "fake_enabled": True},
            journal_after={"fake_path": "/same/", "fake_enabled": True})
    assert activity.feed(db, USER)["items"] == []


def test_disabling_selected_internal_page_is_recorded(env):
    db, site = env
    receipt(db, site, journal_before={"fake_path": "/old/", "fake_enabled": True},
            journal_after={"fake_path": "/old/", "fake_enabled": False})
    row, = activity.feed(db, USER)["items"]
    assert (row["before"], row["after"]) == ("/old/", "")


def test_unconfirmed_internal_change_is_not_shown(env):
    db, site = env
    op = receipt(db, site, alternate={"currentFakeMain": "/new/"})
    op.status = "unknown"; db.commit()
    assert activity.feed(db, USER)["items"] == []


def test_manual_autopilot_run_and_confirmed_main_form_one_row(env):
    db, site = env
    execution = run(db, site, "completed", "completed")
    receipt(db, site, "reglue", auto_run_id=execution.id, source_domain="old.test", reserve="new.test")
    rows = activity.feed(db, USER)["items"]
    assert len(rows) == 1
    assert rows[0]["id"] == "run:" + execution.id
    assert (rows[0]["before"], rows[0]["after"]) == ("old.test", "new.test")


def test_planned_main_is_not_reported_as_completed_change(env):
    db, site = env
    run(db, site, "partial", "cross_create_subdomains", old_main="old.test", new_main="planned.test")
    row, = activity.feed(db, USER)["items"]
    assert "after" not in row
    assert row["status"] == "partial"


def test_mass_launch_is_one_row_and_active_even_before_first_run(env):
    db, site = env
    batch = job(db, site)
    initial = activity.feed(db, USER)
    assert initial["active"][0]["report_url"].endswith(batch.id)
    execution = run(db, site, list_launch_id=batch.id)
    batch.result = {"items": {site.id: {"site_id": site.id, "run_id": execution.id}}, "groups": []}; db.commit()
    receipt(db, site, "reglue", auto_run_id=execution.id, source_domain="old.test", reserve="new.test")
    result = activity.feed(db, USER)
    assert len(result["active"]) == 1 and not result["items"]
    assert result["active"][0]["progress"] == 75
    assert "Смена Main" in result["active"][0]["stage"]


def test_active_mass_launch_not_lost_behind_newer_history_or_pagination(env):
    db, site = env
    batch = job(db, site)
    batch.created_at = batch.updated_at = NOW - timedelta(days=30); db.commit()
    receipt(db, site, "reglue", source_domain="old.test", reserve="new.test")
    result = activity.feed(db, USER, limit=1, before="2026-01-01")
    assert result["active"][0]["id"] == "job:" + batch.id
    assert not result["items"]


def test_publication_branch_keeps_completed_main_job_active(env):
    db, site = env
    batch = job(db, site, "completed")
    execution = run(db, site, "completed", "completed", list_launch_id=batch.id)
    batch.result = {"items": {site.id: {"site_id": site.id, "run_id": execution.id}},
                    "groups": [{"plans": [{"site_id": site.id, "internal_pages": {"enabled": True, "count": 3}}]}]}
    branch = models.BackgroundJob(id=pilot_internal_pages.identifier(batch.id, site.id), kind=pilot_internal_pages.KIND,
        status="queued", payload={"parent_job_id": batch.id, "site_id": site.id, "plan": {"count": 3}}, result={})
    db.add(branch); db.commit()
    row, = activity.feed(db, USER)["active"]
    assert row["progress"] == 50
    assert "внутренних страниц" in row["stage"]


def test_mass_history_remains_one_row_after_completion(env):
    db, site = env
    batch = job(db, site, "completed")
    execution = run(db, site, "completed", "completed", list_launch_id=batch.id)
    batch.result = {"items": {site.id: {"site_id": site.id, "run_id": execution.id}}, "groups": []}; db.commit()
    receipt(db, site, "reglue", auto_run_id=execution.id, source_domain="old.test", reserve="new.test")
    row, = activity.feed(db, USER)["items"]
    assert row["kind"] == "mass" and row["progress"] == 100


def test_site_scope_hides_receipts_runs_and_whole_reports(env):
    db, site = env
    job(db, site); run(db, site)
    receipt(db, site, "reglue", source_domain="old.test", reserve="new.test")
    result = activity.feed(db, {**USER, "allowed_site_ids": []})
    assert result["active"] == result["items"] == []


def test_report_with_inaccessible_donor_has_no_broken_or_leaking_link(env):
    db, site = env
    batch = job(db, site)
    batch.result = {"items": {}, "groups": [{"plans": [{"site_id": site.id, "source_site_id": "private"}]}]}; db.commit()
    assert not activity.feed(db, {**USER, "allowed_site_ids": [site.id]})["active"]


def test_pagination_same_timestamp_has_no_missing_or_duplicate_events(env):
    db, site = env
    receipt(db, site, "reglue", source_domain="old.test", reserve="first.test")
    receipt(db, site, "reglue", source_domain="first.test", reserve="second.test")
    first = activity.feed(db, USER, limit=1)
    second = activity.feed(db, USER, limit=1, before=first["next_before"])
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_before"] is None


def test_read_does_not_commit_or_dispatch_work(env, monkeypatch):
    db, site = env
    job(db, site)
    def forbidden(*args, **kwargs):
        raise AssertionError("Dashboard must be read-only")
    monkeypatch.setattr(db, "commit", forbidden)
    monkeypatch.setattr(db, "flush", forbidden)
    with db.no_autoflush:
        assert activity.feed(db, USER)["active"]


def test_maintenance_report_progress_and_link(env):
    db, site = env
    batch = job(db, site, "running")
    batch.kind = "maintenance_report"
    batch.payload = {**batch.payload, "name": "Обновление контента"}
    batch.result = {"entries": [{"site_id": site.id, "status": "running", "phase": "paragraphs"}]}; db.commit()
    row, = activity.feed(db, USER)["active"]
    assert row["report_url"] == "/auto-reglue/pilot/report?maintenance=" + batch.id
    assert "Публикация текста" in row["stage"]
    assert 0 <= row["progress"] < 100


def test_legacy_mass_group_is_one_linked_row(env):
    db, site = env
    execution = run(db, site)
    config = models.AutoReglueConfig(key="mass-report:batch", value={"id": "batch", "actor": "anton",
        "filter": {"brand": "Brand", "geo": "CZ"}, "results": [{"site_id": site.id, "run_id": execution.id}], "skipped": []})
    db.add(config); db.commit()
    result = activity.feed(db, USER)
    row, = result["active"]
    assert row["id"] == "batch:batch"
    assert row["report_url"] == "/dashboard?mass_report=batch"
    report = activity.legacy_report("batch", USER, db)
    assert report["entries"][0]["run_id"] == execution.id


def test_autopilot_group_manifest_does_not_duplicate_parent_report(env):
    db, site = env
    batch = job(db, site)
    execution = run(db, site, list_launch_id=batch.id)
    db.add(models.AutoReglueConfig(key="mass-report:group", value={"id": "group", "actor": "anton",
        "filter": {"brand": "Brand", "geo": "CZ"}, "results": [{"site_id": site.id, "run_id": execution.id}], "skipped": []}))
    db.commit()
    row, = activity.feed(db, USER)["active"]
    assert row["id"] == "job:" + batch.id


def test_legacy_report_enforces_donor_access(env):
    from fastapi import HTTPException
    db, site = env
    execution = run(db, site, source_site_id="private")
    db.add(models.AutoReglueConfig(key="mass-report:group", value={"id": "group", "actor": "anton",
        "filter": {"brand": "Brand", "geo": "CZ"}, "results": [{"site_id": site.id, "run_id": execution.id}], "skipped": []}))
    db.commit()
    with pytest.raises(HTTPException) as error:
        activity.legacy_report("group", {**USER, "allowed_site_ids": [site.id]}, db)
    assert error.value.status_code == 404


def test_cancelled_launch_with_unstarted_items_is_not_pinned_forever(env):
    db, site = env
    job(db, site, "cancelled")
    result = activity.feed(db, USER)
    assert not result["active"]
    assert result["items"][0]["status"] == "cancelled"
