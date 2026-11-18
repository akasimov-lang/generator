from sqlalchemy import select

from app import auto_lb, generation_anchors, models
from app.auto_lb_api import GenerateRequest, create, state
from app.background_jobs import run_job
from test_auto_lb import configure, response
from test_project_network import env
import pytest


def test_surplus_topics_are_saved_once_and_exposed_in_full(env, monkeypatch):
    db, site, _ = env
    user, provider = configure(db, site)
    created = create(site.id, GenerateRequest(kind="topics"), {"id": user.id}, db)
    lines = [f"Téma {n}" for n in range(337)]
    calls = []

    async def gemini(_provider, prompt):
        calls.append(prompt)
        return response(lines)

    monkeypatch.setattr("app.services.call_gemini", gemini)
    job = db.scalar(select(models.BackgroundJob))
    assert run_job(db, job.id)["status"] == "completed"
    result = state(site.id, {"id": user.id}, db)
    saved = next(row for row in result["generations"] if row["id"] == created["id"])
    assert saved["line_count"] == saved["unique_count"] == 337
    assert saved["text"].splitlines() == result["topic_text"].splitlines() == lines
    assert saved["error"] is None
    assert len(calls) == 1 and provider.total_tokens_used == 12


def test_surplus_does_not_hide_duplicate_topics(env):
    db, site, _ = env
    configure(db, site)
    lines = [f"Topic {n}" for n in range(300)] + [" TOPIC  0 "]
    with pytest.raises(ValueError, match="повторяющиеся"):
        auto_lb.normalize_result("topics", "\n".join(lines), auto_lb.project_context(site))


def test_surplus_does_not_hide_invalid_format(env):
    db, site, _ = env
    configure(db, site)
    lines = [f"Topic {n}" for n in range(300)] + ["# unwanted heading"]
    with pytest.raises(ValueError, match="формат"):
        auto_lb.normalize_result("topics", "\n".join(lines), auto_lb.project_context(site))


def test_general_anchor_job_uses_project_seeds_and_keeps_queued_snapshot(env, monkeypatch):
    db, site, _ = env
    user, _ = configure(db, site)
    site.site_type, site.cache_geo, site.cache_language = "general", "PL", "pl"
    db.commit()
    seeds = ["kasyno mobilne", "bonus powitalny"]
    generation_anchors.save_settings(db, site, seeds)
    preview = state(site.id, {"id": user.id}, db)
    created = create(site.id, GenerateRequest(kind="anchors"), {"id": user.id}, db)
    assert created["context"]["generation_anchors"] == seeds
    assert created["context"]["generation_anchors_source"] == "custom"
    assert created["prompt"] == preview["prompts"]["anchors"]
    assert all(seed in created["prompt"] for seed in seeds)
    generation_anchors.save_settings(db, site, ["zmienione słowa"])

    async def gemini(_provider, prompt):
        assert all(seed in prompt for seed in seeds)
        assert "zmienione słowa" not in prompt
        return response(["KASYNO  MOBILNE", "Naturalny wariant", "Naturalny wariant"])

    monkeypatch.setattr("app.services.call_gemini", gemini)
    assert run_job(db, db.scalar(select(models.BackgroundJob)).id)["status"] == "completed"
    saved = db.get(models.AutoLbGeneration, created["id"])
    assert saved.context["generation_anchors"] == seeds
    assert saved.result_text.splitlines()[:3] == ["KASYNO MOBILNE", "Naturalny wariant", "Naturalny wariant"]
    assert saved.result_text.splitlines().count("bonus powitalny") == 1
    assert sum(auto_lb.normalized_key(line) == "kasyno mobilne" for line in saved.result_text.splitlines()) == 1
    assert "zmienione słowa" not in saved.result_text
    assert state(site.id, {"id": user.id}, db)["context"]["generation_anchors"] == ["zmienione słowa"]


def test_branded_seed_prompt_preserves_unique_count_contract(env):
    db, site, _ = env
    user, _ = configure(db, site)
    generation_anchors.save_settings(db, site, ["BetOnRed vstup", "BetOnRed registrace"])
    created = create(site.id, GenerateRequest(kind="anchors", unique_anchor_count=1), {"id": user.id}, db)
    assert "BetOnRed vstup" in created["prompt"] and "BetOnRed registrace" in created["prompt"]
    assert "ровно 1 уникальных анкоров" in created["prompt"]
    text = "\n".join(["BetOnRed vstup"] * 100)
    assert auto_lb.normalize_result("anchors", text, created["context"]) == text


def test_seed_settings_are_isolated_between_projects(env):
    db, site, _ = env
    configure(db, site)
    other = models.Site(name="second.test", base_url="https://second.test", publication_endpoint="https://second.test/api",
                        brand="Other", cache_geo="CZ", cache_language="cs", cache_canon="second.test")
    db.add(other)
    db.commit()
    generation_anchors.save_settings(db, site, ["Private project phrase"])
    context = auto_lb.project_context(other, db=db)
    assert context["generation_anchors"] == ["Other"]
    assert context["generation_anchors_source"] == "default"
    assert "Private project phrase" not in auto_lb.build_prompt("anchors", context)
