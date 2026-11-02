import copy
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app import models, project_network as network
from app.fake_main import retarget_fake_head
from app.fake_main_head import receipt_id
from test_project_network import env, change


def prepare(env):
    db, site, remote = env
    remote.data['settings']['alternate'].update(fakeMain=['/cz/', '/lemons/'], enableDynamicRoutes=True, custom='keep')
    remote.data['head'].update(
        alternateMarkup='<link rel="alternate" href="https://{{settings.canon}}/" hreflang="cs" />\n'
            '<link rel="alternate" href="https://{{settings.canon}}/cz/" hreflang="cs-CZ" />',
        enableAlternates=False, enableCanonical=False,
        canonicalDefaultMarkup='<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}" />',
        canonicalFakeMainMarkup='<link rel="canonical" href="https://{{settings.canon}}/cz/" />')
    return network.read_network(db, site)


def parent(db):
    return db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.action == 'select_fake_main'))


@pytest.mark.parametrize('href,expected', [
    ('https://{{settings.canon}}/cz/', 'https://{{settings.canon}}/lemons/'),
    ('https://main.test/cz/?a=1&amp;b=2#cz', 'https://main.test/lemons/?a=1&amp;b=2#cz'),
    ('//main.test/cz/', '//main.test/lemons/'),
    ('/cz/#section', '/lemons/#section'),
    ('https://external.test/cz/', 'https://external.test/cz/'),
    ('https://main.test/nested/cz/', 'https://main.test/nested/cz/'),
    ('https://main.test/cz/child/', 'https://main.test/cz/child/'),
    ('https://main.test/cz1/', 'https://main.test/cz1/'),
    ('https://main.test/?next=/cz/', 'https://main.test/?next=/cz/'),
    ('https://{{settings.canon}}{{reqPath}}', 'https://{{settings.canon}}{{reqPath}}'),
])
def test_only_exact_local_href_changes(href, expected):
    markup = f"<LINK data-label='/cz/' href='{href}' hreflang='cs-CZ' rel='alternate' />"
    state = {'canon': 'main.test', 'domains': ['main.test'], 'alternateMarkup': markup}
    result = retarget_fake_head(state, '/cz/', '/lemons/')
    assert result.get('alternateMarkup', markup) == markup.replace(f"href='{href}'", f"href='{expected}'")


def test_select_syncs_path_and_head_preserving_every_other_setting(env):
    db, site, remote = env
    state = prepare(env)
    before = copy.deepcopy(remote.data)
    payload = network.NetworkChange(request_id=uuid4(), action='select_fake_main', revision=state['revision'], fake_main_path='/lemons/')
    result = network.change_network(db, site, payload, 'editor')
    assert result['fake_main_current'] == '/lemons/'
    assert '/lemons/' in result['canonicalFakeMainMarkup']
    assert '/lemons/' in result['alternateMarkup'] and '/cz/' not in result['alternateMarkup']
    assert result['canonicalDefaultMarkup'] == before['head']['canonicalDefaultMarkup']
    assert result['enableCanonical'] is result['enableAlternates'] is False
    assert remote.data['head']['customHeaders'] == before['head']['customHeaders']
    assert remote.data['settings']['alternate'] == {**before['settings']['alternate'], 'currentFakeMain': '/lemons/'}
    assert remote.calls[1] == ('PATCH', '/projects/update-head', {'folder': 'project.test',
        'alternateMarkup': result['alternateMarkup'], 'canonicalFakeMainMarkup': result['canonicalFakeMainMarkup']})
    assert parent(db).status == 'confirmed'
    assert db.get(models.NetworkOperation, receipt_id(parent(db))).status == 'confirmed'
    network.change_network(db, site, payload, 'editor')
    network.read_network(db, site)
    assert len(remote.calls) == 2


def test_fixed_default_canonical_is_replaced_too(env):
    db, site, remote = env
    prepare(env)
    remote.data['head']['canonicalDefaultMarkup'] = '<link rel="canonical" href="https://main.test/cz/" />'
    state = network.read_network(db, site)
    result = change(env, 'select_fake_main', state['revision'], fake_main_path='/lemons/')
    assert result['canonicalDefaultMarkup'] == '<link rel="canonical" href="https://main.test/lemons/" />'


@pytest.mark.parametrize('action,extra,expected_writes', [
    ('select_fake_main', {'fake_main_path': '/cz/'}, 1),
    ('select_fake_main', {'enable_dynamic_routes': False}, 1),
    ('create_fake_main', {'fake_main_path': '/new/'}, 1),
    ('create_fake_main', {'fake_main_path': '/new/', 'activate_fake_main': True}, 2),
])
def test_only_an_actual_current_path_change_updates_head(env, action, extra, expected_writes):
    db, site, remote = env
    state = prepare(env)
    change(env, action, state['revision'], **extra)
    assert len(remote.calls) == expected_writes


def test_waits_for_settings_before_sending_head_and_resumes_on_read(env):
    db, site, remote = env
    state = prepare(env)
    remote.delayed = True
    result = change(env, 'select_fake_main', state['revision'], fake_main_path='/lemons/')
    assert parent(db).status != 'confirmed' and len(remote.calls) == 1
    assert result['fake_main_current'] == '/cz/'
    remote.data['settings']['alternate'] = copy.deepcopy(remote.calls[0][2]['alternate'])
    remote.delayed = False
    result = network.read_network(db, site)
    assert parent(db).status == 'confirmed' and len(remote.calls) == 2
    assert '/lemons/' in result['canonicalFakeMainMarkup']


@pytest.mark.parametrize('applied', [True, False])
def test_timeout_is_reconciled_without_resending_head(env, monkeypatch, applied):
    db, site, remote = env
    state = prepare(env)
    original = remote.request
    def request(method, path, payload):
        if path.endswith('update-head'):
            remote.calls.append((method, path, copy.deepcopy(payload)))
            if applied:
                remote.data['head'].update({k: v for k, v in payload.items() if k != 'folder'})
            raise httpx.ReadTimeout('timeout')
        return original(method, path, payload)
    monkeypatch.setattr(remote, 'request', request)
    change(env, 'select_fake_main', state['revision'], fake_main_path='/lemons/')
    assert parent(db).status == ('confirmed' if applied else 'unknown')
    for _ in range(3): network.read_network(db, site)
    assert len(remote.calls) == 2
    remote.data['head'].update(parent(db).request_payload['head_sync'])
    network.read_network(db, site)
    assert parent(db).status == 'confirmed' and len(remote.calls) == 2


def test_separate_manual_head_edit_after_path_write_is_not_overwritten(env, monkeypatch):
    db, site, remote = env
    state = prepare(env)
    original = remote.request
    def request(method, path, payload):
        result = original(method, path, payload)
        if path.endswith('update-value'):
            remote.data['head']['canonicalFakeMainMarkup'] = '<link rel="canonical" href="https://main.test/manual/" />'
        return result
    monkeypatch.setattr(remote, 'request', request)
    result = change(env, 'select_fake_main', state['revision'], fake_main_path='/lemons/')
    assert result['fake_main_current'] == '/lemons/'
    assert '/manual/' in result['canonicalFakeMainMarkup']
    assert parent(db).status == 'failed' and 'изменилась отдельно' in parent(db).message
    assert len(remote.calls) == 1


def test_rejected_head_write_reports_partial_failure(env, monkeypatch):
    db, site, remote = env
    state = prepare(env)
    original = remote.request
    def request(method, path, payload):
        if path.endswith('update-head'):
            remote.calls.append((method, path, copy.deepcopy(payload)))
            return 200, {'success': False, 'message': 'rejected'}
        return original(method, path, payload)
    monkeypatch.setattr(remote, 'request', request)
    result = change(env, 'select_fake_main', state['revision'], fake_main_path='/lemons/')
    assert result['fake_main_current'] == '/lemons/'
    assert parent(db).status == 'failed' and 'rejected' in parent(db).message
    network.read_network(db, site)
    assert len(remote.calls) == 2
