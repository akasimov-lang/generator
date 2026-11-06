from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from app import models, project_network as network
from app.reglue_head import retarget_main_alternates
from app.fake_main_head import receipt_id
from test_project_network import env, change


@pytest.mark.parametrize('href,expected', [
    ('https://main.test/pl/?q=1&amp;v=2#section', 'https://next.test/pl/?q=1&amp;v=2#section'),
    ('//main.test:8443/pl/', '//next.test:8443/pl/'),
    ('http://MAIN.test/{{reqPath}}', 'http://next.test/{{reqPath}}'),
    ('https://{{settings.canon}}/pl/', 'https://{{settings.canon}}/pl/'),
    ('https://{{settings.canon}}{{reqPath}}', 'https://{{settings.canon}}{{reqPath}}'),
    ('https://other.test/pl/', 'https://other.test/pl/'),
    ('https://sub.main.test/pl/', 'https://sub.main.test/pl/'),
    ('/pl/', '/pl/'),
])
def test_only_literal_old_host_is_retargeted(href, expected):
    markup = f"<LINK rel='alternate' hreflang='pl' href='{href}' data-label='main.test' />"
    result = retarget_main_alternates({'canon': 'main.test', 'alternateMarkup': markup}, 'next.test')
    assert result.get('alternateMarkup', markup) == markup.replace(f"href='{href}'", f"href='{expected}'")


def test_manual_reglue_updates_old_main_links_preserves_variables_and_is_idempotent(env):
    db, site, remote = env
    markup = '<link rel="alternate" href="https://main.test/pl/" hreflang="pl" />\n<link rel="alternate" href="https://{{settings.canon}}/" hreflang="x-default" />'
    remote.data['head']['alternateMarkup'] = markup
    state = network.read_network(db, site)
    payload = network.NetworkChange(request_id=uuid4(), action='reglue', revision=state['revision'], domain='reserve.test')
    result = network.change_network(db, site, payload, 'test')
    assert result['alternateMarkup'] == markup.replace('https://main.test/', 'https://reserve.test/')
    parent = db.get(models.NetworkOperation, str(payload.request_id))
    assert parent.status == 'confirmed'
    assert db.get(models.NetworkOperation, receipt_id(parent)).status == 'confirmed'
    before = deepcopy(remote.calls)
    network.change_network(db, site, payload, 'test')
    network.read_network(db, site)
    assert remote.calls == before


@pytest.mark.parametrize('applied', [True, False])
def test_timeout_after_manual_reglue_never_replays_head(env, monkeypatch, applied):
    db, site, remote = env
    state = network.read_network(db, site)
    original = remote.request
    def request(method, path, payload):
        if path.endswith('update-head'):
            if applied: original(method, path, payload)
            else: remote.calls.append((method, path, deepcopy(payload)))
            raise httpx.ReadTimeout('lost response')
        return original(method, path, payload)
    monkeypatch.setattr(remote, 'request', request)
    change(env, 'reglue', state['revision'], domain='reserve.test')
    parent = db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.action=='reglue'))
    assert parent.status == ('confirmed' if applied else 'unknown')
    network.read_network(db, site)
    assert sum(path.endswith('update-head') for _, path, _ in remote.calls) == 1


def test_concurrent_alternate_edit_is_not_overwritten(env, monkeypatch):
    db, site, remote = env
    state = network.read_network(db, site)
    original = remote.request
    def request(method, path, payload):
        result = original(method, path, payload)
        if path.endswith('update-reglue'):
            remote.data['head']['alternateMarkup'] = '<link rel="alternate" href="https://external.test/" hreflang="pl" />'
        return result
    monkeypatch.setattr(remote, 'request', request)
    change(env, 'reglue', state['revision'], domain='reserve.test')
    parent = db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.action=='reglue'))
    assert parent.status == 'failed' and 'изменилась отдельно' in parent.message
    assert not any(path.endswith('update-head') for _, path, _ in remote.calls)
