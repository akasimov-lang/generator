import asyncio

import pytest

from app import models, services


def test_czech_faq_keeps_real_answers_split_across_paragraphs():
    source = [services.header_block('Často kladené dotazy', 2),
              services.paragraph_block('Q: Je aplikace zdarma? A: Ano. Q: Jak se přihlásím?'),
              services.paragraph_block('A: Použijte svůj účet.'),
              services.header_block('Závěr', 2), services.paragraph_block('Původní závěr.')]
    result = services.normalize_editor_faq_blocks(source)
    assert result[1]['data'] == [
        {'question': 'Je aplikace zdarma?', 'answer': 'Ano.'},
        {'question': 'Jak se přihlásím?', 'answer': 'Použijte svůj účet.'},
    ]
    assert result[2:] == source[-2:]
    assert len(source) == 5


def test_czech_faq_label_with_parenthetical_abbreviation_is_recognized():
    result = services.build_blocks_from_ai_text('H2: Často kladené dotazy (FAQ)\nQ: Jak začít?\nA: Přečtěte si pravidla.', 'Průvodce', None, False, True)
    assert [b['data'] for b in result if b['type'] == 'faq'] == [[{'question': 'Jak začít?', 'answer': 'Přečtěte si pravidla.'}]]


def test_markdown_question_subheadings_are_normalized_without_eating_next_section():
    result = services.build_blocks_from_ai_text('## FAQ\n### Jak začít?\nPřečtěte si pravidla.\n### Jak pokračovat?\nOvěřte podmínky.\n## Shrnutí\nPůvodní závěr.', 'Průvodce', None, False, True)
    faq = next(b for b in result if b['type'] == 'faq')
    assert faq['data'] == [{'question': 'Jak začít?', 'answer': 'Přečtěte si pravidla.'}, {'question': 'Jak pokračovat?', 'answer': 'Ověřte podmínky.'}]
    assert result[-2]['data'] == {'text': 'Shrnutí', 'level': 2}
    assert result[-1]['data']['text'] == 'Původní závěr.'


def test_parser_does_not_invent_an_english_faq_when_answers_are_missing():
    result = services.build_blocks_from_ai_text('H2: Pravidla\nPřečtěte si podmínky.', 'Průvodce', None, False, True)
    assert not any(b['type'] == 'faq' for b in result)
    assert 'This page explains' not in str(result)


def test_required_missing_faq_stops_ai_generation_before_publication(monkeypatch):
    async def reply(*args, **kwargs):
        return {'candidates': [{'content': {'parts': [{'text': 'Title: Praktický průvodce platbami online\nH1: Platební průvodce\nMeta Description: Přehled pravidel a postupů.\nH2: Pravidla\nPřečtěte si podmínky.'}]}}]}
    monkeypatch.setattr(services, 'call_gemini', reply)
    monkeypatch.setattr(services, 'seo_title_needs_improvement', lambda title: False)
    provider = models.AiProvider(name='test', provider_type='gemini', api_key='test', model='test')
    with pytest.raises(ValueError, match='FAQ'):
        asyncio.run(services.build_gemini_content(provider, 'Platební průvodce', 'CZ', 'cs', 300, None, 'simple_page', None, None, False, True))
