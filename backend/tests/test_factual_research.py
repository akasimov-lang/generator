import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app import factual_research as research, models, services


def request(query="operator withdrawal processing time"):
    return {"question": "What is the processing time?", "query": query,
            "reason": "Compare withdrawal conditions", "source_type": "official terms", "period": "current"}


def response(requests):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"requests": requests})}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}}


def serp(*urls):
    return {"tasks": [{"result": [{"items": [
        {"type": "organic", "url": url, "title": "Terms", "description": "Search snippet"}
        for url in urls
    ]}]}]}


def provider():
    return models.AiProvider(name="Test", provider_type="gemini", api_key="test")


def context():
    return {"topic": "Withdrawals", "geo": "DE", "language": "de", "brief": "Compare terms"}


def test_plan_is_validated_deduplicated_and_limited():
    requests = [request("Query 1"), request("query 1"), *[request(f"Query {i}") for i in range(2, 8)]]
    parsed = research.parse_plan("```json\n" + json.dumps({"requests": requests}) + "\n```")
    assert [entry["query"] for entry in parsed] == ["Query 1", "Query 2", "Query 3"]
    for raw in ['[]', '{}', '{"requests":[{"query":"test"}]}', 'not json']:
        with pytest.raises(ValueError):
            research.parse_plan(raw)


@pytest.mark.parametrize("snake_case", [True, False])
def test_url_context_analysis_requires_successful_retrieval_metadata(monkeypatch, snake_case):
    urls = ["https://example.com/read", "https://example.com/blocked"]

    async def analyze(_provider, prompt, *, url_context=False):
        assert url_context is True
        assert all(url in prompt for url in urls)
        entries = [{"retrieved_url" if snake_case else "retrievedUrl": url,
                    "url_retrieval_status" if snake_case else "urlRetrievalStatus": status}
                   for url, status in zip(urls, ["URL_RETRIEVAL_STATUS_SUCCESS", "URL_RETRIEVAL_STATUS_ERROR"])]
        return {"candidates": [{
            "content": {"parts": [{"text": json.dumps({"pages": [
                {"url": url, "analysis": f"Analysis for {url}"} for url in urls
            ]})}]},
            "url_context_metadata" if snake_case else "urlContextMetadata": {
                "url_metadata" if snake_case else "urlMetadata": entries
            },
        }]}

    monkeypatch.setattr(services, "call_gemini", analyze)
    report = asyncio.run(research.analyze_competitor_urls(provider(), {
        **context(), "competitor_research": {"competitor_urls": [*urls, urls[0], "file:///private/data"]},
    }))
    assert len(report["pages"]) == 2
    assert report["pages"][0]["analysis"] == f"Analysis for {urls[0]}"
    assert "analysis" not in report["pages"][1]
    assert report["status"] == "partial"


@pytest.mark.parametrize("unsupported", [True, False])
def test_url_context_failure_does_not_claim_pages_were_read(monkeypatch, unsupported):
    async def analyze(*args, **kwargs):
        if unsupported:
            raise ValueError("Unsupported tool")
        return {"candidates": [{"content": {"parts": [{"text": json.dumps({"pages": [
            {"url": "https://example.com/a", "analysis": "Unconfirmed analysis"}
        ]})}]}}]}

    monkeypatch.setattr(services, "call_gemini", analyze)
    report = asyncio.run(research.analyze_competitor_urls(provider(), {
        **context(), "competitor_research": {"competitor_urls": ["https://example.com/a"]},
    }))
    assert "analysis" not in report["pages"][0]
    assert report["status"] == ("failed" if unsupported else "partial")


def test_url_analysis_reaches_planner_and_article_context(monkeypatch):
    async def analyze(*args):
        return {"status": "complete", "pages": [{"url": "https://example.com", "status": "read", "analysis": "Unique competitor finding"}]}

    async def plan(_provider, prompt):
        assert "Unique competitor finding" in prompt
        return response([])

    monkeypatch.setattr(research, "analyze_competitor_urls", analyze)
    monkeypatch.setattr(services, "call_gemini", plan)
    report = asyncio.run(research.research_facts(provider(), object(), context=context()))
    prompt = services.build_gemini_prompt(
        topic="Topic", geo="DE", language="de", target_words=1000, site=None,
        prompt_template="Write article", shortcode=None, include_toc=False, include_faq=False,
        competitor_brief={"competitor_urls": ["https://example.com"]},
        generation_context={"factual_research": report},
    )
    assert "https://example.com" in prompt
    assert "Unique competitor finding" in prompt


def test_second_round_uses_actual_source_text_and_preserves_query_provenance(monkeypatch):
    plans, searches, fetches, saved = [], [], [], []
    ai = provider()

    async def plan(_provider, prompt):
        plans.append(prompt)
        return response([request("first query" if len(plans) == 1 else "followup query")])

    async def search(_provider, query, geo, language):
        searches.append((query, geo, language))
        return serp("https://operator.example/terms")

    async def fetch(url):
        fetches.append(url)
        return {"url": url, "status": "fetched", "excerpt": "Processing takes three working days."}

    monkeypatch.setattr(services, "call_gemini", plan)
    monkeypatch.setattr(services, "call_dataforseo_google_serp", search)
    monkeypatch.setattr(research, "fetch_source", fetch)
    report = asyncio.run(research.research_facts(ai, object(), context=context(),
                                               checkpoint=lambda value: saved.append(json.loads(json.dumps(value)))))
    assert searches == [("first query", "DE", "de"), ("followup query", "DE", "de")]
    assert len(fetches) == 1
    assert "Processing takes three working days." in plans[1]
    assert report["queries"][0]["results"][0]["source_id"] == "S1"
    assert report["queries"][1]["results"][0]["source_id"] == "S1"
    assert report["status"] == "budget_reached"
    assert saved[0]["queries"] == []
    assert saved[-1]["finished_at"]
    assert ai.total_tokens_used == 30
    rendered = research.render_research(report)
    assert "Processing takes three working days." in rendered
    assert "Do not treat a SERP snippet as verified evidence" in rendered


def test_budget_limits_searches_and_pages(monkeypatch):
    calls, fetched = [], []
    round_count = 0

    async def plan(*args):
        nonlocal round_count
        round_count += 1
        return response([request(f"round {round_count} query {i}") for i in range(10)])

    async def search(_provider, query, *_args):
        calls.append(query)
        return serp(*[f"https://example.com/{len(calls)}/{i}" for i in range(10)])

    async def fetch(url):
        fetched.append(url)
        return {"url": url, "status": "fetched", "excerpt": "Source text"}

    monkeypatch.setattr(services, "call_gemini", plan)
    monkeypatch.setattr(services, "call_dataforseo_google_serp", search)
    monkeypatch.setattr(research, "fetch_source", fetch)
    asyncio.run(research.research_facts(provider(), object(), context=context()))
    assert round_count == 2
    assert len(calls) == 5
    assert len(fetched) == 10
    assert research.COMPETITOR_QUERY_LIMIT + len(calls) == research.ARTICLE_QUERY_LIMIT == 10


def test_duplicate_queries_are_not_searched_again(monkeypatch):
    calls = []

    async def plan(*args):
        return response([request()])

    async def search(*args):
        calls.append(args)
        return serp()

    monkeypatch.setattr(services, "call_gemini", plan)
    monkeypatch.setattr(services, "call_dataforseo_google_serp", search)
    report = asyncio.run(research.research_facts(provider(), object(), context=context()))
    assert len(calls) == 1
    assert report["status"] == "partial"
    assert report["sources"] == []


@pytest.mark.parametrize("failure", ["planner", "search", "source"])
def test_failures_are_recorded_without_inventing_evidence(monkeypatch, failure):
    async def plan(*args):
        return {"candidates": []} if failure == "planner" else response([request()])

    async def search(*args):
        if failure == "search":
            raise ValueError("Provider failed")
        return serp("https://example.com/terms")

    async def fetch(*args):
        raise httpx.ReadTimeout("Source timed out")

    monkeypatch.setattr(services, "call_gemini", plan)
    monkeypatch.setattr(services, "call_dataforseo_google_serp", search)
    monkeypatch.setattr(research, "fetch_source", fetch)
    report = asyncio.run(research.research_facts(provider(), object(), context=context()))
    assert report["status"] in {"failed", "partial"}
    assert all("excerpt" not in source for source in report["sources"])


def test_no_gaps_skips_paid_search(monkeypatch):
    async def plan(*args):
        return response([])

    async def search(*args):
        pytest.fail("No research was requested")

    monkeypatch.setattr(services, "call_gemini", plan)
    monkeypatch.setattr(services, "call_dataforseo_google_serp", search)
    report = asyncio.run(research.research_facts(provider(), object(), context=context()))
    assert report["status"] == "not_needed"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/a", "http://[::1]/", "https://user:pass@example.com/", "http://example.com:8080/"])
def test_source_fetch_rejects_private_and_invalid_urls(url):
    with pytest.raises(ValueError):
        asyncio.run(research.require_public_url(url))


def test_source_fetch_checks_redirect_destination(monkeypatch):
    checked = []

    async def validate(url):
        checked.append(url)
        if "127.0.0.1" in url:
            raise ValueError("Non-public source address")

    def handle(request):
        assert request.url.host == "example.com"
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(research, "require_public_url", validate)
    monkeypatch.setattr(research.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(ValueError, match="Non-public"):
        asyncio.run(research.fetch_source("https://example.com/terms"))
    assert checked == ["https://example.com/terms", "http://127.0.0.1/private"]


@pytest.mark.parametrize("content_type", ["text/html; charset=utf-8", "text/plain; charset=utf-8", "application/pdf"])
def test_source_fetch_reads_text_and_rejects_unsupported_content(monkeypatch, content_type):
    async def validate(url):
        pass

    def handle(request):
        assert "x-goog-api-key" not in request.headers
        assert "authorization" not in request.headers
        return httpx.Response(200, headers={"content-type": content_type}, text=(
            "<html><title>Payment terms</title><script>SECRET_SCRIPT</script>"
            "<p>Withdrawals require identity verification. Processing takes three working days "
            "after all required documents have been reviewed.</p></html>"
        ))

    client_class = httpx.AsyncClient
    monkeypatch.setattr(research, "require_public_url", validate)
    monkeypatch.setattr(research.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs))
    if content_type == "application/pdf":
        with pytest.raises(ValueError, match="Unsupported"):
            asyncio.run(research.fetch_source("https://example.com/terms"))
    else:
        source = asyncio.run(research.fetch_source("https://example.com/terms"))
        assert "three working days" in source["excerpt"]
        assert source["status"] == "fetched"
        assert source["retrieved_at"]
        if "text/html" in content_type:
            assert "SECRET_SCRIPT" not in source["excerpt"]


def test_language_retry_reuses_research_and_renders_evidence(monkeypatch):
    task = SimpleNamespace(collect_competitors=True)
    item = SimpleNamespace(task_id="task", generation_context={})
    db = SimpleNamespace(get=lambda *args: task, commit=lambda: None)
    research_calls, prompts = [], []

    async def facts(*args, **kwargs):
        research_calls.append(kwargs)
        report = {"status": "complete", "sources": [{"url": "https://example.com/terms", "excerpt": "Evidence"}]}
        kwargs["checkpoint"](report)
        return report

    async def build(**kwargs):
        prompts.append(services.build_gemini_prompt(**{key: value for key, value in kwargs.items() if key != "provider"}))
        return {}

    monkeypatch.setattr(services, "get_dataforseo_provider", lambda db: object())
    monkeypatch.setattr(services, "research_facts", facts)
    monkeypatch.setattr(services, "build_ai_content", build)
    monkeypatch.setattr(services, "detected_content_language", lambda result: "de")
    monkeypatch.setattr(services, "generated_content_uses_language", lambda *args: len(prompts) > 1)
    asyncio.run(services._build_task_content(
        db, item, provider=provider(), topic="Withdrawals", geo="DE", language="de",
        site=None, target_words=1000, prompt_template="Write article", shortcode=None,
        include_toc=False, include_faq=False,
    ))
    assert len(research_calls) == 1
    assert len(prompts) == 2
    assert all(research.RESEARCH_MARKER in prompt and "Evidence" in prompt for prompt in prompts)
    assert "MANDATORY LANGUAGE CORRECTION" in prompts[1]
    assert item.generation_context["factual_research"]["status"] == "complete"


@pytest.mark.parametrize("technical, enabled", [(False, False), (True, True)])
def test_research_opt_out_and_technical_pages_skip_planner(monkeypatch, technical, enabled):
    item = SimpleNamespace(task_id="task", generation_context={"content_kind": "technical_page"} if technical else {})
    item.generation_context["factual_research"] = {"status": "complete", "sources": ["stale"]}
    db = SimpleNamespace(get=lambda *args: SimpleNamespace(collect_competitors=enabled))

    async def build(*args, **kwargs):
        assert "factual_research" not in kwargs["generation_context"]
        return {}

    monkeypatch.setattr(services, "get_dataforseo_provider", lambda db: pytest.fail("Research should be skipped"))
    monkeypatch.setattr(services, "build_ai_content", build)
    monkeypatch.setattr(services, "generate_checked", build)
    monkeypatch.setattr(services, "detected_content_language", lambda result: "de")
    monkeypatch.setattr(services, "generated_content_uses_language", lambda *args: True)
    asyncio.run(services._build_task_content(db, item, provider=provider(), language="de"))
    assert "factual_research" not in item.generation_context
