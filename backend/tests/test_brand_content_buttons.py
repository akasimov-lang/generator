from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.brand_content_buttons import apply_brand_content_buttons, generation_instruction, valid_label, ensure_label

SITE = SimpleNamespace(brand="Vox Casino", site_type="monobrand")


def block(kind, **data):
    return {"id": kind, "type": kind, "data": data}


LABEL = "Bonus bei Vox Casino aktivieren"


def payload(*blocks, slug="/promo-codes/", brand="Vox Casino", label=LABEL):
    return {"generation_meta": {"content_button": {"brand": brand, "text": label}}, "custom": "keep", "pages": [{"slug": slug, "title": "Keep title", "custom": "keep-page",
            "content": {"version": "keep-version", "blocks": list(blocks)}}]}


def blocks(result):
    return result["pages"][0]["content"]["blocks"]


def test_cta_after_intro_table_like_reference_without_changing_source():
    source = payload(block("header", text="Heading", level=1), block("paragraph", text="Intro", custom="keep"),
                     block("header", text="Offers", level=3), block("table", content=[["Code", "Offer"]]),
                     block("paragraph", text="Next paragraph"))
    before = deepcopy(source)
    result = apply_brand_content_buttons(source, SITE)
    assert source == before
    button = blocks(result)[4]
    assert button["type"] == "button" and button["data"] == {"button": LABEL}
    assert result == {**source, "pages": [{**source["pages"][0], "content": {
        **source["pages"][0]["content"], "blocks": [*blocks(source)[:4], button, *blocks(source)[4:]]}}]}
    assert apply_brand_content_buttons(result, SITE) == result


def test_distant_table_does_not_delay_first_paragraph_button():
    source = payload(block("paragraph", text="Intro"), block("paragraph", text="More text"),
                     block("table", content=[["Later"]]))
    result = blocks(apply_brand_content_buttons(source, SITE))
    assert [b["type"] for b in result] == ["paragraph", "button", "paragraph", "table"]


def test_table_first_is_supported_and_shortcode_wrappers_are_preserved():
    source = payload(block("shortcode", shortcode="section-open"), block("header", text="Offers", level=1),
                     block("table", content=[["Code"]]), block("shortcode", shortcode="section-close"))
    result = blocks(apply_brand_content_buttons(source, SITE))
    assert [b["type"] for b in result] == ["shortcode", "header", "table", "button", "shortcode"]


def test_existing_cta_keeps_custom_copy_and_fields_without_adding_duplicate():
    source = payload(block("paragraph", text="Intro"), block("button", button="Bonus aktivieren", custom="keep", link="keep-link"))
    result = apply_brand_content_buttons(source, SITE)
    assert len(blocks(result)) == 2
    assert blocks(result)[1] == {**blocks(source)[1], "data": {
        **blocks(source)[1]["data"], "button": LABEL}}
    assert apply_brand_content_buttons(result, SITE) == result


def test_older_draft_without_ai_copy_is_unchanged():
    source = payload(block("paragraph", text="Intro"), block("button", button="Go to <b>VOX Casino</b>"))
    source.pop("generation_meta")
    assert apply_brand_content_buttons(source, SITE) == source


@pytest.mark.parametrize("site", [None, SimpleNamespace(brand="Общие ключи", site_type=None),
                                  SimpleNamespace(brand="Old Brand", site_type="general")])
def test_general_sites_without_a_review_brand_are_not_given_a_fake_brand(site):
    source = payload(block("paragraph", text="Intro"))
    assert apply_brand_content_buttons(source, site) == source


def test_review_uses_its_casino_brand_instead_of_generic_project_brand():
    source = payload(block("paragraph", text="Intro"), brand="22Bet", label="22Bet Spiele entdecken")
    result = apply_brand_content_buttons(source, SimpleNamespace(brand="Общие ключи", site_type="general"),
        {"content_kind": "casino_review", "casino_brand": "22Bet"})
    assert next(b for b in blocks(result) if b['type']=='button')["data"]["button"] == "22Bet Spiele entdecken"


def test_homepage_and_empty_or_malformed_documents_are_not_changed():
    source = payload(block("paragraph", text="Intro"), slug="/")
    assert apply_brand_content_buttons(source, SITE) == source
    for source in [payload(), payload(block("header", text="Only heading")),
                   {"pages": [{"slug": "/inner/", "content": "unsupported"}]}]:
        assert apply_brand_content_buttons(source, SITE) == source


def test_generation_spec_requires_topic_language_action_and_exact_brand():
    instruction = generation_instruction(SITE, {}, "de", "Promo codes")
    assert all(value in instruction for value in ["Button Text:", "topic-specific", "Vox Casino", "Promo codes", '"language": "de"'])
    assert generation_instruction(SimpleNamespace(brand="Общие ключи", site_type="general"), {}, "pl", "Bonus") == ""


@pytest.mark.parametrize("label", ["Vox Casino", "Click here", "Vox Casino https://spam.test", "<b>Vox Casino</b> öffnen", "Vox Casino\nöffnen"])
def test_invalid_cta_copy_is_rejected(label):
    assert not valid_label(label, "Vox Casino")


def test_cta_metadata_does_not_leak_into_article():
    from app.services import extract_ai_article_parts
    parts = extract_ai_article_parts("Title: Titel\nH1: Bonus\nButton Text: " + LABEL + "\nFirst paragraph", "Topic")
    assert parts["button_text"] == LABEL
    assert parts["body"] == "First paragraph"


def test_missing_contextual_label_is_generated_once_and_usage_is_counted(monkeypatch):
    import asyncio
    from app import services
    provider = SimpleNamespace(prompt_tokens_used=0, completion_tokens_used=0, total_tokens_used=0)
    prompts = []
    async def call(provider, prompt):
        prompts.append(prompt)
        return {"candidates": [{"content": {"parts": [{"text": LABEL}]}}], "usageMetadata": {"totalTokenCount": 12}}
    monkeypatch.setattr(services, "call_gemini", call)
    label = asyncio.run(ensure_label(provider, "Vox Casino", brand="Vox Casino", topic="Bonus", language="de", excerpt="Intro"))
    assert label == LABEL and len(prompts) == 1 and provider.total_tokens_used == 12
    assert '"topic": "Bonus"' in prompts[0] and '"language": "de"' in prompts[0]
