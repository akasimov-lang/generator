from app.services import PROMPT_FORMAT_CONTRACT_MARKER, build_gemini_prompt


def test_prompt_placeholders_are_rendered() -> None:
    prompt = build_gemini_prompt(
        topic="Legale Online Casinos",
        geo="DE",
        language="de",
        target_words=1600,
        site=None,
        prompt_template="Topic: {{TOPIC}}, Geo: {{GEO}}, Language: {{LANGUAGE}}, Words: {{TARGET_WORDS}}, Slug: {{SLUG}}",
        shortcode=None,
        include_toc=True,
        include_faq=True,
    )

    assert "Legale Online Casinos" in prompt
    assert "DE" in prompt
    assert "de" in prompt
    assert "1600" in prompt
    assert "/legale-online-casinos/" in prompt
    assert "{{TOPIC}}" not in prompt
    assert "{{GEO}}" not in prompt


def test_prompt_format_contract_is_appended_once() -> None:
    prompt = build_gemini_prompt(
        topic="Legale Online Casinos",
        geo="DE",
        language="de",
        target_words=1600,
        site=None,
        prompt_template="Topic: {{TOPIC}}",
        shortcode=None,
        include_toc=True,
        include_faq=True,
    )

    prompt_with_contract = build_gemini_prompt(
        topic="Legale Online Casinos",
        geo="DE",
        language="de",
        target_words=1600,
        site=None,
        prompt_template=f"Topic: {{{{TOPIC}}}}\n\n{PROMPT_FORMAT_CONTRACT_MARKER}",
        shortcode=None,
        include_toc=True,
        include_faq=True,
    )

    assert prompt.count(PROMPT_FORMAT_CONTRACT_MARKER) == 1
    assert prompt_with_contract.count(PROMPT_FORMAT_CONTRACT_MARKER) == 1
