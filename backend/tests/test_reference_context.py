import copy
import json

import pytest

from app import reference_context as reference


def corpus(count=528):
    return {'version': 1, 'brand': 'Общие ключи', 'geo': 'CZ',
            'excluded_research_sources': 0, 'editorial_guidelines': ['Style and factual constraints'],
            'sources': [{'sha256': f'{i:064x}', 'text': f'Unique source {i}. ' + 'casino facts ' * 2000,
                         'details': {'topic': f'Topic {i}'},
                         'provenance': [{'kind': 'competitor_page', 'id': f'{i}-{j}',
                                         'url': f'https://example.org/source/{i}/{j}?token=' + 'x' * 800,
                                         'title': f'České casino {i}'} for j in range(3)]}
                        for i in range(count)]}


def test_large_proxy_provenance_keeps_every_source_within_prompt_limit():
    context = corpus()
    result = reference.prompt_context(context)
    assert len(json.dumps(result, ensure_ascii=False)) <= reference.MAX_PROMPT_CHARS
    assert result['reference_sampling']['compact_provenance'] is True
    assert [s['sha256'] for s in result['sources']] == [s['sha256'] for s in context['sources']]
    assert all(s['excerpts'] and s['provenance_count'] == 3 for s in result['sources'])
    assert result['editorial_guidelines'] == context['editorial_guidelines']


def test_prompt_compaction_preserves_full_corpus_and_audit_urls():
    context = corpus()
    original = copy.deepcopy(context)
    reference.prompt_context(context)
    assert context == original
    audit = reference.audit(context)
    assert audit['source_count'] == 528
    assert audit['sources'][200]['provenance'] == original['sources'][200]['provenance']


def test_small_context_is_not_sampled_or_compacted():
    context = corpus(1)
    assert reference.prompt_context(context) is context


def test_genuinely_excessive_source_count_still_fails_without_silent_exclusion(monkeypatch):
    context = corpus(8)
    monkeypatch.setattr(reference, 'MAX_PROMPT_CHARS', 1500)
    with pytest.raises(ValueError, match='тематическая выборка'):
        reference.prompt_context(context)
    assert len(context['sources']) == 8


def test_repeated_addresses_select_latest_fetched_snapshot_for_prompt_and_report():
    context = corpus(3)
    for i, source in enumerate(context['sources']):
        source['provenance'] = [{'kind': 'competitor_page', 'id': str(i),
                                 'url': 'https://example.org/casino?utm_source=' + str(i), 'title': 'Casino'}]
        source['details']['fetched_at'] = f'2026-11-{i+1:02}T00:00:00Z'
    original = copy.deepcopy(context)
    selected = reference.prompt_context(context)
    assert len(selected['sources']) == 1
    assert selected['sources'][0]['sha256'] == context['sources'][2]['sha256']
    assert selected['sources'][0]['provenance'][0]['url'] == 'https://example.org/casino'
    assert reference.audit(context)['source_count'] == 1
    assert selected['source_deduplication']['duplicate_observations_removed'] == 2
    assert context == original


def test_fetched_page_wins_over_newer_search_snippet():
    context = corpus(2)
    for source in context['sources']:
        source['provenance'] = [{'kind': 'competitor_page', 'url': 'https://example.org/'}]
    context['sources'][1]['provenance'][0]['kind'] = 'competitor_result'
    context['sources'][1]['details']['fetched_at'] = '2099-01-01'
    assert reference.unique_sources(context)['sources'][0]['sha256'] == context['sources'][0]['sha256']


def test_url_normalization_unwraps_known_search_links_and_preserves_distinct_pages():
    assert reference.source_url('https://www.google.com/url?q=https%3A%2F%2FEXAMPLE.org%3A443%2Fa%3Futm_source%3Dsearch%26lang%3Dcs%23faq') == 'https://example.org/a?lang=cs'
    assert reference.source_url('https://example.org/a?lang=cs') != reference.source_url('https://example.org/a?lang=pl')
    assert reference.source_url('https://example.org/A') != reference.source_url('https://example.org/a')


def test_shared_text_retains_distinct_source_addresses_and_unaddressed_facts():
    context = corpus(2)
    context['sources'][0]['provenance'] = [{'url': 'https://example.org/a'}, {'url': 'https://example.org/a#faq'}, {'url': 'https://example.org/b'}]
    context['sources'][1]['provenance'] = [{'kind': 'template_facts', 'id': 'facts', 'url': ''}]
    result = reference.unique_sources(context)
    assert [p['url'] for p in result['sources'][0]['provenance']] == ['https://example.org/a', 'https://example.org/b']
    assert result['sources'][1] == context['sources'][1]
