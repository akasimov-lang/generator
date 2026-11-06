from copy import deepcopy
from types import SimpleNamespace
from contextlib import nullcontext
from urllib.parse import unquote
import pytest
from app import models, allday_template_repair as repair
from test_project_network import env


def project():
    return {'settings': {'canon': 'alldaybabyla.com'}, 'data': {'menu': {'header': [{'slug': '/games/', 'title': 'Gry'}]}},
        'layout': '<body><meta itemprop="image" content="/uploads/img/webp/logo-mostbet.webp">{{{renderedBlocks}}}</body>',
        'styles': 'body {color: navy}', 'shortcodes': [{'name': 'header.hbs', 'data':
        '<header><div class="masthead"><a class="brand-home" href="./index.html">Logo</a><div class="account-actions"><button data-split="login">Login</button></div></div><details class="mobile-menu">Old anchors</details><nav class="chapter-dock">Old links</nav></header>'}]}


def test_repair_preserves_account_tracking_and_content_and_renders_real_menu():
    original = project(); before = deepcopy(original)
    after = repair.proposed(original)
    assert original == before
    assert '<button data-split="login">Login</button>' in after['header']
    assert after['header'].index('brand-home') < after['header'].index('pp-main-menu') < after['header'].index('account-actions')
    assert '#each headerMenu' in after['header'] and 'href="{{this.slug}}"' in after['header']
    assert 'Old anchors' not in after['header'] and 'chapter-dock' not in after['header']
    assert '{{{renderedBlocks}}}' in after['layout'] and 'logo-mostbet' not in after['layout']
    assert after['styles'].startswith(original['styles'])


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
            elif endpoint == '/projects/shortcode': current['shortcodes'][0]['data'] = unquote(payload['contents'])
            else: pytest.fail('Unexpected write')
            return 201, {'ok': True}
    monkeypatch.setattr(repair, 'Remote', lambda *args: nullcontext(Remote()))
    repair.prepare(db); repair.apply(db)
    assert len(calls) == 3 and repair.fields(current) == repair.proposed(before)
    assert current['data'] == before['data'] and current['settings'] == before['settings']
    assert repair.apply(db)['status'] == 'already_applied' and len(calls) == 3
    ledger = db.get(models.AutoReglueConfig, repair.KEY)
    assert ledger.value['before'] == repair.fields(before)
    assert all(r['status'] == 'confirmed' for r in ledger.value['receipts'])
