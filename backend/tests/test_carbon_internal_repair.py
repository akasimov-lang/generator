from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from app import carbon_internal_repair as repair, models
from test_project_network import env


def project():
    return {'settings': {'canon': 'carboncraftworks.com'}, 'head': {'canonical': 'preserved'},
            'layout': '{{buildHead headCompiled}}<body><main>{{> header}}<div class="contentMain">{{{renderedBlocks}}}</div>{{> footer}}</main></body>',
            'styles': 'body{color:white}', 'shortcodes': [{'name': 'header.hbs', 'data': 'menu unchanged'}],
            'data': {'menu': {'header': [{'slug': '/prehled-bonusu/'}]},
                     'pages': [{'slug': '/', 'title': 'Home'}, {'slug': '/prehled-bonusu/', 'title': 'Bonus', 'content': {'blocks': [{'type': 'button', 'data': {'button': 'Bonus'}}]}}]}}


def test_proposal_targets_all_inner_pages_without_touching_content_or_header():
    source = project(); before = deepcopy(source)
    result = repair.proposed(source)
    assert source == before
    assert result['layout'].replace('<body data-cc-page="{{page.slug}}">', '<body>') == source['layout']
    assert '.btn-content' in result['styles']
    assert ':not([data-cc-page="/"])' in result['styles']
    assert result['styles'].startswith(source['styles'])


def test_native_styles_and_layout_are_confirmed_without_changing_pages_or_seo(env, monkeypatch):
    db, site, _ = env; monkeypatch.setattr(repair, 'SITE', site.id)
    source = project(); original = deepcopy(source); calls = []
    class Remote:
        client = SimpleNamespace(headers={})
        def project(self): return deepcopy(source)
        def request(self, method, endpoint, payload):
            calls.append(endpoint)
            if endpoint == '/projects/update-style': source['styles'] = payload['contents']
            elif endpoint == '/projects/update-layout': source['layout'] = unquote(payload['contents'])
            else: pytest.fail('Unexpected native write')
            return 200, {}
    monkeypatch.setattr(repair, 'Remote', lambda *_: nullcontext(Remote()))
    repair.apply(db); repair.apply(db)
    assert calls == ['/projects/update-style', '/projects/update-layout']
    assert all(source[key] == original[key] for key in ('data', 'settings', 'head', 'shortcodes'))
    ledger = db.get(models.AutoReglueConfig, repair.KEY)
    assert ledger.value['before'] == repair.fields(original)
    assert ledger.value['status'] == 'applied'
    assert all(receipt['status'] == 'confirmed' for receipt in ledger.value['receipts'])


def test_uncertain_native_write_is_not_blindly_retried(env, monkeypatch):
    db, site, _ = env; monkeypatch.setattr(repair, 'SITE', site.id)
    source = project(); calls = []
    class Remote:
        client = SimpleNamespace(headers={})
        def project(self): return deepcopy(source)
        def request(self, *args):
            calls.append(args)
            raise TimeoutError('Response lost')
    monkeypatch.setattr(repair, 'Remote', lambda *_: nullcontext(Remote()))
    with pytest.raises(TimeoutError): repair.apply(db)
    with pytest.raises(ValueError, match='Предыдущая отправка'): repair.apply(db)
    assert len(calls) == 1
