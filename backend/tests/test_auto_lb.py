import asyncio
from collections import Counter
from pathlib import Path
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import auto_lb, models
from app.auto_lb_api import router
from app.background_jobs import dispatch_pending, run_job
from app.db import get_db
from app.security import require_auth
from test_project_network import env


def configure(db, site):
    site.brand, site.cache_geo, site.cache_language = "BetOnRed", "CZ", "cs"
    site.cache_canon = "https://current.example/some/path"
    user = models.User(username="editor", password_hash="unused")
    provider = models.AiProvider(name="Gemini", provider_type="gemini", endpoint_url="https://example.test",
                                 model="test", api_key="test-key", is_active=True)
    db.add_all([user, provider]); db.commit()
    return user, provider


def response(lines):
    return {"candidates": [{"content": {"parts": [{"text": "\n".join(lines)}]}}],
            "usageMetadata": {"totalTokenCount": 12}}


def test_reference_frequencies_and_current_main_replacement(env):
    db, site, _ = env
    configure(db, site)
    context = auto_lb.project_context(site)
    result = auto_lb.normalize_result("anchors", "\n".join(auto_lb.ANCHORS), context).splitlines()
    expected = [context["main"] if x == "betonred.cz" else context["main_url"] if x == "https://betonred.cz" else x for x in auto_lb.ANCHORS]
    assert result == expected
    assert len(result) == 87
    assert Counter(result)["current.example"] == 9
    assert Counter(result)["https://current.example"] == 4
    assert "betonred.cz" not in "\n".join(result)


def test_repeated_translations_are_enforced_without_deduplication(env):
    db, site, _ = env
    configure(db, site)
    lines = list(auto_lb.ANCHORS)
    lines[9] = "Different accidental translation"
    result = auto_lb.normalize_result("anchors", "\n".join(lines), auto_lb.project_context(site)).splitlines()
    assert result[9] == result[2] == "BetOnRed Česko"


def test_prompt_adapts_every_available_language_and_project(env):
    db, site, _ = env
    configure(db, site)
    site.brand, site.cache_geo = "Other Brand", "DE"
    codes = re.findall(r'code: "([^"]+)"', (Path(__file__).parents[2] / "frontend/src/languageOptions.ts").read_text())
    assert len(codes) == 76
    for language in codes:
        site.cache_language = language
        context = auto_lb.project_context(site)
        prompt = auto_lb.build_prompt("anchors", context)
        assert f"Язык результата: {language}" in prompt
        assert "Other Brand" in prompt and "ГЕО DE" in prompt and "current.example" in prompt
        assert "ровно 87 строк" in prompt
    assert len(auto_lb.TOPIC_EXAMPLES) == 100
    assert "100 рекламно-информационных тем" in auto_lb.build_prompt("topics", context)


@pytest.mark.parametrize("field,value", [("brand", "Общие ключи"), ("cache_geo", ""), ("cache_language", ""), ("cache_canon", "")])
def test_missing_project_context_is_not_invented(env, field, value):
    db, site, _ = env
    configure(db, site)
    setattr(site, field, value)
    with pytest.raises(ValueError):
        auto_lb.project_context(site)


def test_topic_count_duplicates_and_list_markers(env):
    db, site, _ = env
    configure(db, site)
    ctx = auto_lb.project_context(site)
    assert auto_lb.parse_lines("1. Heading\n5 tipů pro hráče\n• Another") == ["Heading", "5 tipů pro hráče", "Another"]
    with pytest.raises(ValueError, match="100 строк"):
        auto_lb.normalize_result("topics", "\n".join(auto_lb.TOPIC_EXAMPLES[:-1]), ctx)
    with pytest.raises(ValueError, match="повторяющиеся"):
        auto_lb.normalize_result("topics", "\n".join(["same"] * 100), ctx)


def test_durable_jobs_separate_kinds_and_snapshot_context(env, monkeypatch):
    db, site, _ = env
    user, provider = configure(db, site)
    from app.auto_lb_api import create, GenerateRequest, state
    one = create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)
    assert create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)["id"] == one["id"]
    two = create(site.id, GenerateRequest(kind="topics"), {"id": user.id}, db)
    assert two["id"] != one["id"]
    jobs = db.scalars(select(models.BackgroundJob)).all()
    dispatched = []
    dispatch_pending(db, lambda *args: dispatched.append(args))
    assert [queue for _, queue in dispatched] == ["generation", "generation"]
    site.cache_canon = "changed.example"; db.commit()
    calls = []
    async def gemini(_provider, prompt):
        calls.append(prompt)
        return response(auto_lb.ANCHORS)
    monkeypatch.setattr("app.services.call_gemini", gemini)
    assert run_job(db, jobs[0].id)["status"] == "completed"
    assert run_job(db, jobs[0].id)["status"] == "skipped"
    assert len(calls) == 1
    row = db.get(models.AutoLbGeneration, one["id"])
    assert "current.example" in row.result_text and "changed.example" not in row.result_text
    assert state(site.id, {"id": user.id}, db)["context"]["main"] == "changed.example"
    assert provider.total_tokens_used == 12


def test_invalid_output_retries_then_records_failure(env, monkeypatch):
    db, site, _ = env
    user, provider = configure(db, site)
    from app.auto_lb_api import create, GenerateRequest
    row = create(site.id, GenerateRequest(kind="topics"), {"id": user.id}, db)
    async def gemini(*args): return response(["short"])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    job = db.scalar(select(models.BackgroundJob))
    assert run_job(db, job.id)["status"] == "failed"
    row = db.get(models.AutoLbGeneration, row["id"])
    assert row.status == "failed" and "100 строк" in row.error and not row.result_text
    assert provider.total_tokens_used == 24


def test_project_access_and_provider_secrets(env):
    db, site, _ = env
    user, provider = configure(db, site)
    other = models.Site(name="other.test", base_url="https://other.test", publication_endpoint="https://other.test/api")
    db.add(other); db.commit()
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    def auth():
        db.info["allowed_site_ids"] = [site.id]
        return {"id": user.id, "is_admin": False}
    app.dependency_overrides[require_auth] = auth
    # Call endpoints directly: same scoped SQLAlchemy session used by request auth.
    from app.auto_lb_api import state, create, GenerateRequest
    from fastapi import HTTPException
    auth()
    assert "test-key" not in str(state(site.id, auth(), db))
    for operation in (lambda: state(other.id, auth(), db), lambda: create(other.id, GenerateRequest(kind="topics"), auth(), db)):
        with pytest.raises(HTTPException) as error: operation()
        assert error.value.status_code == 404
