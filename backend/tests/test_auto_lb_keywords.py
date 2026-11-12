import json
from pathlib import Path
import re

import pytest
from sqlalchemy import select

from app import auto_lb, auto_lb_keywords as keywords, models
from app.auto_lb_api import GenerateRequest, create, state
from app.background_jobs import run_job
from test_auto_lb import configure, response
from test_project_network import env


def general(db, site, *, geo="PL", language="pl"):
    user, provider = configure(db, site)
    site.site_type, site.brand = "general", "Общие ключи"
    site.cache_geo, site.cache_language = geo, language
    db.commit()
    return user, provider


def job(db):
    return db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.status == "queued"))


def test_polish_exact_keywords_in_both_prompts_and_anchor_results(env):
    db, site, _ = env
    user, _ = general(db, site, geo="pl_PL", language="pl-PL")
    context = auto_lb.project_context(site)
    assert context["geo"] == "PL"
    assert context["required_keywords"] == list(keywords.POLISH)
    preview = state(site.id, {"id": user.id}, db)
    for kind in ("anchors", "topics"):
        assert all(phrase in preview["prompts"][kind] for phrase in keywords.POLISH)
    result = auto_lb.normalize_result("anchors", "Other anchor\nPOLSKIE  KASYNO ONLINE\nOther anchor", context).splitlines()
    assert result[:3] == ["Other anchor", keywords.POLISH[0], "Other anchor"]
    assert all(phrase in result for phrase in keywords.POLISH)
    assert len(result) == 12
    assert result.count(keywords.POLISH[0]) == 1


@pytest.mark.parametrize("site_type,brand", [("monobrand", "Lemon Casino"), ("review", "Pelican")])
def test_branded_projects_do_not_get_generic_keywords(env, site_type, brand):
    db, site, _ = env
    configure(db, site)
    site.site_type, site.brand, site.cache_geo, site.cache_language = site_type, brand, "PL", "pl"
    ctx = auto_lb.project_context(site)
    assert "required_keyword_profile" not in ctx
    assert "polskie kasyno online" not in auto_lb.build_prompt("anchors", ctx)


def test_all_supported_languages_and_other_geos_have_localization_contract(env):
    db, site, _ = env
    general(db, site, geo="en_US", language="en")
    codes = re.findall(r'code: "([^"]+)"', (Path(__file__).parents[2] / "frontend/src/languageOptions.ts").read_text())
    assert len(codes) == 76
    for language in codes:
        site.cache_language = language
        ctx = auto_lb.project_context(site)
        assert ctx["geo"] == "US"
        assert ctx["required_keyword_profile"] == keywords.PROFILE
        assert "required_keywords" not in ctx
        for kind in ("anchors", "topics"):
            prompt = auto_lb.build_prompt(kind, ctx)
            assert f"Язык результата: {language}" in prompt
            assert "вместо Польши используй страну GEO проекта" in prompt
            assert all(phrase in prompt for phrase in keywords.POLISH)


def test_translation_is_saved_reused_and_all_keys_are_in_generated_anchors(env, monkeypatch):
    db, site, _ = env
    user, provider = general(db, site, geo="de_DE", language="de")
    translated = ["deutsches Online Casino", "beste Online Casinos", "Internet Casinos",
                  "Echtgeld Casino", "auszahlende Internet Casinos", "auszahlende Casinos",
                  "Online Casino mit den besten Auszahlungen", "Online Casino BLIK", "BLIK Casino", "Casino mit BLIK"]
    calls = []
    async def gemini(_provider, prompt):
        calls.append(prompt)
        if len(calls) == 1:
            assert '"geo": "DE"' in prompt and '"language": "de"' in prompt
            return response([json.dumps(translated, ensure_ascii=False)])
        assert all(phrase in prompt for phrase in translated)
        return response(["Eine weitere Phrase", "https://old.example"])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    for i in range(2):
        row = create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)
        assert run_job(db, job(db).id)["status"] == "completed"
        saved = db.get(models.AutoLbGeneration, row["id"])
        assert saved.context["required_keywords"] == translated
        assert saved.result_text.splitlines() == ["Eine weitere Phrase", "https://current.example", *translated]
        assert saved.context["homepage_title"] == row["context"]["homepage_title"]
        site.cache_canon = "current.example"; db.commit()
    assert len(calls) == 3  # Only one translation for both generations.
    assert provider.total_tokens_used == 36


def test_topics_require_keywords_and_retry_missing_phrases(env, monkeypatch):
    db, site, _ = env
    user, provider = general(db, site)
    created = create(site.id, GenerateRequest(kind="topics"), {"id": user.id}, db)
    calls = []
    async def gemini(_provider, prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return response([f"Inny temat {i}" for i in range(300)])
        assert "В темах отсутствуют обязательные ключи" in prompt
        return response([f"Poradnik: {phrase}" for phrase in keywords.POLISH] + [f"Inny temat {i}" for i in range(290)])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    assert run_job(db, job(db).id)["status"] == "completed"
    saved = db.get(models.AutoLbGeneration, created["id"])
    assert len(saved.result_text.splitlines()) == 300
    assert len(calls) == 2 and provider.total_tokens_used == 24


def test_subsequent_topic_batches_are_new_but_keep_required_phrases(env, monkeypatch):
    db, site, _ = env
    user, _ = general(db, site)
    counter = []
    async def gemini(_provider, prompt):
        counter.append(prompt);n = len(counter)
        return response([f"Poradnik {n}: {phrase}" for phrase in keywords.POLISH] + [f"Temat {n}: {i}" for i in range(290)])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    for _ in range(2):
        create(site.id, GenerateRequest(kind="topics"), {"id": user.id}, db)
        assert run_job(db, job(db).id)["status"] == "completed"
    result = state(site.id, {"id": user.id}, db)["topic_text"].splitlines()
    assert len(result) == len(set(result)) == 600
    assert all(sum(phrase in line for line in result) >= 2 for phrase in keywords.POLISH)


def test_invalid_translation_retries_then_fails_without_incomplete_result(env, monkeypatch):
    db, site, _ = env
    user, provider = general(db, site, geo="CZ", language="cs")
    created = create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)
    calls = []
    async def gemini(_provider, prompt):
        calls.append(prompt)
        return response([json.dumps(["same"] * 10)])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    assert run_job(db, job(db).id)["status"] == "failed"
    saved = db.get(models.AutoLbGeneration, created["id"])
    assert saved.result_text is None and "10 разных переводов" in saved.error
    assert len(calls) == 2 and provider.total_tokens_used == 24


def test_translation_retry_keeps_payment_name_and_then_saves_result(env, monkeypatch):
    db, site, _ = env
    user, _ = general(db, site, geo="CZ", language="cs")
    created = create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)
    calls = []
    async def gemini(_provider, prompt):
        calls.append(prompt)
        if len(calls) <= 2:
            values = [f"Překlad {i}" for i in range(10)]
            if len(calls) == 2:
                assert "BLIK" in prompt
                values[-3:] = ["online kasino BLIK", "BLIK kasino", "kasino s BLIK"]
            return response([json.dumps(values)])
        return response(["Další fráze"])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    assert run_job(db, job(db).id)["status"] == "completed"
    saved = db.get(models.AutoLbGeneration, created["id"])
    assert len(saved.context["required_keywords"]) == 10 and len(calls) == 3
    assert "kasino s BLIK" in saved.result_text.splitlines()


def test_older_general_jobs_are_not_reinterpreted(env, monkeypatch):
    db, site, _ = env
    user, provider = general(db, site, geo="CZ", language="cs")
    ctx = auto_lb.project_context(site);ctx.pop("required_keyword_profile")
    saved = models.AutoLbGeneration(site_id=site.id, created_by_user_id=user.id, provider_id=provider.id,
        kind="anchors", context=ctx, prompt="original saved prompt")
    db.add(saved);db.commit()
    async def gemini(_provider, prompt):
        assert prompt.startswith("original saved prompt\n")
        assert 'REFERENCE_CONTEXT=' in prompt and 'END_REFERENCE_CONTEXT' in prompt
        assert 'required_keyword_profile' not in saved.context
        return response(["Original result"])
    monkeypatch.setattr("app.services.call_gemini", gemini)
    import asyncio
    asyncio.run(auto_lb.generate(db, saved))
    assert saved.result_text == "Original result"
    assert saved.prompt == 'original saved prompt' and saved.context == ctx
