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
    context.pop("output_count"); context.pop("prompt_version")
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
    context = auto_lb.project_context(site)
    context.pop("output_count"); context.pop("prompt_version")
    result = auto_lb.normalize_result("anchors", "\n".join(lines), context).splitlines()
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
        assert "300 строк" in prompt
        assert "ОБРАЗЕЦ" not in prompt and "Česko" not in prompt and "betonred.cz" not in prompt
    prompt = auto_lb.build_prompt("topics", context)
    assert "300 рекламно-информационных тем" in prompt
    for removed in ["ПРИМЕР", "образец", "Используй пример", "Не обещай выигрыш", "Не переносить", "BetOnRed", "Чехию", "конкретных бонусов"]:
        assert removed not in prompt


@pytest.mark.parametrize("field,value", [("brand", "Общие ключи"), ("cache_geo", ""), ("cache_language", ""), ("cache_canon", "")])
def test_missing_project_context_is_not_invented(env, field, value):
    db, site, _ = env
    configure(db, site)
    site.site_type = "monobrand"
    setattr(site, field, value)
    with pytest.raises(ValueError):
        auto_lb.project_context(site)


def test_topic_count_duplicates_and_list_markers(env):
    db, site, _ = env
    configure(db, site)
    ctx = auto_lb.project_context(site)
    assert auto_lb.parse_lines("1. Heading\n5 tipů pro hráče\n• Another") == ["Heading", "5 tipů pro hráče", "Another"]
    with pytest.raises(ValueError, match="300 строк"):
        auto_lb.normalize_result("topics", "\n".join(f"Topic {n}" for n in range(299)), ctx)
    with pytest.raises(ValueError, match="повторяющиеся"):
        auto_lb.normalize_result("topics", "\n".join(["same"] * 300), ctx)


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
        return response([f"BetOnRed phrase {n % 28}" for n in range(298)] + ["current.example", "https://current.example"])
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
    assert row.status == "failed" and "300 строк" in row.error and not row.result_text
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


def test_new_anchor_generation_uses_no_reference_and_replaces_domains(env):
    db,site,_=env;configure(db,site)
    context=auto_lb.project_context(site)
    lines=['BetOnRed']*150+['Local brand phrase']*148+['old-domain.test','https://old-domain.test']
    result=auto_lb.normalize_result('anchors','\n'.join(lines),context).splitlines()
    assert len(result)==300 and result[:298]==lines[:298]
    assert result[-2:]==['current.example','https://current.example']


def test_topic_accumulation_survives_history_limit_main_change_and_failure(env):
    db,site,_=env;user,provider=configure(db,site)
    context=auto_lb.project_context(site)
    for n in range(42):
        db.add(models.AutoLbGeneration(site_id=site.id,created_by_user_id=user.id,provider_id=provider.id,
            kind='topics',context=context,prompt='old saved prompt',status='completed',result_text=f'Topic {n}'))
    db.add(models.AutoLbGeneration(site_id=site.id,created_by_user_id=user.id,provider_id=provider.id,
        kind='topics',context={**context,'language':'de'},prompt='',status='completed',result_text='Other language'))
    db.add(models.AutoLbGeneration(site_id=site.id,created_by_user_id=user.id,provider_id=provider.id,
        kind='topics',context=context,prompt='',status='failed',result_text=None))
    db.commit()
    from app.auto_lb_api import state
    site.cache_canon='changed.example';db.commit()
    result=state(site.id,{'id':user.id},db)
    assert result['topic_text'].splitlines()==[f'Topic {n}' for n in range(42)]
    assert len(result['generations'])==40
    assert result['anchor_count']==result['topic_count']==300


def test_repeated_generation_appends_300_topics_and_retries_duplicate_batch(env,monkeypatch):
    db,site,_=env;user,provider=configure(db,site)
    from app.auto_lb_api import create,GenerateRequest,state
    batches=iter([[f'Old topic {i}' for i in range(300)], [f'Old topic {i}' for i in range(300)], [f'New topic {i}' for i in range(300)]])
    async def gemini(*args): return response(next(batches))
    monkeypatch.setattr('app.services.call_gemini',gemini)
    for _ in range(2):
        created=create(site.id,GenerateRequest(kind='topics'),{'id':user.id},db)
        job=db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.status=='queued'))
        assert run_job(db,job.id)['status']=='completed'
    text=state(site.id,{'id':user.id},db)['topic_text'].splitlines()
    assert text==[f'Old topic {i}' for i in range(300)]+[f'New topic {i}' for i in range(300)]
    assert provider.total_tokens_used==36


@pytest.mark.parametrize('count', [1, 30, 47, 300])
def test_unique_anchor_setting_snapshotted_and_preview_matches_job(env, count):
    db, site, _ = env
    user, _ = configure(db, site)
    from app.auto_lb_api import create, GenerateRequest, state
    preview = state(site.id, {'id': user.id}, db, unique_anchor_count=count)
    row = create(site.id, GenerateRequest(kind='anchors', unique_anchor_count=count), {'id': user.id}, db)
    assert row['context']['unique_anchor_count'] == count
    assert row['prompt'] == preview['prompts']['anchors']
    assert f'ровно {count} уникальных анкоров' in row['prompt']
    assert 'Не менее 10%' in row['prompt']
    lines = [f'BetOnRed phrase {n % count}' for n in range(300)]
    assert auto_lb.normalize_result('anchors', '\n'.join(lines), row['context']).splitlines() == lines


def test_unique_default_and_invalid_counts():
    from app.auto_lb_api import GenerateRequest
    from pydantic import ValidationError
    assert GenerateRequest(kind='anchors').unique_anchor_count == 30
    for invalid in [0, -1, 301, 2.5, True, None, '30']:
        with pytest.raises(ValidationError):
            GenerateRequest(kind='anchors', unique_anchor_count=invalid)


def test_unique_count_checked_after_domain_replacement_and_normalization(env):
    db, site, _ = env
    configure(db, site)
    ctx = {**auto_lb.project_context(site), 'unique_anchor_count': 4}
    lines = ['BetOnRed  info', 'betonred info', 'one.example', 'two.example'] * 75
    with pytest.raises(ValueError, match='получено 2'):
        auto_lb.normalize_result('anchors', '\n'.join(lines), ctx)
    ctx['unique_anchor_count'] = 2
    result = auto_lb.normalize_result('anchors', '\n'.join(lines), ctx)
    assert result.count('current.example') == 150


def test_incorrect_unique_count_retries_with_saved_requirement(env, monkeypatch):
    db, site, _ = env
    user, _ = configure(db, site)
    from app.auto_lb_api import create, GenerateRequest
    row = create(site.id, GenerateRequest(kind='anchors', unique_anchor_count=40), {'id': user.id}, db)
    prompts = []
    async def gemini(_provider, prompt):
        prompts.append(prompt)
        count = 1 if len(prompts) == 1 else 40
        return response([f'BetOnRed info {n % count}' for n in range(300)])
    monkeypatch.setattr('app.services.call_gemini', gemini)
    job = db.scalar(select(models.BackgroundJob))
    assert run_job(db, job.id)['status'] == 'completed'
    assert len(prompts) == 2 and 'Ожидалось 40 уникальных анкоров, получено 1' in prompts[1]
    saved = db.get(models.AutoLbGeneration, row['id'])
    assert auto_lb.serialize(saved)['unique_count'] == 40


@pytest.mark.parametrize("count", [299, 313])
def test_anchor_output_keeps_all_rows_without_exact_count(env, count):
    db, site, _ = env
    configure(db, site)
    ctx = auto_lb.project_context(site)
    ctx.update(prompt_version=2, unique_anchor_count=30)
    lines = [f"Brand phrase {n % 30}" for n in range(count)]
    assert auto_lb.normalize_result("anchors", "\n".join(lines), ctx).splitlines() == lines


@pytest.mark.parametrize("site_type,brand", [("general", ""), ("general", "Old Brand"), (None, "Общие ключи"), (None, "")])
def test_general_sites_use_online_casino_for_auto_lb(env, site_type, brand):
    db, site, _ = env
    configure(db, site)
    site.site_type, site.brand = site_type, brand
    context = auto_lb.project_context(site)
    assert context["brand"] == "online casino"
    assert site.brand == brand
    for kind in ("anchors", "topics"):
        prompt = auto_lb.build_prompt(kind, context)
        assert "online casino" in prompt
        assert "online casino casino" not in prompt
    assert context["main"] == "current.example"
    assert context["language"] == "cs"


def test_general_anchor_job_has_homepage_context_and_no_count_limit(env):
    from app.auto_lb_api import create, GenerateRequest, state
    db, site, _ = env
    user, _ = configure(db, site)
    site.site_type = "general"
    site.homepage_title = "Online Casinos Deutschland — Vergleich"
    db.commit()
    current = state(site.id, {"id": user.id}, db)
    assert current["anchor_count"] is None
    assert current["topic_count"] == 300
    row = create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)
    assert row["context"]["homepage_title"] == site.homepage_title
    assert "unique_anchor_count" not in row["context"]
    assert "https://current.example" in row["prompt"]
    assert site.homepage_title in row["prompt"]
    assert "300" not in row["prompt"]
    assert "30 уникальных" not in row["prompt"]
    for count in (7, 351):
        lines = [f"casino phrase {n}" for n in range(count)]
        assert auto_lb.normalize_result("anchors", "\n".join(lines), row["context"]).splitlines() == lines
    with pytest.raises(ValueError, match="пустой"):
        auto_lb.normalize_result("anchors", "", row["context"])
    site.homepage_title = "New title"
    assert row["context"]["homepage_title"] != site.homepage_title
