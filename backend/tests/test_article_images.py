import asyncio
import base64
from copy import deepcopy
import io
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import article_images as images, article_images_api as api, models, services
from app.db import Base, get_db
from app.security import require_auth


def picture(color="blue", size=(1600, 400)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    return output.getvalue()


def article():
    return {"generation_meta": {"keep": "metadata"}, "pages": [{"slug": "/bonus/", "title": "Bonus", "content": {"blocks": [
        {"id": "h", "type": "header", "data": {"text": "Bonus", "level": 1}},
        {"id": "p1", "type": "paragraph", "data": {"text": "Welcome Brand"}},
        {"id": "cta", "type": "button", "data": {"button": "Brand bonus"}},
        {"id": "t", "type": "table", "data": {"content": [["Keep"]]}},
        {"id": "p2", "type": "paragraph", "data": {"text": "Second paragraph"}},
        {"id": "manual", "type": "image", "data": {"file": {"url": "https://site.test/keep.webp"}}},
        {"id": "p3", "type": "paragraph", "data": {"text": "Third paragraph"}},
    ]}}]}


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name="image.test", brand="Brand", site_type="monobrand", cache_geo="PL", cache_language="pl",
            base_url="https://image.test", publication_endpoint="https://image.test/api")
        provider = models.AiProvider(name="Gemini", provider_type="gemini", model="text-model", api_key="secret",
            endpoint_url="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")
        db.add_all([site, provider]); db.flush()
        task = models.GenerationTask(site_id=site.id, title="Images", geo="PL", language="pl", ai_provider_id=provider.id)
        db.add(task); db.flush()
        item = models.ContentItem(task_id=task.id, site_id=site.id, topic="Bonus", slug="/bonus/", generated_json=article(),
            status="generated", idempotency_key=str(uuid4()))
        db.add_all([item, models.AutoReglueConfig(key=images.CONFIG_KEY, value={"enabled": True, "model": images.DEFAULT_MODEL,
            "provider_id": provider.id, "include_logo": False})]); db.commit()
        yield db, site, item, provider


def test_low_banner_and_exact_logo_overlay():
    raw = picture("blue", (1600, 900))
    logo = {"data": base64.b64encode(picture("red", (40, 20))).decode()}
    with Image.open(io.BytesIO(images.prepare_image(raw, logo))) as image:
        assert image.size == (1200, 300) and image.format == "WEBP"
        pixel = image.getpixel((1150, 270))
        assert pixel[0] > 200 and pixel[2] < 60
    with pytest.raises(ValueError): images.prepare_image(b"not an image")
    with pytest.raises(ValueError): images.prepare_image(picture(size=(40, 20)))


def test_inserts_after_second_paragraph_preserving_native_blocks_and_no_duplicate():
    source = article(); before = deepcopy(source)
    asset = SimpleNamespace(id=str(uuid4()), model="image-model", details={})
    result = images.attach(source, asset, "Bonus")
    blocks = result["pages"][0]["content"]["blocks"]
    assert source == before
    assert blocks[4]["id"] == "p2" and blocks[5]["type"] == "image"
    assert blocks[5]["data"]["file"]["height"] == 300
    assert blocks[:5] + blocks[6:] == before["pages"][0]["content"]["blocks"]
    assert images.attach(result, asset, "Bonus") == result
    assert result["generation_meta"]["keep"] == "metadata"


def test_single_paragraph_fallback_and_empty_paragraph_ignored():
    assert images.image_position([{"type": "paragraph", "data": {"text": ""}},
        {"type": "paragraph", "data": {"text": "One"}}, {"type": "button", "data": {}}]) == 2
    assert images.image_position([{"type": "header", "data": {"text": "Heading"}}]) is None


def test_durable_asset_reused_on_retry_and_public_endpoint_exposes_only_webp(setup, monkeypatch):
    db, site, item, provider = setup
    calls = []
    async def request(provider, model, prompt):
        calls.append((model, prompt)); return picture()
    monkeypatch.setattr(images, "request_image", request)
    first = asyncio.run(images.generate_for_content(db, item, site, article(), provider))
    second = asyncio.run(images.generate_for_content(db, item, site, article(), provider))
    assert first == second and len(calls) == 1
    assert provider.model == "text-model"
    row = db.scalar(select(models.ArticleImage))
    assert row.status == "ready" and row.image_data
    assert "4:1" in row.prompt and '"topic": "Bonus"' in row.prompt
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.get(f"/article-images/media/{row.id}.webp")
        assert response.status_code == 200 and response.headers["content-type"] == "image/webp"
        assert response.content == row.image_data
        assert client.get(f"/article-images/media/{row.id}.webp", headers={"If-None-Match": response.headers["etag"]}).status_code == 304
        assert client.get("/article-images/settings").status_code == 401
        assert client.get(f"/article-images/media/{uuid4()}.webp").status_code == 404


def test_image_failure_keeps_finished_text_and_separate_retry_does_not_regenerate_text(setup, monkeypatch):
    db, site, item, provider = setup
    source = article()
    async def fail(*args): raise ValueError("Images HTTP 429")
    monkeypatch.setattr(images, "request_image", fail)
    with pytest.raises(ValueError, match="429"):
        asyncio.run(images.generate_for_content(db, item, site, source, provider))
    db.expire_all()
    assert item.generated_json["pages"] == source["pages"]
    assert item.generated_json["generation_meta"]["article_image"]["status"] == "failed"
    async def success(*args): return picture()
    monkeypatch.setattr(images, "request_image", success)
    item.status = "generating"
    result = asyncio.run(images.retry(db, item))
    assert result["status"] == "generated" and item.generation_error is None
    assert len(db.scalars(select(models.ArticleImage)).all()) == 1
    assert item.generated_json["pages"][0]["title"] == source["pages"][0]["title"]


def test_disabled_and_homepage_do_not_call_image_model(setup, monkeypatch):
    db, site, item, provider = setup
    async def bad(*args): raise AssertionError("must not call")
    monkeypatch.setattr(images, "request_image", bad)
    item.slug = "/"
    assert asyncio.run(images.generate_for_content(db, item, site, article(), provider)) == article()
    item.slug = "/bonus/"
    db.get(models.AutoReglueConfig, images.CONFIG_KEY).value = {"enabled": False}
    assert asyncio.run(images.generate_for_content(db, item, site, article(), provider)) == article()


def test_pipeline_waits_for_language_validation_then_adds_image(setup, monkeypatch):
    db, site, item, provider = setup
    calls = []
    async def build(**kwargs): return article()
    async def request(*args): calls.append("image"); return picture()
    monkeypatch.setattr(services, "build_ai_content", build)
    monkeypatch.setattr(services, "generated_content_uses_language", lambda *_: len(calls) > 0)
    monkeypatch.setattr(services, "detected_content_language", lambda _: "de")
    monkeypatch.setattr(images, "request_image", request)
    with pytest.raises(ValueError, match="language"):
        asyncio.run(services._build_task_content(db, item, provider=provider, site=site, language="pl", topic="Bonus"))
    assert not calls
    monkeypatch.setattr(services, "generated_content_uses_language", lambda *_: True)
    result = asyncio.run(services._build_task_content(db, item, provider=provider, site=site, language="pl", topic="Bonus"))
    assert result["generation_meta"]["article_image"]["status"] == "ready" and calls == ["image"]


def test_retry_endpoint_queues_only_one_job_and_rejects_published(setup):
    db, site, item, provider = setup
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_auth] = lambda: {"id": "admin", "is_admin": True}
    with TestClient(app) as client:
        assert client.post(f"/article-images/content/{item.id}/retry").status_code == 202
        assert client.post(f"/article-images/content/{item.id}/retry").status_code == 409
        jobs = db.scalars(select(models.BackgroundJob)).all()
        assert len(jobs) == 1 and jobs[0].kind == "article_image"
        item.status = "published"; db.commit()
        assert client.post(f"/article-images/content/{item.id}/retry").status_code == 409


def test_technical_page_skips_image_provider_even_when_enabled(setup, monkeypatch):
    db, site, item, provider = setup
    item.generation_context = {'content_kind': 'technical_page', 'technical_page_key': 'cookies'}
    payload = article()
    payload['pages'][0]['content']['blocks'] = [b for b in payload['pages'][0]['content']['blocks'] if b['type'] != 'image']
    def forbidden(*args, **kwargs):
        raise AssertionError('Technical pages must not request or attach generated images')
    monkeypatch.setattr(images, 'provider_for', forbidden)
    monkeypatch.setattr(images, 'attach', forbidden)
    result = asyncio.run(images.generate_for_content(db, item, site, payload, provider))
    assert result == payload
    assert not db.scalars(select(models.ArticleImage)).all()
