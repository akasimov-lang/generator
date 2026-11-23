from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import models, project_network as network, reglue_redirect_policy as policy
from app.auto_reglue_api import redirect_policy, update_redirect_policy, ParticipationRequest
from test_project_network import env, change

ROWS = [{'url': 'old.test', 'value': 'main.test/path/', 'metadata': 'keep'},
        {'url': 'custom.test', 'value': 'external.test/offer/'}]


def test_policy_defaults_off_and_is_saved_per_project(env):
    db, site, _ = env
    assert policy.enabled(db, site.id) is False
    policy.save(db, site, True, 'anton')
    db.expire_all()
    assert policy.enabled(db, site.id) is True
    assert policy.enabled(db, 'other-project') is False
    policy.save(db, site, False, 'anton')
    assert policy.enabled(db, site.id) is False


def test_policy_api_checks_project_access_for_reads_and_writes(env):
    db, site, _ = env
    user = {'username': 'anton', 'allowed_site_ids': []}
    with pytest.raises(HTTPException) as read_error:
        redirect_policy(site.id, user, db)
    assert read_error.value.status_code == 404
    with pytest.raises(HTTPException) as write_error:
        update_redirect_policy(site.id, ParticipationRequest(enabled=True), user, db)
    assert write_error.value.status_code == 404
    assert not policy.enabled(db, site.id)
    user['allowed_site_ids'] = [site.id]
    assert update_redirect_policy(site.id, ParticipationRequest(enabled=True), user, db)['enabled']
    assert redirect_policy(site.id, user, db)['enabled']


def test_manual_reglue_preserves_all_redirects_by_default(env):
    db, site, remote = env
    remote.data['settings']['redirects'] = deepcopy(ROWS)
    before = network.read_network(db, site)
    result = change(env, 'reglue', before['revision'], domain='reserve.test')
    assert result['canon'] == 'reserve.test'
    assert result['domain_redirects'] == ROWS
    assert not any('redirects' in payload for _, _, payload in remote.calls)
    parent = next(op for op in result['operations'] if op['action'] == 'reglue')
    assert parent['status'] == 'confirmed'
    assert parent['redirects_after'] == ROWS


def test_webdev_automatic_retarget_is_restored_when_policy_off(env):
    db, site, remote = env
    remote.data['settings']['redirects'] = deepcopy(ROWS)
    native = remote.request
    def request(method, path, payload):
        result = native(method, path, payload)
        if path.endswith('update-reglue'):
            remote.data['settings']['redirects'] = [{'url': 'old.test', 'value': payload['reserve']}]
        return result
    remote.request = request
    before = network.read_network(db, site)
    result = change(env, 'reglue', before['revision'], domain='reserve.test')
    assert result['domain_redirects'] == ROWS
    assert len([p for _, _, p in remote.calls if 'redirects' in p]) == 1
    network.read_network(db, site)
    assert len([p for _, _, p in remote.calls if 'redirects' in p]) == 1


def test_new_main_with_own_redirect_is_not_promoted_while_policy_off(env):
    db, site, remote = env
    remote.data['settings']['redirects'] = [{'url': 'reserve.test', 'value': 'main.test'}]
    before = network.read_network(db, site)
    with pytest.raises(ValueError, match='Новый Main сам перенаправляется'):
        change(env, 'reglue', before['revision'], domain='reserve.test')
    assert not remote.calls


def test_automatic_reglue_also_preserves_redirects_by_default(env, monkeypatch):
    from app import auto_reglue as auto
    db, site, remote = env
    site.brand = 'Pin-Up'; site.cache_geo = 'AZ'; site.cache_language = 'az'; site.project_status = 'mass_actions'
    site.domain_types = {'reserve.test': 'newreg', 'next.test': 'newreg'}; db.commit()
    auto.save_config(db, auto.GlobalConfig(enabled=True, scheme_mode='clean'))
    auto.save_config(db, auto.ProjectConfig(enabled=True, domain_layout='root_main', parent_kind='newreg', language='az'), site.id)
    remote.data['settings']['redirects'] = deepcopy(ROWS)
    monkeypatch.setattr(auto, 'verify_pages', lambda urls: None)
    plan = auto.preview(db, site)
    run, _ = auto.prepare_run(db, site, uuid4(), plan['preview_token'], 'test', 'mass')
    auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert remote.data['settings']['redirects'] == ROWS
    assert not any('redirects' in payload for _, _, payload in remote.calls)


def test_enabled_policy_retargets_existing_old_main_endpoint(env):
    db, site, remote = env
    policy.save(db, site, True, 'anton')
    remote.data['settings']['redirects'] = [{'url': 'old.test', 'value': 'main.test'}]
    before = network.read_network(db, site)
    result = change(env, 'reglue', before['revision'], domain='reserve.test')
    assert result['domain_redirects'] == [{'url': 'old.test', 'value': 'reserve.test'}]
    assert next(op for op in result['operations'] if op['action'] == 'reglue')['status'] == 'confirmed'


def test_saved_receipt_keeps_policy_when_checkbox_changes_later(env):
    from app.domain_redirects import for_reglue
    db, site, remote = env
    remote.data['settings']['redirects'] = deepcopy(ROWS)
    before = network.read_network(db, site)
    result = change(env, 'reglue', before['revision'], domain='reserve.test')
    op = next(op for op in result['operations'] if op['action'] == 'reglue')
    receipt = db.get(models.NetworkOperation, op['id'])
    policy.save(db, site, True, 'anton')
    assert receipt.request_payload['redirect_to_main'] is False
    assert for_reglue({**result, 'redirects_verified': True}, receipt.request_payload) == ROWS
