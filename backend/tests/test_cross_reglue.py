import copy
from contextlib import nullcontext
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, auto_reglue as auto, project_network as network, cross_reglue as cross
from test_project_network import env


@pytest.fixture
def setup(env, monkeypatch):
    db, source, _ = env
    source.brand = 'Pin-Up'; source.cache_geo = 'az-AZ'; source.project_status = 'mass_actions'
    target = models.Site(name='destination.test', base_url='https://target.test', publication_endpoint='https://target.test/api', brand='Pin-Up', cache_geo='AZ', project_status='mass_actions', cache_canon='target.test')
    db.add(target); db.commit()
    class Remote:
        def __init__(self, data):
            self.data = data; self.calls = []; self.job_ready = True; self.fail_job = False
        def project(self): return copy.deepcopy(self.data)
        def job_state(self, job):
            return {'state': 'failed' if self.fail_job else 'completed' if self.job_ready else 'running', 'result': {'errorCount': int(self.fail_job)}}
        def request(self, method, path, payload):
            self.calls.append((path, copy.deepcopy(payload)))
            if path.endswith('check-domain'): return 200, {'reachable': True}
            if path == '/site-config/delete':
                self.data['settings']['domains'] = [d for d in self.data['settings']['domains'] if d not in payload['domains']]
                return 200, {'jobId': 'delete-job'}
            if path == '/site-config/create':
                self.data['settings']['domains'] += [d['domain'] for d in payload['domains']]
                return 200, {'jobId': 'add-job'}
            if path.endswith('update-reglue'):
                self.data['settings']['prev'] = self.data['settings']['canon']; self.data['settings']['canon'] = payload['reserve']
            elif path.endswith('update-value'):
                self.data['settings'].update(payload)
            else:
                self.data['head'].update(payload)
            return 200, {'ok': True}
    def data(main, domains):
        return {'settings': {'canon': main, 'domains': domains, 'port': 1234}, 'head': {'alternateMarkup': '<link rel="alternate" hreflang="az" href="https://' + main + '/az/" />', 'enableAlternates': True}}
    sr = Remote(data('main.test', ['main.test', 'next.test']))
    tr = Remote(data('target.test', ['target.test']))
    monkeypatch.setattr(network, 'Remote', lambda db, site: nullcontext(sr if site.id == source.id else tr))
    monkeypatch.setattr(network, 'project_server_url', lambda *args: 'https://server.test/')
    monkeypatch.setattr(auto, 'verify_pages', lambda urls: None)
    auto.save_config(db, auto.GlobalConfig(enabled=True, execution_mode='cross_network'))
    return db, source, target, sr, tr


def launch(setup):
    db, source, target, sr, tr = setup
    plan = auto.preview(db, target)
    run, _ = auto.prepare_run(db, target, uuid4(), plan['preview_token'], 'test', 'mass')
    return run


def test_transfer_main_and_alternate_snapshots_no_duplicate(setup):
    db, source, target, sr, tr = setup
    run = launch(setup)
    auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert 'next.test' not in sr.data['settings']['domains']
    assert tr.data['settings']['canon'] == 'next.test'
    assert 'https://target.test/az/' in run.plan['alternates_before']['markup']
    assert 'https://next.test/az/' in run.plan['alternates_after']['markup']
    assert run.plan['added_at'] == target.network_state['domain_added_at']['next.test']
    assert run.plan['elapsed_seconds'] >= 0
    before = len(sr.calls) + len(tr.calls)
    auto.execute(db, run.id)
    assert len(sr.calls) + len(tr.calls) == before


def test_waits_for_extraction_job_even_if_membership_removed(setup):
    db, source, target, sr, tr = setup
    run = launch(setup); sr.job_ready = False
    auto.execute(db, run.id)
    assert run.status == 'waiting'
    assert not tr.calls
    sr.job_ready = True
    auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert sum(path == '/site-config/delete' for path, _ in sr.calls) == 1


def test_waits_for_add_job_and_https_before_main(setup, monkeypatch):
    db, source, target, sr, tr = setup
    run = launch(setup); tr.job_ready = False
    auto.execute(db, run.id)
    assert run.status == 'waiting'
    assert tr.data['settings']['canon'] == 'target.test'
    tr.job_ready = True
    def unavailable(urls): raise ValueError('HTTPS unavailable')
    monkeypatch.setattr(auto, 'verify_pages', unavailable)
    auto.execute(db, run.id)
    assert run.status == 'waiting'
    assert tr.data['settings']['canon'] == 'target.test'
    monkeypatch.setattr(auto, 'verify_pages', lambda urls: None)
    auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert sum(path == '/site-config/create' for path, _ in tr.calls) == 1


def test_clean_cross_alternates(setup):
    db, _, target, _, tr = setup
    auto.save_config(db, auto.GlobalConfig(enabled=True, execution_mode='cross_network', scheme_mode='clean'))
    run = launch(setup); auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert run.plan['alternates_after'] == {'markup': '', 'enabled': False}
    assert tr.data['head']['alternateMarkup'] == ''
    op = db.get(models.NetworkOperation, cross.receipt_id(run, 'alternates'))
    assert op.request_payload['alternates_before']['markup']
    assert op.request_payload['alternateMarkup'] == ''


def test_ban_after_preview_stops_before_deletion(setup):
    db, source, target, sr, tr = setup
    run = launch(setup)
    network.update_domain_history(db, source, network.DomainHistoryUpdate(domain='next.test', field='ban', checked=True), 'user')
    auto.execute(db, run.id)
    assert run.status == 'failed' and 'БАН' in run.message
    assert sr.calls == tr.calls == []


def test_monthly_limit_and_unknown_date(setup):
    from datetime import datetime, timezone
    db, source, target, sr, tr = setup
    assert auto.preview(db, target)['new_main'] == 'next.test'
    source.network_state = {**source.network_state, 'domain_added_at': {'next.test': datetime.now(timezone.utc).isoformat()}}; db.commit()
    with pytest.raises(ValueError, match='Повторный перенос'):
        auto.preview(db, target)
    assert sr.calls == tr.calls == []


def test_access_brand_geo_and_source_reservation(setup):
    db, source, target, sr, tr = setup
    db.info['cross_allowed_site_ids'] = {target.id}
    with pytest.raises(ValueError, match='Нет подходящего'):
        auto.preview(db, target)
    db.info.clear()
    source.cache_geo = 'PL'; db.commit()
    with pytest.raises(ValueError, match='Нет подходящего'):
        auto.preview(db, target)
    source.cache_geo = 'AZ'; db.commit()
    run = launch(setup)
    assert auto.active_run(db, source.id).id == run.id
    with pytest.raises(network.NetworkConflict):
        network.change_network(db, source, network.NetworkChange(request_id=uuid4(), action='reserve', domain='next.test', revision='unused'), 'user')


def test_failed_job_never_adds_to_target(setup):
    db, _, _, sr, tr = setup
    run = launch(setup); sr.fail_job = True
    auto.execute(db, run.id)
    assert run.status == 'partial'
    assert tr.calls == []


def test_ban_after_extraction_prevents_addition(setup):
    db, source, target, sr, tr = setup
    run = launch(setup); sr.job_ready = False
    auto.execute(db, run.id)
    assert run.status == 'waiting'
    from app.domain_transfer_policy import set_ban
    set_ban(db, source, 'next.test', True, 'user')
    sr.job_ready = True
    auto.execute(db, run.id)
    assert run.status == 'partial' and 'БАН' in run.message
    assert not tr.calls


def test_cross_add_requires_extraction_receipt(setup):
    db, source, target, sr, tr = setup
    run = launch(setup)
    state = network.read_network(db, target)
    with pytest.raises(ValueError, match='извлечения'):
        network.change_network(db, target, network.NetworkChange(request_id=uuid4(), action='create_domains', domains=['next.test'], revision=state['revision']), 'user', auto_run_id=run.id)
    assert not tr.calls


def test_ordinary_add_does_not_require_extraction(setup):
    db, source, target, sr, tr = setup
    state = network.read_network(db, target)
    network.change_network(db, target, network.NetworkChange(request_id=uuid4(), action='create_domains', domains=['fresh.test'], revision=state['revision']), 'user')
    assert 'fresh.test' in tr.data['settings']['domains']


def test_brand_mismatch_and_used_history_exclude_donor(setup):
    db, source, target, sr, tr = setup
    source.brand = 'Other Brand'; db.commit()
    with pytest.raises(ValueError, match='Нет подходящего'):
        auto.preview(db, target)
    source.brand = target.brand; db.commit()
    network.read_network(db, source)
    network.update_domain_history(db, source, network.DomainHistoryUpdate(domain='next.test', field='alternate', checked=True), 'user')
    with pytest.raises(ValueError, match='истории использования'):
        auto.preview(db, target)
