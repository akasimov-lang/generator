import asyncio
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, services as service_module
from app.db import Base
from app.schemas import GenerationTaskCreate, MenuStructureGenerationCreate, MenuStructurePreviewRequest
from app.services import (
    CASINO_REVIEW_PROMPT_NAME,
    MENU_STRUCTURE_PROMPT_MARKER,
    apply_content_section_slug,
    auto_publish_generated_task,
    build_gemini_prompt,
    create_generation_task,
    create_menu_structure_task,
    normalize_generated_menu_structure,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSession() as session:
        yield session


def make_site(db: Session) -> models.Site:
    site = models.Site(
        name="casino.example",
        base_url="https://casino.example",
        publication_endpoint="https://publisher.example/pages",
        payload_mode="simple_page",
    )
    db.add(site)
    db.flush()
    return site


def test_generated_menu_rejects_long_article_title_as_label() -> None:
    with pytest.raises(ValueError, match="exceeds 40 characters"):
        normalize_generated_menu_structure(
            [{"title": "Kryptowaluty w kasynach online: kompletny przewodnik po bezpiecznych płatnościach"}],
            levels=1,
            mode="thematic",
            top_level_count=1,
        )


def test_generated_casino_review_structure_requires_one_geo_parent_and_ten_brands() -> None:
    raw_items = [{
        "title": "Kasyno online recenzje",
        "children": [{"title": f"Casino Brand {index}"} for index in range(1, 11)],
    }]

    items = normalize_generated_menu_structure(raw_items, levels=2, mode="casino_reviews")

    assert len(items) == 1
    assert items[0]["content_kind"] == "menu_page"
    assert len(items[0]["children"]) == 10
    assert all(item["content_kind"] == "casino_review" for item in items[0]["children"])


def test_generated_casino_review_structure_rejects_wrong_brand_count() -> None:
    with pytest.raises(ValueError, match="exactly 10"):
        normalize_generated_menu_structure(
            [{"title": "Reviews", "children": [{"title": "Only Brand"}]}],
            levels=2,
            mode="casino_reviews",
        )


def test_generated_thematic_structure_enforces_selected_top_level_count() -> None:
    raw_items = [{"title": "Bonuses"}, {"title": "Games"}, {"title": "Guides"}]

    items = normalize_generated_menu_structure(
        raw_items,
        levels=1,
        mode="thematic",
        top_level_count=3,
    )

    assert [item["title"] for item in items] == ["Bonuses", "Games", "Guides"]
    with pytest.raises(ValueError, match="exactly 4 top-level"):
        normalize_generated_menu_structure(
            raw_items,
            levels=1,
            mode="thematic",
            top_level_count=4,
        )


def test_menu_preview_retries_titles_already_used_by_another_project_in_same_geo(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = make_site(db)
    site.cache_geo = "PL"
    site.cache_language = "pl"
    site.homepage_title = "Kasyna online"
    other_site = models.Site(
        name="other-casino.example",
        base_url="https://other-casino.example",
        publication_endpoint="https://other-casino.example/api/content",
        cache_geo="PL",
        cache_language="pl",
        default_menu={
            "header": [{"id": 1, "title": "Bonusy", "slug": "/bonusy/", "order": 0}],
            "footer": [],
        },
    )
    provider = models.AiProvider(
        name="Gemini",
        provider_type="gemini",
        endpoint_url="https://gemini.example",
        model="test",
        api_key="secret",
        is_active=True,
    )
    db.add_all([other_site, provider])
    db.commit()
    responses = [
        {"items": [{"title": "Bonusy"}, {"title": "Gry"}]},
        {"items": [{"title": "Metody płatności"}, {"title": "Bezpieczna gra"}]},
    ]
    prompts: list[str] = []

    async def fake_call_gemini(_provider: models.AiProvider, prompt: str) -> dict:
        prompts.append(prompt)
        payload = responses.pop(0)
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}], "usageMetadata": {}}

    monkeypatch.setattr(service_module, "call_gemini", fake_call_gemini)

    preview = asyncio.run(service_module.generate_menu_structure_preview(
        db,
        provider,
        site,
        MenuStructurePreviewRequest(menu_type="header", levels=1, top_level_count=2, mode="thematic"),
    ))

    assert [item["title"] for item in preview["items"]] == ["Metody płatności", "Bezpieczna gra"]
    assert len(prompts) == 2
    assert "independent search intent" in prompts[0]
    assert "already used in this GEO" in prompts[1]
    preview_log = db.scalar(select(models.PublicationLog).where(models.PublicationLog.response_status == 200))
    assert preview_log is not None
    assert preview_log.request_payload["action"] == "menu_structure_preview"


def test_casino_review_mode_uses_system_prompt_and_brand_context(db: Session) -> None:
    site = make_site(db)
    section = models.Section(site_id=site.id, external_id="casinos", name="Casinos", path="/casinos/")
    db.add(section)
    db.commit()

    task = create_generation_task(
        db,
        GenerationTaskCreate(
            site_id=site.id,
            section_id=section.id,
            geo="PL",
            language="pl",
            topics=["Alpha Casino", "Alpha Casino", "Beta Casino"],
            generation_mode="casino_reviews",
            collect_competitors=False,
            include_casino_rating=True,
        ),
    )

    assert task.title == "Обзоры казино · 2 брендов · PL-PL"
    assert task.prompt_template_name == CASINO_REVIEW_PROMPT_NAME
    assert task.generation_mode == "casino_reviews"
    assert task.include_casino_rating is False
    assert all(item.include_casino_rating is False for item in task.items)
    assert [item.generation_context["casino_brand"] for item in task.items] == ["Alpha Casino", "Beta Casino"]
    assert all(item.generation_context["hero_image_slot"] == "hero_after_h1" for item in task.items)
    assert db.scalar(select(models.PromptTemplate).where(models.PromptTemplate.name == CASINO_REVIEW_PROMPT_NAME))


def test_menu_structure_mode_creates_one_main_page_per_unique_path(db: Session) -> None:
    site = make_site(db)
    root = models.Section(site_id=site.id, external_id="casino", name="Casino", path="/casino/", menu_type="header")
    child = models.Section(site_id=site.id, external_id="bonuses", name="Bonuses", path="/bonuses/", menu_type="header", parent_id=root.id)
    duplicate_footer = models.Section(site_id=site.id, external_id="bonuses-footer", name="Bonuses", path="/bonuses/", menu_type="footer")
    db.add_all([root, child, duplicate_footer])
    db.commit()

    task = create_menu_structure_task(
        db,
        site,
        MenuStructureGenerationCreate(
            geo="PL",
            language="pl",
            collect_competitors=False,
            menu_types=["header", "footer"],
            auto_publish=True,
        ),
    )

    assert task.generation_mode == "menu_structure"
    assert task.auto_publish is True
    assert task.topics_count == 2
    assert {item.slug for item in task.items} == {"/casino/", "/bonuses/"}
    assert all(item.section_content_mode == "menu_page" for item in task.items)
    assert all(item.generation_context["content_kind"] == "menu_page" for item in task.items)
    assert MENU_STRUCTURE_PROMPT_MARKER in task.prompt_template


def test_menu_structure_mode_adopts_cached_children_and_expands_selected_root(db: Session) -> None:
    site = make_site(db)
    root = models.Section(
        site_id=site.id,
        external_id="100",
        name="Online casinoer",
        path="/online-casinoer/",
        menu_type="header",
        sync_status="synced",
    )
    db.add(root)
    db.flush()
    site.default_menu = {
        "header": [
            {
                "id": 100,
                "title": "Online casinoer",
                "slug": "/online-casinoer/",
                "order": 0,
                "children": [
                    {"id": 101, "title": "Bedste online casinoer", "slug": "/bedste-online-casinoer/", "order": 0},
                    {"id": 102, "title": "Nye casinoer", "slug": "/nye-casinoer/", "order": 1},
                ],
            },
            {"id": 200, "title": "Guides", "slug": "/guides/", "order": 1},
        ],
        "footer": [],
    }
    db.commit()

    task = create_menu_structure_task(
        db,
        site,
        MenuStructureGenerationCreate(
            geo="DK",
            language="da",
            collect_competitors=False,
            menu_types=["header"],
            section_ids=[root.id],
        ),
    )

    assert task.topics_count == 3
    assert {item.topic for item in task.items} == {
        "Online casinoer",
        "Bedste online casinoer",
        "Nye casinoer",
    }
    child_sections = {section.name: section for section in db.scalars(
        select(models.Section).where(models.Section.site_id == site.id)
    ).all()}
    assert child_sections["Bedste online casinoer"].parent_id == root.id
    assert child_sections["Nye casinoer"].parent_id == root.id
    child_item = next(item for item in task.items if item.topic == "Bedste online casinoer")
    assert child_item.generation_context["current_section"]["breadcrumb"] == [
        "Online casinoer",
        "Bedste online casinoer",
    ]


@pytest.mark.parametrize("enabled", [False, True])
def test_menu_structure_mode_uses_explicit_review_switch(db: Session, enabled: bool) -> None:
    site = make_site(db)
    root = models.Section(site_id=site.id, external_id="100", name="Casino reviews", path="/casino-reviews/", menu_type="header", sync_status="synced")
    db.add(root)
    db.flush()
    brand = models.Section(site_id=site.id, external_id="101", name="Alpha Casino", path="/casino-reviews/alpha-casino/", menu_type="header", parent_id=root.id, sync_status="synced", is_review=enabled)
    db.add(brand)
    db.add(models.PublicationLog(
        endpoint_url="internal://generated-menu",
        response_status=200,
        request_payload={
            "action": "generated_menu_structure_apply",
            "project_name": site.name,
            "review_paths": ["/casino-reviews/alpha-casino/"],
        },
    ))
    db.commit()

    task = create_menu_structure_task(
        db,
        site,
        MenuStructureGenerationCreate(
            geo="PL",
            language="pl",
            collect_competitors=False,
            menu_types=["header"],
        ),
    )

    brand_item = next(item for item in task.items if item.section_id == brand.id)
    assert brand_item.generation_context["content_kind"] == ("casino_review" if enabled else "menu_page")
    if enabled:
        assert brand_item.generation_prompt_name == CASINO_REVIEW_PROMPT_NAME
        assert brand_item.generation_context["casino_brand"] == "Alpha Casino"
        assert service_module._prompt_template_for_task_item(db, task, brand_item)
    else:
        assert "casino_brand" not in brand_item.generation_context
    root_item = next(item for item in task.items if item.section_id == root.id)
    assert root_item.generation_context["content_kind"] == "menu_page"


def test_generation_context_is_rendered_for_gemini() -> None:
    context = {
        "content_kind": "casino_review",
        "casino_brand": "Alpha Casino",
        "current_section": {"name": "Casinos", "path": "/casinos/"},
        "site_menu": [{"name": "Casinos", "path": "/casinos/"}],
    }
    prompt = build_gemini_prompt(
        topic="Alpha Casino",
        geo="PL",
        language="pl",
        target_words=2000,
        site=None,
        prompt_template="Brand={{BRAND_NAME}} Section={{CURRENT_SECTION}} Menu={{MENU_STRUCTURE}}",
        shortcode=None,
        include_toc=True,
        include_faq=True,
        generation_context=context,
    )

    assert "Brand=Alpha Casino" in prompt
    assert '"path": "/casinos/"' in prompt
    assert "{{BRAND_NAME}}" not in prompt


def test_top_level_menu_page_prompt_uses_exact_homepage_title_as_brand_context(db: Session) -> None:
    site = make_site(db)
    site.homepage_title = "Beste Ausländische Online Casinos Schweiz 2026 | Top 10 Online Casino"

    prompt = build_gemini_prompt(
        topic="Modes de Paiement",
        geo="FR",
        language="fr",
        target_words=1800,
        site=site,
        prompt_template="Homepage={{HOMEPAGE_TITLE}} Brand={{PROJECT_BRAND}}",
        shortcode=None,
        include_toc=True,
        include_faq=True,
        generate_title=False,
        generation_context={
            "content_kind": "menu_page",
            "current_section": {
                "name": "Modes de Paiement",
                "path": "/modes-de-paiement/",
                "breadcrumb": ["Modes de Paiement"],
            },
        },
    )

    assert site.homepage_title in prompt
    assert "Infer the project brand only from that homepage title" in prompt
    assert "internal page SEO title distinct from the homepage" in prompt
    assert "Title must repeat the Topic exactly" not in prompt


def test_matching_menu_page_never_becomes_a_nested_duplicate() -> None:
    section = models.Section(name="Modes de Paiement", path="/modes-de-paiement/")
    item = models.ContentItem(
        topic="Modes de Paiement",
        slug="/modes-de-paiement/",
        section_content_mode="nested",
        generated_json={
            "pages": [{"title": "Modes de Paiement", "slug": "/modes-de-paiement/", "content": {"blocks": []}}],
        },
        idempotency_key="matching-menu-page",
    )

    slug = apply_content_section_slug(item, section)

    assert slug == "/modes-de-paiement/"
    assert item.section_content_mode == "menu_page"
    assert item.generated_json["pages"][0]["slug"] == "/modes-de-paiement/"


def test_auto_publish_accepts_and_publishes_each_valid_item(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    site = make_site(db)
    section = models.Section(site_id=site.id, external_id="guides", name="Guides", path="/guides/")
    task = models.GenerationTask(
        title="Structure",
        site_id=site.id,
        geo="PL",
        language="pl",
        topics_count=1,
        generation_mode="menu_structure",
        auto_publish=True,
        status="generated",
    )
    item = models.ContentItem(
        task=task,
        site_id=site.id,
        section_id=section.id,
        section_content_mode="menu_page",
        topic="Guides",
        slug="/guides/",
        status="generated",
        idempotency_key="auto-publish-guides",
        generated_json={
            "pages": [{
                "slug": "/guides/",
                "title": "Guides",
                "content": {"blocks": [
                    {"type": "header", "data": {"text": "Guides", "level": 1}},
                    {"type": "header", "data": {"text": "Details", "level": 2}},
                    {"type": "paragraph", "data": {"text": "Complete editorial content for publication."}},
                ]},
            }],
        },
    )
    db.add_all([section, task, item])
    db.commit()

    async def fake_publish(db_session: Session, content: models.ContentItem, target_site: models.Site, initiator_username: str | None = None) -> None:
        assert content.status == "approved"
        assert target_site.id == site.id
        assert initiator_username == "automatic-menu-generation"
        content.status = "published"
        db_session.commit()

    monkeypatch.setattr(service_module, "publish_item", fake_publish)
    auto_publish_generated_task(db, task)

    assert task.status == "published"
    assert item.status == "published"
