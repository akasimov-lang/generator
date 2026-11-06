from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, services
from app.db import Base
from app.page_generation_structure import DEFAULT_PROMPT, INSTRUCTION, MARKER, page_brief
from app.schemas import GenerationTaskCreate


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def render(template=None, kind="menu_page"):
    return services.build_gemini_prompt(
        topic="Tworzenie konta", geo="PL", language="pl", target_words=1600,
        site=None, prompt_template=template, shortcode=None, include_toc=True,
        include_faq=False, generation_context={"content_kind": kind},
    )


def test_new_task_does_not_inherit_saved_base_and_keeps_specific_brief(db):
    base = models.PromptTemplate(name=services.BASE_PROMPT_TEMPLATE_NAME,
                                content="BASE RULE: always include 20 sections", is_default=False)
    db.add(base)
    db.flush()
    task = services.create_generation_task(db, GenerationTaskCreate(
        topics=["Tworzenie konta"], geo="PL", language="pl",
        collect_competitors=False, save_as_draft=True,
        prompt_template="Use supplied account facts and include a comparison.",
    ))
    assert "BASE RULE" not in task.prompt_template
    assert task.prompt_template.startswith("Use supplied account facts and include a comparison.")
    assert INSTRUCTION in task.prompt_template
    assert base.content == "BASE RULE: always include 20 sections"


def test_saved_composed_task_loses_only_automatic_base_during_generation():
    legacy = ("BASE RULE: require legal section\n" + services.PROMPT_FORMAT_CONTRACT_MARKER
              + "\nРАБОЧИЙ ПРОМПТ ДЛЯ КОНКРЕТНОЙ ЗАДАЧИ:\n"
                "My custom section: registration steps.\nKeep the anchor Pelican exactly once.")
    result = render(legacy)
    assert "BASE RULE" not in result
    assert "My custom section: registration steps." in result
    assert "Keep the anchor Pelican exactly once." in result
    assert result.count(MARKER) == 1
    assert result.count(services.PROMPT_FORMAT_CONTRACT_MARKER) == 1


def test_old_factory_outline_is_replaced_but_appended_menu_and_anchor_context_survives():
    legacy = ('Рабочий промпт для конкретной задачи.\n\nБазовые требования качества, юридической осторожности '
              'и формата ответа применяются отдельно через "Базовый промпт".\n'
              'H2: Intro\nH2: Quick Answer\nH2: Lizenz und rechtlicher Rahmen\n'
              '- Nächste Prüfung vor Veröffentlichung: ...\n\n'
              'Current menu section: Rejestracja. Link to / using Pelican.')
    result = render(legacy)
    assert "H2: Intro" not in result
    assert "H2: Quick Answer" not in result
    assert "H2: Lizenz" not in result
    assert "Current menu section: Rejestracja. Link to / using Pelican." in result
    assert "Тема: Tworzenie konta" in result


@pytest.mark.parametrize("kind", ["article", "menu_page", "casino_review", "technical_page"])
def test_free_structure_and_intro_rule_apply_with_old_format_contract(kind):
    result = render("Use only supplied facts.\n" + services.PROMPT_FORMAT_CONTRACT_MARKER, kind)
    assert INSTRUCTION in result
    assert "- Language: pl" in result
    assert "- Include FAQ: no" in result
    assert page_brief(page_brief(None)) == page_brief(None)


@pytest.mark.parametrize("heading", ["H2: Intro", "## Introduction", "H2: Введение", "H2: Wstęp",
                                      "H2: Úvod", "H2: Einleitung", "Intro:", "**Intro**"])
def test_generated_intro_heading_is_removed_and_body_stays_before_contents(heading):
    blocks = services.build_blocks_from_ai_text(
        heading + "\nNajpierw przygotuj dokument.\nH2: Rejestracja krok po kroku\nWypełnij formularz.",
        "Tworzenie konta", None, True, False,
    )
    assert blocks[0]["data"]["level"] == 1
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["data"]["text"] == "Najpierw przygotuj dokument."
    assert blocks[2].get("pagepilot_toc")
    headers = [services.clean_text(b["data"]["text"]) for b in blocks if b["type"] == "header"]
    assert headers == ["Tworzenie konta", "Rejestracja krok po kroku"]
    assert "Wypełnij formularz." in str(blocks)
    assert len(blocks[2]["data"]["items"]) == 2


def test_meaningful_heading_and_mentions_of_introduction_are_preserved():
    blocks = services.build_blocks_from_ai_text(
        "This introduction explains registration.\nH2: Introduction to payment security\nUse secure methods.",
        "Account guide", None, False, False,
    )
    assert blocks[1]["data"]["text"] == "This introduction explains registration."
    assert blocks[2]["data"]["text"] == "Introduction to payment security"


def test_default_editor_draft_matches_free_generation_brief():
    source = (Path(__file__).resolve().parents[2] / "frontend/src/main.tsx").read_text()
    draft = source.split("const DEFAULT_PROMPT_DRAFT = `", 1)[1].split("`;", 1)[0]
    assert draft == DEFAULT_PROMPT + "\n\n" + INSTRUCTION
