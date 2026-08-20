import asyncio
import json

from app import models
from app.services import (
    HIDDEN_TOPIC_GENERATION_PROMPT_MARKER,
    build_hidden_topic_generation_prompt,
    filter_unique_topic_candidates,
    generate_topic_suggestions,
    topics_are_probable_duplicates,
)


def test_duplicate_check_ignores_year_plural_and_minor_rewording() -> None:
    assert topics_are_probable_duplicates(
        "Best Online Casinos in Australia 2026",
        "Best Online Casino in Australia",
    )
    assert not topics_are_probable_duplicates(
        "Online Casino Laws in Australia",
        "Casino Withdrawal Delays for Australian Players",
    )


def test_filter_unique_candidates_rejects_existing_and_batch_duplicates() -> None:
    accepted, rejected = filter_unique_topic_candidates(
        [
            "Best Online Casino in Australia",
            "Casino Withdrawal Times for Australian Players",
            "Australian Casino Withdrawal Times for Players",
            "Mobile Casino Browser Security in Australia",
        ],
        ["Best Online Casinos in Australia 2026"],
    )

    assert accepted == [
        "Casino Withdrawal Times for Australian Players",
        "Mobile Casino Browser Security in Australia",
    ]
    assert len(rejected) == 2


def test_hidden_prompt_contains_project_context_and_existing_topics() -> None:
    site = models.Site(
        name="best-casino-australia.com",
        base_url="https://best-casino-australia.com",
        publication_endpoint="https://example.com/content",
        payload_mode="simple_page",
    )

    prompt = build_hidden_topic_generation_prompt(
        site=site,
        geo="AU",
        language="en",
        existing_topics=["Existing topic"],
        count=10,
        section_context="Guides · /guides/",
    )

    assert HIDDEN_TOPIC_GENERATION_PROMPT_MARKER in prompt
    assert "best-casino-australia.com" in prompt
    assert "Existing topic" in prompt
    assert "exactly 10" in prompt
    assert "MANDATORY SELECTED MENU SECTION SCOPE" in prompt
    assert "natural child page of this exact menu section" in prompt
    assert "Guides · /guides/" in prompt


def test_hidden_prompt_without_section_keeps_project_wide_scope() -> None:
    site = models.Site(
        name="best-casino-australia.com",
        base_url="https://best-casino-australia.com",
        publication_endpoint="https://example.com/content",
        payload_mode="simple_page",
    )

    prompt = build_hidden_topic_generation_prompt(
        site=site,
        geo="AU",
        language="en",
        existing_topics=[],
        count=10,
        section_context="",
    )

    assert "No menu section is selected" in prompt
    assert "MANDATORY SELECTED MENU SECTION SCOPE" not in prompt


def test_gemini_retries_until_ten_unique_topics(monkeypatch) -> None:
    responses = [
        [
            "Best Online Casinos in Australia",
            "Casino Withdrawal Times for Australian Players",
        ],
        [
            "Online Casino Laws in Australia",
            "How to Check an Offshore Casino Licence",
            "AUD Casino Deposit Methods Explained",
            "Casino Bonus Wagering Requirements Explained",
            "Currency Conversion Fees in Online Casinos",
            "Mobile Casino App Security Checks",
            "How Live Dealer Casino Streams Work",
            "Responsible Gambling Limits in Australia",
            "Casino Account Verification Steps",
        ],
    ]
    prompts: list[str] = []

    async def fake_call_gemini(provider, prompt):
        del provider
        prompts.append(prompt)
        topics = responses[len(prompts) - 1]
        payload = {
            "topics": [
                {"title": title, "primary_intent": title, "uniqueness_reason": "Distinct intent"}
                for title in topics
            ]
        }
        return {
            "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
        }

    monkeypatch.setattr("app.services.call_gemini", fake_call_gemini)
    provider = models.AiProvider(
        name="Gemini",
        provider_type="gemini",
        endpoint_url="https://example.com/{model}",
        model="gemini-test",
        api_key="key",
        is_active=True,
    )
    site = models.Site(
        name="best-casino-australia.com",
        base_url="https://best-casino-australia.com",
        publication_endpoint="https://example.com/content",
        payload_mode="simple_page",
    )

    topics = asyncio.run(
        generate_topic_suggestions(
            provider=provider,
            site=site,
            geo="AU",
            language="en",
            existing_topics=["Best Online Casinos in Australia 2026"],
        )
    )

    assert len(topics) == 10
    assert "Best Online Casinos in Australia" not in topics
    assert len(prompts) == 2
    assert "exactly 9" in prompts[1]
    assert provider.total_tokens_used == 4
