import asyncio

from app import models
from app.services import PROMPT_FORMAT_CONTRACT_MARKER, build_gemini_content, build_gemini_prompt


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


def test_competitor_research_placeholders_are_rendered() -> None:
    prompt = build_gemini_prompt(
        topic="Beste Online Casinos",
        geo="DE",
        language="de",
        target_words=1600,
        site=None,
        prompt_template=(
            "Queries:\n{{SEARCH_QUERIES}}\n"
            "URLs:\n{{COMPETITOR_URLS}}\n"
            "Gaps:\n{{CONTENT_GAPS}}\n"
            "Headings:\n{{COMMON_HEADINGS}}\n"
            "Missing:\n{{MISSING_BLOCKS_TO_COVER}}"
        ),
        shortcode=None,
        include_toc=True,
        include_faq=True,
        competitor_brief={
            "generated_at": "2026-08-04T00:00:00+00:00",
            "search_queries": ["beste online casinos deutschland"],
            "competitor_urls": ["https://example.com/casinos"],
            "competitor_summary": [{"url": "https://example.com/casinos", "title": "Example", "headings": ["GGL Lizenz"]}],
            "content_gaps": ["Раскрыть сильнее: KYC."],
            "common_headings": ["GGL Lizenz"],
            "topics_to_cover": ["KYC und Identitätsprüfung"],
        },
    )

    assert "beste online casinos deutschland" in prompt
    assert "https://example.com/casinos" in prompt
    assert "KYC und Identitätsprüfung" in prompt
    assert "{{SEARCH_QUERIES}}" not in prompt


def test_gemini_content_generation_passes_competitor_brief_to_prompt(monkeypatch) -> None:
    captured = {}

    async def fake_call_gemini(provider, prompt):
        captured["prompt"] = prompt
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    "Title: A different and overly long title invented by the model\n"
                                    "Meta Description: Test description.\n"
                                    "H1: A different and overly long H1 invented by the model\n"
                                    "Intro:\n"
                                    "Test content about safe providers."
                                )
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
        }

    monkeypatch.setattr("app.services.call_gemini", fake_call_gemini)
    provider = models.AiProvider(
        name="Gemini",
        provider_type="gemini",
        endpoint_url="https://example.com/{model}",
        model="gemini-test",
        api_key="key",
    )

    generated = asyncio.run(
        build_gemini_content(
            provider=provider,
            topic="Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich",
            geo="DE",
            language="de",
            target_words=1600,
            site=None,
            payload_mode="simple_page",
            prompt_template="Research:\n{{COMPETITOR_SUMMARY}}\n{{CONTENT_GAPS}}",
            shortcode=None,
            include_toc=True,
            include_faq=True,
            competitor_brief={
                "competitor_summary": [{"url": "https://example.com", "title": "Example Casino Page"}],
                "content_gaps": ["Mehr Details zu KYC und Limits"],
            },
        )
    )

    assert "Example Casino Page" in captured["prompt"]
    assert "Mehr Details zu KYC und Limits" in captured["prompt"]
    assert generated["pages"][0]["title"] == "Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich"
    assert generated["pages"][0]["content"]["blocks"][0]["data"]["text"] == "Beste Online Casinos in Deutschland 2026"
