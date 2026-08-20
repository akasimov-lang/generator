import asyncio

from app import models, services as service_module
from app.services import (
    CASINO_RATING_PROMPT_MARKER,
    PROMPT_FORMAT_CONTRACT_MARKER,
    TEXT_VARIABILITY_PROTOCOL_MARKER,
    append_casino_rating_requirement,
    build_gemini_content,
    build_gemini_prompt,
    call_gemini,
    variation_profile_for_position,
)


def test_gemini_request_retries_transient_http_errors(monkeypatch) -> None:
    calls: list[str] = []
    sleeps: list[int] = []

    class FakeResponse:
        def __init__(self, status_code: int):
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self) -> dict:
            return {"status": "ok"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, endpoint: str, json: dict, headers: dict) -> FakeResponse:
            calls.append(endpoint)
            return FakeResponse(503 if len(calls) < 3 else 200)

    async def fake_sleep(delay: int) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(service_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)
    provider = models.AiProvider(name="Gemini", provider_type="gemini", api_key="test-key")

    response = asyncio.run(call_gemini(provider, "Generate"))

    assert response == {"status": "ok"}
    assert len(calls) == 3
    assert sleeps == [2, 4]


def test_casino_rating_requirement_is_optional_and_idempotent() -> None:
    base_prompt = "Generate an article about {{TOPIC}}"

    disabled = append_casino_rating_requirement(base_prompt, enabled=False)
    enabled = append_casino_rating_requirement(base_prompt, enabled=True)
    repeated = append_casino_rating_requirement(enabled, enabled=True)

    assert disabled == base_prompt
    assert enabled.count(CASINO_RATING_PROMPT_MARKER) == 1
    assert "от 5 до 10" in enabled
    assert repeated == enabled


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


def test_task_variability_protocol_is_rendered_once() -> None:
    profiles = [variation_profile_for_position(index) for index in range(3)]
    context = {
        "task_id": "task-1",
        "task_title": "Three related topics",
        "topics_count": 3,
        "current_topic": "Topic B",
        "current_profile": profiles[1],
        "assignments": [
            {"topic": f"Topic {letter}", "profile": profile, "is_current": index == 1}
            for index, (letter, profile) in enumerate(zip("ABC", profiles))
        ],
    }

    prompt = build_gemini_prompt(
        topic="Topic B",
        geo="DE",
        language="de",
        target_words=1600,
        site=None,
        prompt_template="Topic: {{TOPIC}}",
        shortcode=None,
        include_toc=True,
        include_faq=True,
        variation_context=context,
    )

    assert prompt.count(TEXT_VARIABILITY_PROTOCOL_MARKER) == 1
    assert "Current variability passport: V02" in prompt
    assert "do not reuse a sibling outline" in prompt
    assert "Topic A" in prompt
    assert "Topic C" in prompt


def test_first_thirty_topics_receive_distinct_structural_blueprints() -> None:
    profiles = [variation_profile_for_position(index) for index in range(30)]

    assert len({profile["id"] for profile in profiles}) == 30
    assert len({profile["structure"] for profile in profiles}) == 30


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
