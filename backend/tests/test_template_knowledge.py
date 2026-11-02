import asyncio
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models, services, site_templates as templates, template_sources
from app.db import get_db
from app.security import require_auth
from app.site_templates_api import router
from app.template_knowledge import LIBRARY, attach_sources, matching_sources, source_excerpt
from test_site_templates import db, content


@pytest.mark.parametrize("brand,geo,expected", [
    ("Lemon Casino", "PL", 1), ("lemoncasino", "pl", 1), (" Lemon-Casino ", "PL", 1),
    ("Lemon Casino", "CZ", 0), ("Lemon", "PL", 0), ("Other", "PL", 0),
])
def test_knowledge_matches_only_brand_and_geo(brand, geo, expected):
    assert len(matching_sources(brand, geo)) == expected


def setup_template(db, *, collect=False):
    user = models.User(username="knowledge", password_hash="")
    provider = models.AiProvider(name="Gemini", provider_type="gemini", endpoint_url="https://api.test", api_key="test")
    db.add_all([user, provider]); db.flush()
    request = templates.TemplateRequest(brand="Lemon Casino", geo="PL", language="pl",
        ai_provider_id=provider.id, collect_competitors=collect)
    row = models.SiteTemplate(created_by_user_id=user.id, brand=request.brand, geo=request.geo,
        language=request.language, request_data=request.model_dump(), status="awaiting_sources")
    db.add(row); db.commit()
    return user, provider, row


def test_snapshot_is_exact_idempotent_and_preserves_manual_edits(db):
    _, _, row = setup_template(db)
    attach_sources(db, row); db.commit()
    source = db.scalar(select(models.TemplateSource))
    entry = matching_sources(row.brand, row.geo)[0]
    assert source.google_html == (LIBRARY / entry["file"]).read_text(encoding="utf-8")
    assert hashlib.sha256(source.google_html.encode()).hexdigest() == entry["sha256"]
    assert source.capture["source"] == "user_upload"
    extracted = source_excerpt(source)
    assert "Dzienny limit wypłat 2500 €" in extracted["excerpt"]
    assert "Book of Dead 96,21%" in extracted["excerpt"]
    assert not extracted["excerpt_truncated"]
    row.document = {**row.document, "research": {**row.document["research"], "analysis": "saved analysis"}}
    source.google_html = source.google_html.replace("2500 €", "2600 €")
    attach_sources(db, row); db.commit()
    assert len(db.scalars(select(models.TemplateSource)).all()) == 1
    assert len(row.document["research"]["sources"]) == 1
    assert row.document["research"]["analysis"] == "saved analysis"
    assert "2600 €" in source.google_html


def test_create_template_automatically_attaches_knowledge(db):
    user, provider, _ = setup_template(db)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_auth] = lambda: {"id": user.id, "is_admin": True}
    client = TestClient(app)
    response = client.post("/site-templates", json={"brand": "Lemon Casino", "geo": "PL", "language": "pl",
        "ai_provider_id": provider.id, "collect_competitors": False})
    assert response.status_code == 202, response.text
    template_id = response.json()["id"]
    sources = client.get(f"/site-templates/{template_id}/sources").json()
    assert len(sources) == 1 and sources[0]["url"] == "https://lemonbonus24-7.com/"
    row = db.get(models.SiteTemplate, template_id)
    row.status = "sources_ready"; db.commit()
    assert client.post(f"/site-templates/{template_id}/generate-content").status_code == 202
    assert row.document["research"]["sources"][0]["origin"] == "knowledge_base"


@pytest.mark.parametrize("collect", [False, True])
def test_knowledge_reaches_analysis_and_content_without_recapturing_html(db, monkeypatch, collect):
    _, provider, row = setup_template(db, collect=collect)
    calls, searches = [], []

    async def forbidden(*args, **kwargs):
        raise AssertionError("Saved HTML must not be fetched again")

    async def serp(*args):
        searches.append(args)
        return {}

    async def gemini(provider, prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            assert "lemonbonus24-7.com" in prompt and "Dzienny limit wypłat 2500 €" in prompt
            result = "Competitor analysis from the user supplied Lemon Casino PL HTML. " * 3
        else:
            assert "Competitor analysis from the user supplied Lemon Casino PL HTML." in prompt
            assert "Dzienny limit wypłat 2500 €" in prompt
            result = json.dumps(content().model_dump())
        return {"candidates": [{"content": {"parts": [{"text": result}]}}]}

    monkeypatch.setattr(template_sources, "capture_google", forbidden)
    monkeypatch.setattr(services, "get_dataforseo_provider", lambda db: provider)
    monkeypatch.setattr(services, "call_dataforseo_google_serp", serp)
    monkeypatch.setattr(services, "extract_organic_serp_items", lambda result: [])
    monkeypatch.setattr(services, "call_gemini", gemini)
    assert asyncio.run(templates.generate(db, row, content_only=True))["status"] == "content_ready"
    assert len(calls) == 2 and len(searches) == int(collect)
    assert row.document["research"]["sources"][0]["html_source"] == "user_upload"
