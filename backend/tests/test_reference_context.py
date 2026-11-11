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
                                         'url': 'https://google.com/goto?url=' + 'x' * 800,
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
