from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.brand_home_links import apply_brand_home_links, link_brand_paragraph


def content(*texts):
    return {'blocks': [{'type': 'paragraph', 'data': {'text': text}} for text in texts]}


def test_links_one_brand_in_paragraph_preserving_other_markup():
    source = content('Welcome <strong>MerkurXtip</strong> — MerkurXtip.', 'MerkurXtip again.')
    before = deepcopy(source)
    result, changed = link_brand_paragraph(source, 'MerkurXtip')
    assert changed
    assert result['blocks'][0]['data']['text'] == 'Welcome <strong><a href="/">MerkurXtip</a></strong> — MerkurXtip.'
    assert result['blocks'][1] == source['blocks'][1]
    assert source == before
    repeated, changed = link_brand_paragraph(result, 'MerkurXtip')
    assert not changed and repeated == result


def test_preserves_existing_links_and_links_later_unlinked_mention():
    source = content('<a href="/bonus/">MerkurXtip</a>. MerkurXtip.')
    result, _ = link_brand_paragraph(source, 'MerkurXtip')
    assert result['blocks'][0]['data']['text'] == '<a href="/bonus/">MerkurXtip</a>. <a href="/">MerkurXtip</a>.'


def test_existing_home_link_in_later_paragraph_is_not_duplicated():
    source = content('MerkurXtip here.', '<a href="/"><strong>MerkurXtip</strong></a>')
    assert link_brand_paragraph(source, 'MerkurXtip') == (source, False)


def test_ignores_headings_and_brand_substrings():
    source = {'blocks': [{'type': 'header', 'data': {'text': 'MerkurXtip', 'level': 1}}, *content('NotMerkurXtip')['blocks']]}
    with pytest.raises(ValueError, match='абзаце'):
        link_brand_paragraph(source, 'MerkurXtip')


@pytest.mark.parametrize('site', [None, SimpleNamespace(brand='Общие ключи', site_type=None), SimpleNamespace(brand='MerkurXtip', site_type='general')])
def test_general_sites_are_not_changed(site):
    source = {'pages': [{'slug': '/example/', 'content': content('MerkurXtip')} ]}
    assert apply_brand_home_links(source, site) == source


def test_homepage_is_unchanged_and_each_internal_page_is_linked():
    source = {'pages': [{'slug': slug, 'content': content('MerkurXtip')} for slug in ['/', '/one/', '/two/']]}
    result = apply_brand_home_links(source, SimpleNamespace(brand='MerkurXtip', site_type='monobrand'))
    assert result['pages'][0] == source['pages'][0]
    assert all(p['content']['blocks'][0]['data']['text'] == '<a href="/">MerkurXtip</a>' for p in result['pages'][1:])
