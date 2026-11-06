from copy import deepcopy
from types import SimpleNamespace
from contextlib import nullcontext
from urllib.parse import unquote
import pytest
from app import models, pelicancasinop_template_repair as repair
from test_project_network import env


def project():
    return {'settings': {'canon': 'pelicancasinop.pl'}, 'data': {'menu': {'header': [{'slug': '/games/', 'title': 'Gry'}]}},
        'layout': '<body><meta itemprop="image" content="/uploads/img/webp/logo-mostbet.webp">{{{renderedBlocks}}}</body>',
        'styles': 'body {color: navy}', 'shortcodes': [{'name': 'header.hbs', 'data':
        '<header><div class="header-inner"><a class="brand" href="./index.html">Logo</a><nav class="top-nav"><a href="#games">Old anchors</a></nav><div class="actions"><button data-split="login">Login</button></div></div></header>'}, {'name':'footer.hbs', 'data':'<footer><a href="./index.html">Logo</a><img src="assets/pay-blik.svg"></footer>'}]}


def test_repair_preserves_account_tracking_and_content_and_renders_real_menu():
    original = project(); before = deepcopy(original)
    after = repair.proposed(original)
    assert original == before
    assert '<button data-split="login">Login</button>' in after['header']
    assert after['header'].index('brand') < after['header'].index('pp-main-menu') < after['header'].index('class="actions"')
    assert '#each headerMenu' in after['header'] and 'href="{{this.slug}}"' in after['header']
    assert 'Old anchors' not in after['header'] and 'chapter-dock' not in after['header']
    assert '{{{renderedBlocks}}}' in after['layout'] and 'logo-mostbet' not in after['layout']
    assert after['styles'].startswith(original['styles'])
    assert 'src="/assets/pay-blik.svg"' in after['footer']
    assert 'href="/"' in after['footer']


def test_changed_header_is_rejected_instead_of_replacing_unreviewed_template():
    changed = project(); changed['shortcodes'][0]['data'] = '<header>Another template</header>'
    with pytest.raises(ValueError, match='изменён'):
        repair.proposed(changed)


def test_native_apply_confirms_each_file_and_retry_does_not_repeat_writes(env, monkeypatch):
    db, site, _ = env
    monkeypatch.setattr(repair, 'SITE', site.id)
    current = project(); before = deepcopy(current)
    calls = []
    class Remote:
        client = SimpleNamespace(headers={})
        def project(self): return deepcopy(current)
        def request(self, method, endpoint, payload):
            calls.append(endpoint)
            if endpoint == '/projects/update-style': current['styles'] = payload['contents']
            elif endpoint == '/projects/update-layout': current['layout'] = unquote(payload['contents'])
            elif endpoint == '/projects/shortcode': next(s for s in current['shortcodes'] if s['name'] == payload['filename']+'.hbs')['data'] = unquote(payload['contents'])
            else: pytest.fail('Unexpected write')
            return 201, {'ok': True}
    monkeypatch.setattr(repair, 'Remote', lambda *args: nullcontext(Remote()))
    repair.prepare(db); repair.apply(db)
    assert len(calls) == 4 and repair.fields(current) == repair.proposed(before)
    assert current['data'] == before['data'] and current['settings'] == before['settings']
    assert repair.apply(db)['status'] == 'already_applied' and len(calls) == 4
    ledger = db.get(models.AutoReglueConfig, repair.KEY)
    assert ledger.value['before'] == repair.fields(before)
    assert all(r['status'] == 'confirmed' for r in ledger.value['receipts'])


def test_intro_cleanup_preserves_paragraphs_and_removes_only_its_contents_entry():
    page = {'slug': '/games/', 'content': {'blocks': [
        {'type': 'header', 'data': {'level': 1, 'text': 'Gry'}},
        {'type': 'list', 'pagepilot_toc': True, 'data': {'items': [
            '<a href="#intro">Wstęp do kolekcji gier</a>', '<a href="#rules">Warunki wstępne</a>']}},
        {'type': 'header', 'data': {'level': 2, 'text': '<span id="intro"></span>Wstęp do kolekcji gier'}},
        {'type': 'paragraph', 'data': {'text': 'Oryginalne wprowadzenie z <a href="/">Pelican</a>.'}},
        {'type': 'header', 'data': {'level': 2, 'text': '<span id="rules"></span>Warunki wstępne'}},
        {'type': 'list', 'data': {'items': ['Wstęp do gry', 'Zasady']}},
        {'type': 'faq', 'data': [{'question': 'Jak grać?', 'answer': 'Przeczytaj zasady.'}]}
    ]}}
    before = deepcopy(page)
    content, changes = repair.clean_page(page)
    assert page == before
    assert changes == {'intro_removed': 1, 'translated_headings': 0}
    assert content['blocks'][2:] == before['content']['blocks'][3:]
    assert content['blocks'][1]['data']['items'] == ['<a href="#rules">Warunki wstępne</a>']
    assert repair.clean_page({**page, 'content': content})[0] == content


def test_polish_heading_and_contents_translation_leaves_body_unchanged():
    page = {'slug': '/games/', 'content': {'blocks': [
        {'type': 'list', 'pagepilot_toc': True, 'data': {'items': ['<a href="#method">Methodik: ocena gier</a>']}},
        {'type': 'header', 'data': {'level': 2, 'text': '<span id="method"></span>Methodik: ocena gier'}},
        {'type': 'paragraph', 'data': {'text': 'Methodik jako cytat.'}}
    ]}}
    content, changes = repair.clean_page(page)
    assert changes == {'intro_removed': 0, 'translated_headings': 1}
    assert 'Metodyka:' in content['blocks'][0]['data']['items'][0]
    assert 'Metodyka:' in content['blocks'][1]['data']['text']
    assert content['blocks'][2] == page['content']['blocks'][2]
    assert repair.clean_page({**page, 'slug': '/'})[0] == page['content']
