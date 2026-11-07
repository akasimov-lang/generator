import asyncio
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app import models, services
from test_generation_modes import db, make_site


def provider_transport(monkeypatch, handler):
    provider = models.AiProvider(name='Search', provider_type='dataforseo',
        api_key='login:password', validation_status='valid')
    calls, sleeps = [], []
    original = httpx.AsyncClient

    def request(req):
        calls.append(req)
        return handler(len(calls), req)

    async def location(*args):
        return 2616

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(services, 'get_dataforseo_country_location_code', location)
    monkeypatch.setattr(services.asyncio, 'sleep', sleep)
    monkeypatch.setattr(services.httpx, 'AsyncClient', lambda **kw: original(
        **kw, transport=httpx.MockTransport(request)))
    return provider, calls, sleeps


def payload(code=20000, urls=()):
    return {'status_code': 20000, 'tasks': [{'status_code': code,
        'status_message': 'Internal SE Server Error' if code == 40101 else 'Ok',
        'result': [{'items': [{'type': 'organic', 'url': url, 'title': 'Casino payments',
                              'rank_group': n} for n, url in enumerate(urls, 1)]}]}]}


def test_serp_succeeds_on_seventh_attempt_with_six_fifteen_second_pauses(monkeypatch):
    provider, calls, sleeps = provider_transport(monkeypatch, lambda n, req:
        httpx.Response(200, json=payload(40101 if n < 7 else 20000)))
    result = asyncio.run(services.call_dataforseo_google_serp(provider, 'casino', 'PL', 'pl'))
    assert result['tasks'][0]['status_code'] == 20000
    assert len(calls) == 7 and sleeps == [15] * 6
    assert provider.validation_status == 'valid'


def test_serp_outage_stops_after_seven_attempts_without_invalidating_credentials(monkeypatch):
    provider, calls, sleeps = provider_transport(monkeypatch, lambda n, req:
        httpx.Response(503, text='Unavailable'))
    with pytest.raises(services.DataForSEOTransientError, match='503 after 7'):
        asyncio.run(services.call_dataforseo_google_serp(provider, 'casino', 'PL', 'pl'))
    assert len(calls) == 7 and sleeps == [15] * 6
    assert provider.validation_status == 'valid'


def test_serp_transport_timeout_has_the_same_bounded_retry_policy(monkeypatch):
    def unavailable(n, req):
        raise httpx.ReadTimeout('timeout', request=req)
    provider, calls, sleeps = provider_transport(monkeypatch, unavailable)
    with pytest.raises(services.DataForSEOTransientError, match='7 attempts'):
        asyncio.run(services.call_dataforseo_google_serp(provider, 'casino', 'PL', 'pl'))
    assert len(calls) == 7 and sleeps == [15] * 6


def test_bad_credentials_are_not_retried_as_a_provider_outage(monkeypatch):
    provider, calls, sleeps = provider_transport(monkeypatch, lambda n, req: httpx.Response(401))
    with pytest.raises(ValueError, match='rejected credentials'):
        asyncio.run(services.call_dataforseo_google_serp(provider, 'casino', 'PL', 'pl'))
    assert len(calls) == 1 and sleeps == [] and provider.validation_status == 'invalid'


def test_valid_empty_serp_does_not_consume_error_retries(monkeypatch):
    provider, calls, sleeps = provider_transport(monkeypatch, lambda n, req:
        httpx.Response(200, json=payload(40102)))
    assert not services.extract_organic_serp_items(asyncio.run(
        services.call_dataforseo_google_serp(provider, 'casino', 'PL', 'pl')))
    assert len(calls) == 1 and sleeps == []


def research_item(db, monkeypatch):
    site = make_site(db)
    site.brand = 'Общие ключи'
    task = models.GenerationTask(title='Payments', site_id=site.id, geo='PL', language='pl')
    item = models.ContentItem(task=task, site_id=site.id, topic='Casino payments', slug='/payments/',
        generated_json={}, idempotency_key='research-recovery')
    db.add(item)
    db.flush()
    queries = [models.CompetitorQuery(content_item_id=item.id, query=q, position=n)
               for n, q in enumerate(['casino payments', 'casino payment methods'], 1)]
    db.add_all(queries)
    db.commit()
    monkeypatch.setattr(services, 'ensure_competitor_queries', lambda *args: queries)
    monkeypatch.setattr(services, 'get_dataforseo_provider', lambda db: SimpleNamespace())
    return item, queries


def add_saved_page(db, item, query, *, url='https://example.test/casino-payments', title='Casino payments'):
    result = models.CompetitorResult(content_item_id=item.id, query_id=query.id, query_text=query.query,
        url=url, normalized_url=url)
    db.add(result)
    db.flush()
    page = models.CompetitorPage(content_item_id=item.id, competitor_result_id=result.id,
        url=url, title=title, text_content='Useful saved text', http_status=200, word_count=500)
    db.add(page)
    db.commit()
    return result, page


def test_search_outage_retains_existing_pages_and_builds_brief_without_refetch(db, monkeypatch):
    item, queries = research_item(db, monkeypatch)
    result, page = add_saved_page(db, item, queries[0])
    async def unavailable(*args):
        raise services.DataForSEOTransientError('40101')
    monkeypatch.setattr(services, 'call_dataforseo_google_serp', unavailable)
    # Saved source must remain usable even if no external site can be contacted.
    monkeypatch.setattr(httpx.AsyncClient, 'get', lambda *a, **kw: pytest.fail('Saved page was refetched'))
    asyncio.run(services.collect_competitor_research_for_item(db, item))
    assert db.get(models.CompetitorPage, page.id).text_content == 'Useful saved text'
    assert item.competitor_research_status == 'brief_ready'
    assert item.competitor_brief['analyzed_pages_count'] == 1
    assert item.generation_context['competitor_search_recovery']['attempts'] == 7
    assert queries[0].status == 'search_unavailable' and queries[1].status == 'draft'


def test_partial_serp_is_used_when_the_next_query_exhausts_retries(db, monkeypatch):
    item, queries = research_item(db, monkeypatch)
    calls = []
    async def search(provider, keyword, *args):
        calls.append(keyword)
        if len(calls) == 2:
            raise services.DataForSEOTransientError('40101')
        return payload(urls=['https://example.test/casino-payments'])
    monkeypatch.setattr(services, 'call_dataforseo_google_serp', search)
    asyncio.run(services.collect_competitor_serp_for_item(db, item))
    results = db.scalars(select(models.CompetitorResult).where(models.CompetitorResult.content_item_id == item.id)).all()
    assert [r.url for r in results] == ['https://example.test/casino-payments']
    assert item.competitor_research_status == 'serp_collected'
    assert item.generation_context['competitor_search_recovery']['retained_results'] == 1


def test_empty_research_continues_with_scoped_saved_knowledge_and_visible_notice(db, monkeypatch):
    item, queries = research_item(db, monkeypatch)
    async def unavailable(*args):
        raise services.DataForSEOTransientError('40101')
    monkeypatch.setattr(services, 'call_dataforseo_google_serp', unavailable)
    asyncio.run(services.collect_competitor_research_for_item(db, item))
    assert item.competitor_research_status == 'brief_ready'
    assert item.competitor_brief['research_status'] == 'saved_context'
    assert item.competitor_brief['search_recovery']['retry_delay_seconds'] == 15
    assert '7 попыток' in item.competitor_brief_text
    assert item.competitor_research_error is None


def test_unrelated_loyalty_results_are_excluded_from_casino_brief(db, monkeypatch):
    item, queries = research_item(db, monkeypatch)
    add_saved_page(db, item, queries[0], url='https://ikea.example/rewards', title='IKEA Family points')
    add_saved_page(db, item, queries[1], url='https://example.test/casino-loyalty', title='Casino loyalty')
    services.build_competitor_brief_for_item(db, item)
    assert item.competitor_brief['analyzed_pages_count'] == 1
    assert all('ikea' not in source['url'] for source in item.competitor_brief['competitor_summary'])
