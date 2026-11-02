from uuid import uuid4

import pytest
from sqlalchemy import select

from app import auto_reglue as auto, models, project_network as network
from app.alternate_templates import base_alternate_markup
from app.network_state import alternate_links
from test_project_network import env
from test_cross_reglue import setup


def links(markup):
    return {link['hreflang']: link['href'] for link in alternate_links(markup)}


@pytest.mark.parametrize('language,geo', [('pl', 'PL'), ('cs', 'CZ'), ('az', 'AZ'), ('de', 'DE'), ('pt-BR', 'BR')])
def test_base_markup_uses_each_project_locale(language, geo):
    lang = language.split('-')[0]
    assert links(base_alternate_markup('main.test', language, geo, '/new/')) == {
        lang: 'https://main.test/', f'{lang}-{geo}': 'https://main.test/new/', 'x-default': 'https://main.test/'}


@pytest.mark.parametrize('geo,language', [('PL', 'pl'), ('CZ', 'cs'), ('AZ', 'az'), ('BR', 'pt')])
def test_mass_within_network_replaces_all_links_and_creates_new_current_path(env, monkeypatch, geo, language):
    db, site, remote = env
    site.project_status = 'mass_actions'; site.cache_geo = geo; site.cache_language = language
    remote.data['settings']['domains'] = ['main.test', 'next.project.test', 'last.project.test']
    before = remote.data['head']['alternateMarkup']
    db.commit()
    monkeypatch.setattr(auto, 'verify_pages', lambda urls: None)
    auto.save_config(db, auto.GlobalConfig(enabled=True, scheme_mode='locale_base'))
    auto.save_config(db, auto.ProjectConfig(enabled=True, drop_domain='project.test', use_current_fake_main=True), site.id)
    plan = auto.preview(db, site)
    assert plan['create_fake_main_path'] != '/cz/'
    run, _ = auto.prepare_run(db, site, uuid4(), plan['preview_token'], 'test', 'mass')
    auto.execute(db, run.id); db.refresh(run)
    assert run.status == 'completed', run.message
    path = run.plan['create_fake_main_path']
    assert links(remote.data['head']['alternateMarkup']) == {
        language: 'https://next.project.test/', f'{language}-{geo}': 'https://next.project.test' + path,
        'x-default': 'https://next.project.test/'}
    assert remote.data['settings']['alternate']['currentFakeMain'] == path
    assert remote.data['head']['canonicalFakeMainMarkup'] == auto.fake_canonical_markup(path)
    assert run.plan['alternates_before']['markup'] == before
    assert run.plan['alternates_after']['markup'] == remote.data['head']['alternateMarkup']
    writes = len(remote.calls)
    auto.execute(db, run.id)
    assert len(remote.calls) == writes
    assert auto.preview(db, site)['create_fake_main_path'] != path


def configure_cross(setup, geo='PL', language='pl'):
    db, source, target, sr, tr = setup
    source.cache_geo = target.cache_geo = geo
    target.cache_language = language
    tr.data['settings']['alternate'] = {'fakeMain': ['/existing/'], 'currentFakeMain': '/existing/', 'enableDynamicRoutes': True}
    db.commit()
    auto.save_config(db, auto.GlobalConfig(enabled=True, execution_mode='cross_network', scheme_mode='locale_base'))
    plan = auto.preview(db, target)
    run, _ = auto.prepare_run(db, target, uuid4(), plan['preview_token'], 'test', 'mass')
    return run


@pytest.mark.parametrize('geo,language', [('PL', 'pl'), ('CZ', 'cs'), ('AZ', 'az'), ('DE', 'de')])
def test_cross_network_base_scheme_and_confirmed_history(setup, geo, language):
    db, source, target, sr, tr = setup
    before = tr.data['head']['alternateMarkup']
    run = configure_cross(setup, geo, language)
    assert run.plan['old_fake_main_path'] == '/existing/'
    path = run.plan['create_fake_main_path']
    auto.execute(db, run.id); db.refresh(run)
    assert run.status == 'completed', run.message
    assert links(tr.data['head']['alternateMarkup']) == {
        language: 'https://next.test/', f'{language}-{geo}': 'https://next.test' + path, 'x-default': 'https://next.test/'}
    assert tr.data['settings']['alternate']['currentFakeMain'] == path
    assert tr.data['head']['canonicalFakeMainMarkup'] == auto.fake_canonical_markup(path)
    assert run.plan['alternates_before']['markup'] == before
    assert run.plan['alternates_after']['markup'] == tr.data['head']['alternateMarkup']
    assert run.plan['applied_result']['fake_main_path'] == path
    operation = db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.site_id == target.id,
        models.NetworkOperation.action == 'alternates'))
    assert operation.request_payload['alternates_before']['markup'] == before
    writes = len(sr.calls) + len(tr.calls)
    auto.execute(db, run.id)
    assert len(sr.calls) + len(tr.calls) == writes


def test_cross_waits_for_new_fake_page_without_resending(setup):
    db, source, target, sr, tr = setup
    run = configure_cross(setup)
    request = tr.request
    def delayed(method, path, payload):
        if path.endswith('update-value') and 'alternate' in payload:
            tr.calls.append((path, payload))
            return 200, {'ok': True}
        return request(method, path, payload)
    tr.request = delayed
    auto.execute(db, run.id); db.refresh(run)
    assert run.status == 'waiting' and tr.data['settings']['canon'] == 'target.test'
    auto.execute(db, run.id)
    assert sum('alternate' in body for _, body in tr.calls) == 1
    payload = next(body for _, body in tr.calls if 'alternate' in body)
    tr.data['settings']['alternate'] = payload['alternate']
    auto.execute(db, run.id); db.refresh(run)
    assert run.status == 'completed', run.message


def test_manual_replacement_records_original_and_new_markup(env):
    db, site, remote = env
    state = network.read_network(db, site)
    before = state['alternateMarkup']
    markup = base_alternate_markup('{{settings.canon}}', 'cs', 'CZ', '/cz/')
    result = network.change_network(db, site, network.NetworkChange(request_id=uuid4(), action='alternates',
        revision=state['revision'], alternate_markup=markup, enable_alternates=True), 'test')
    operation = result['operations'][0]
    assert operation['alternates_before']['markup'] == before
    assert operation['alternates_after']['markup'] == markup
    assert result['alternateMarkup'] == markup


def test_base_root_mode_needs_no_separate_xdefault_or_subdomain(env):
    db, site, remote = env
    site.cache_geo = 'pt-BR'; site.cache_language = 'pt-BR'; site.project_status = 'mass_actions'
    site.domain_types = {'next.test': 'newreg'}
    state = network.read_network(db, site)
    cfg = auto.ProjectConfig(enabled=True, domain_layout='root_main', parent_kind='newreg')
    plan = auto.build_plan(site, state, auto.GlobalConfig(enabled=True, scheme_mode='locale_base'), cfg)
    assert plan['new_main'] == plan['x_default_domain'] == 'next.test'
    assert set(links(plan['alternateMarkup'])) == {'pt', 'pt-BR', 'x-default'}


def test_cross_missing_language_rejected_before_any_mutation(setup):
    db, source, target, sr, tr = setup
    with pytest.raises(ValueError):
        configure_cross(setup, 'CZ', '')
    assert sr.calls == tr.calls == []


def test_cross_waits_for_canonical_confirmation_without_rewriting(setup):
    db, source, target, sr, tr = setup
    run = configure_cross(setup)
    request = tr.request
    def ignore_canonical(method, path, payload):
        result = request(method, path, payload)
        if path.endswith('update-head'):
            tr.data['head'].pop('canonicalFakeMainMarkup', None)
        return result
    tr.request = ignore_canonical
    auto.execute(db, run.id); db.refresh(run)
    assert run.status == 'waiting' and 'applied_result' not in run.plan
    writes = len(sr.calls) + len(tr.calls)
    auto.execute(db, run.id)
    assert len(sr.calls) + len(tr.calls) == writes
    tr.data['head']['canonicalFakeMainMarkup'] = run.plan['canonicalFakeMainMarkup']
    auto.execute(db, run.id); db.refresh(run)
    assert run.status == 'completed', run.message
