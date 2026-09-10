import asyncio
import copy
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models, services, technical_pages as technical
from app.db import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def setup(db, name="example.com", keys=("privacy",), language="de", menu="footer"):
    site = models.Site(name=name, base_url=f"https://{name}", publication_endpoint="https://publisher.test",
                       homepage_title="Example — unabhängige Casino Informationen", default_menu={"header": [{"id": 1, "title": "Home", "slug": "/", "order": 0}], "footer": []})
    provider = models.AiProvider(name="Gemini", provider_type="gemini", endpoint_url="https://provider.test", api_key="test-key", is_active=True)
    db.add_all([site, provider])
    db.commit()
    payload = technical.TechnicalPagesRequest(brand="Example", facts="Informational affiliate website. Contact: contact@example.com. No accounts or payments.",
        geo="DE", language=language, ai_provider_id=provider.id,
        menu_type=menu, pages=[{"key": key, "label": "Datenschutz" if key == "privacy" else technical.BY_KEY[key]["label"]} for key in keys])
    return site, provider, payload


def article(seed="original"):
    body = " ".join(f"{seed}{i} Informationen über diese Webseite und ihre Besucher" for i in range(40))
    return {"pages": [{"title": "Datenschutz bei Example", "slug": "/privacy-policy/", "content": {"blocks": [
        {"type": "header", "data": {"text": "Datenschutz", "level": 1}},
        *[{"type": "paragraph", "data": {"text": " ".join(body.split()[i:i + 50])}} for i in range(0, len(body.split()), 50)],
    ]}}]}


def test_creation_keeps_stable_menu_and_context(db):
    site, _, payload = setup(db, keys=("privacy", "contacts"))
    task = technical.create_task(db, site, payload, None)
    assert task.generation_mode == "technical_pages"
    assert len(task.items) == 2
    assert task.auto_publish and task.generate_title
    assert not task.include_faq and not task.include_toc and not task.collect_competitors
    assert task.items[0].section_content_mode == "menu_page"
    assert task.items[0].generation_context["homepage_title"] == site.homepage_title
    assert site.default_menu["header"][0]["title"] == "Home"
    assert site.default_menu["footer"] == []  # Only local draft menu until publication.
    assert site.technical_page_settings["brand"] == "Example"
    with pytest.raises(ValueError, match="уже существуют"):
        technical.create_task(db, site, payload, None)
    assert len(db.scalars(select(models.GenerationTask)).all()) == 1


@pytest.mark.parametrize("menu", ["header", "footer"])
def test_full_catalog_and_selected_menu(db, menu):
    site, _, payload = setup(db, keys=tuple(technical.BY_KEY), menu=menu)
    task = technical.create_task(db, site, payload, None)
    assert len(task.items) == 10
    assert len({item.slug for item in task.items}) == 10
    assert {section.menu_type for section in db.scalars(select(models.Section))} == {menu}


def test_missing_facts_title_provider_and_duplicate_types_rejected(db):
    site, _, payload = setup(db)
    for overrides in [{"pages": [{"key": "privacy"}, {"key": "privacy"}]}, {"pages": [{"key": "unknown"}]}, {"geo": "  "}]:
        with pytest.raises(ValueError):
            technical.TechnicalPagesRequest(**{**payload.model_dump(), **overrides})
    site.homepage_title = ""
    with pytest.raises(ValueError, match="Title"):
        technical.create_task(db, site, payload, None)
    site.homepage_title = "Example"
    payload.ai_provider_id = "missing"
    with pytest.raises(ValueError, match="Gemini"):
        technical.create_task(db, site, payload, None)


def test_preview_translates_only_labels_and_keeps_keys(db, monkeypatch):
    site, _, payload = setup(db)
    payload.pages[0].label = ""
    async def fake(provider, prompt):
        assert "privacy" in prompt and '"language": "de"' in prompt
        return {"candidates": [{"content": {"parts": [{"text": '{"labels":{"privacy":"Datenschutz"}}'}]}}]}
    monkeypatch.setattr(services, "call_gemini", fake)
    result = asyncio.run(technical.preview_pages(db, site, payload))
    assert result["pages"][0]["label"] == "Datenschutz"
    assert result["pages"][0]["path"] == "/datenschutz/"


def test_generation_and_revisions_stop_after_two_automatic_rewrites(db, monkeypatch):
    site, provider, payload = setup(db)
    first = technical.create_task(db, site, payload, None).items[0]
    technical.validate_and_record(db, first, article())
    db.commit()
    second_site, _, second_payload = setup(db, name="second.example")
    second = technical.create_task(db, second_site, second_payload, None).items[0]
    with pytest.raises(technical.TechnicalSimilarityError):
        technical.validate_and_record(db, second, article())
    calls = []
    async def fake(**kwargs):
        calls.append(kwargs["prompt_template"])
        return article()
    monkeypatch.setattr(services, "build_ai_content", fake)
    with pytest.raises(ValueError, match="двух автоматических доработок"):
        asyncio.run(technical.generate_checked(db, second, provider=provider))
    assert len(calls) == 3
    calls.clear()
    with pytest.raises(ValueError, match="двух автоматических доработок"):
        asyncio.run(technical.generate_checked(db, second, provider=provider, technical_revision=True, prompt_template="EDITOR: shorten paragraphs"))
    assert len(calls) == 3
    assert "REJECTED DRAFT" in calls[1] and "original0" in calls[1]
    assert "EDITOR: shorten paragraphs" in calls[2]


@pytest.mark.parametrize("field,value", [("geo", "FR"), ("language", "fr"), ("brand", "Other")])
def test_comparison_scope(db, field, value):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    technical.validate_and_record(db, item, article())
    db.commit()
    other = models.ContentItem(id="other", generation_context={**item.generation_context, field: value})
    assert technical.corpus(db, other) == []


def test_prompt_has_homepage_brand_facts_and_previous_texts(db):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    prompt = technical.technical_prompt(db, item)
    assert site.homepage_title in prompt and "TITLE REQUIREMENT" in prompt
    assert payload.facts in prompt and "Example" in prompt
    assert technical.group_key(item.generation_context) == technical.group_key({**item.generation_context, "brand": " EXAMPLE ", "geo": "de"})


def test_generation_and_publication_guard_and_drafts_excluded_from_menu(db, monkeypatch):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    assert services.build_project_menu_payload(db, site, "footer")["list"] == []
    async def fake(**kwargs):
        assert kwargs["include_faq"] is False
        assert "TITLE REQUIREMENT" in kwargs["prompt_template"]
        return article()
    monkeypatch.setattr(services, "build_ai_content", fake)
    services.generate_content_item(db, item)
    assert item.status == "generated"
    assert services.build_project_menu_payload(db, site, "footer")["list"][0]["title"] == "Datenschutz"
    services.validate_content_for_publication(item)
    altered = copy.deepcopy(item.generated_json)
    altered["pages"][0]["content"]["blocks"][1]["data"]["text"] = "Manual unverified edit"
    item.generated_json = altered
    with pytest.raises(ValueError, match="проверку сходства"):
        services.validate_content_for_publication(item)


def test_editor_check_blocks_publication(db):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    result = {**article(), "generation_meta": {"editor_check": "Contact email is unknown"}}
    with pytest.raises(ValueError, match="Contact email is unknown"):
        technical.validate_and_record(db, item, result)


def test_published_revision_preserves_url_and_runs_comparison(db, monkeypatch):
    site, _, payload = setup(db)
    task = technical.create_task(db, site, payload, None)
    item = task.items[0]
    source = article()
    source["pages"][0]["slug"] = item.slug
    item.generated_json = source
    item.status = "published"
    item.generated_at = datetime.now(timezone.utc)
    item.published_at = datetime.now(timezone.utc)
    revision = models.ContentRevision(content_item_id=item.id, source_json=source, remarks="Make the explanation clearer", source_status="published", is_published_replacement=True, generate_title=True)
    db.add(revision)
    db.commit()
    original_slug, original_section = item.slug, item.section_id
    async def fake(**kwargs):
        assert "Make the explanation clearer" in kwargs["prompt_template"]
        result = article()
        result["pages"][0]["slug"] = "/wrong-new-url/"
        return result
    monkeypatch.setattr(services, "build_ai_content", fake)
    services.revise_content_item(db, item, revision)
    assert item.slug == original_slug and item.section_id == original_section
    assert item.generated_json["pages"][0]["slug"] == original_slug
    assert item.generation_context["technical_check"]["automatic_revisions"] == 0
    assert revision.status == "completed"


def test_menu_failure_stops_publication(db, monkeypatch):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    technical.validate_and_record(db, item, article(), compare=False)
    item.generated_json = article()
    item.status = "approved"
    db.commit()
    async def fail(*args, **kwargs):
        raise ValueError("menu endpoint unavailable")
    monkeypatch.setattr(services, "sync_technical_menu", fail)
    asyncio.run(services.publish_item(db, item, site))
    assert item.status == "publication_failed"
    assert "menu endpoint unavailable" in item.generation_error


def test_supplied_preview_path_is_kept_after_label_edit(db):
    site, _, payload = setup(db)
    payload.pages[0].path = "/datenschutz/"
    payload.pages[0].label = "Datenschutzinformation"
    task = technical.create_task(db, site, payload, None)
    assert task.items[0].slug == "/datenschutz/"


def test_policy_types_are_compared_within_same_brand_geo_language(db):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    technical.validate_and_record(db, item, article())
    db.commit()
    other = models.ContentItem(id="other", generation_context={**item.generation_context, "brand": "EXAMPLE", "technical_page_key": "contacts"})
    assert len(technical.corpus(db, other)) == 1


def test_unique_rewrite_is_accepted_on_second_attempt(db, monkeypatch):
    site, provider, payload = setup(db)
    first = technical.create_task(db, site, payload, None).items[0]
    technical.validate_and_record(db, first, article())
    db.commit()
    other_site, _, other_payload = setup(db, name="second.example")
    item = technical.create_task(db, other_site, other_payload, None).items[0]
    calls = []
    unique = article()
    unique["pages"][0]["content"]["blocks"] = [{"type": "paragraph", "data": {"text": " ".join(f"unique{i}" for i in range(550))}}]
    async def fake(**kwargs):
        calls.append(kwargs)
        return article() if len(calls) == 1 else unique
    monkeypatch.setattr(services, "build_ai_content", fake)
    result = asyncio.run(technical.generate_checked(db, item, provider=provider))
    assert result == unique and len(calls) == 2
    assert item.generation_context["technical_check"]["automatic_revisions"] == 1
    assert item.generation_context["technical_check"]["compared"] == 1


def test_defaults_are_simple_and_target_550_words(db):
    _, _, payload = setup(db)
    minimal = technical.TechnicalPagesRequest(**{**payload.model_dump(), "brand": "", "facts": ""})
    assert minimal.target_words == 550
    assert "500–600" in technical.TECHNICAL_PROMPT


def test_detected_brand_must_appear_in_homepage(db, monkeypatch):
    site, _, payload = setup(db)
    async def fake(provider, prompt):
        return {"candidates": [{"content": {"parts": [{"text": '{"brand":"Invented","labels":{}}'}]}}]}
    monkeypatch.setattr(services, "call_gemini", fake)
    assert asyncio.run(technical.preview_pages(db, site, payload))["brand"] == ""


def test_technical_prompt_overrides_generic_editor_report_and_allows_missing_facts(db):
    site, _, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    common = dict(topic=item.topic, geo="DE", language="de", target_words=550,
                  site=site, prompt_template=technical.TECHNICAL_PROMPT,
                  shortcode=None, include_toc=False, include_faq=False)
    prompt = services.build_gemini_prompt(**common, generation_context=item.generation_context)
    assert "authorizes inventing plausible" in prompt
    assert "Missing website information alone must not produce Editor Check" in prompt
    assert prompt.index("TECHNICAL PAGE EDITOR CHECK CONTRACT") > prompt.index(services.PROMPT_FORMAT_CONTRACT_MARKER)
    assert "TECHNICAL PAGE EDITOR CHECK CONTRACT" not in services.build_gemini_prompt(**common)


def test_routine_editor_report_is_automatically_revised(db, monkeypatch):
    site, provider, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    calls = []
    async def fake(**kwargs):
        calls.append(kwargs["prompt_template"])
        result = article()
        if len(calls) == 1:
            result["generation_meta"] = {"editor_check": "Паспорт вариативности: V04. Структура: OK"}
        return result
    monkeypatch.setattr(services, "build_ai_content", fake)
    result = asyncio.run(technical.generate_checked(db, item, provider=provider))
    assert len(calls) == 2
    assert "checks silently" in calls[1]
    assert "V04" in calls[1]
    assert "editor_check" not in result.get("generation_meta", {})
    assert item.generation_context["technical_check"]["automatic_revisions"] == 1
    assert len(db.scalars(select(models.TechnicalPageText)).all()) == 1


def test_unresolved_editor_check_stops_after_two_revisions(db, monkeypatch):
    site, provider, payload = setup(db)
    item = technical.create_task(db, site, payload, None).items[0]
    calls = []
    async def fake(**kwargs):
        calls.append(kwargs)
        return {**article(), "generation_meta": {"editor_check": "Conflicting supplied operator names"}}
    monkeypatch.setattr(services, "build_ai_content", fake)
    with pytest.raises(technical.TechnicalEditorCheckError, match="Conflicting supplied operator names"):
        asyncio.run(technical.generate_checked(db, item, provider=provider))
    assert len(calls) == 3
    assert db.scalars(select(models.TechnicalPageText)).all() == []
    assert "technical_check" not in item.generation_context
