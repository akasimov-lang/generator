from uuid import uuid4
import pytest
from app import auto_reglue as auto, cross_reglue as cross, cross_reglue_batch as batch, project_network as network, models
from app.network_reserve import selected_reserve
from app.network_state import observe_network
from app.domain_transfer_queue import listing
from test_project_network import env
from test_cross_reglue import setup, launch
from test_cross_reglue_batch import pool, reserve, finish
from test_move_plus2 import init


def select(remote, domain):
    remote.data['settings'].update(reserveOption=domain, reserve=domain)


@pytest.mark.parametrize('scheme', ['preserve', 'clean', 'locale_base'])
def test_selected_reserve_promotes_without_extracting_or_importing(setup, scheme):
    db, source, target, sr, tr = setup
    target.cache_language = 'az-AZ'; db.commit()
    tr.data['settings']['domains'].append('local-reserve.test')
    select(tr, 'local-reserve.test')
    tr.data['settings']['redirects'] = [{'url': 'old-redirect.test', 'value': 'target.test'}]
    auto.save_config(db, auto.config(db).model_copy(update={'scheme_mode': scheme}))
    run = launch(setup)
    assert run.plan['use_selected_reserve'] and run.plan['new_main'] == 'local-reserve.test'
    auto.execute(db, run.id)
    assert run.status == 'completed', run.message
    assert tr.data['settings']['canon'] == 'local-reserve.test'
    assert tr.data['settings']['redirects'] == [{'url': 'old-redirect.test', 'value': 'local-reserve.test'}]
    assert not sr.calls
    assert not any(path in {'/site-config/create', '/site-config/delete'} for path, _ in tr.calls)
    assert len(tr.data['settings']['domains']) == 2
    assert not listing(db, target.brand, 'AZ')['entries']
    assert target.cache_reserve is None  # Used reserve is now Main.
    before = len(tr.calls)
    auto.execute(db, run.id)
    assert len(tr.calls) == before


def test_mixed_batch_uses_local_reserve_and_donates_other_newreg(pool):
    db, source, target, remotes, add = pool
    sr = remotes[source.id]
    sr.data['settings']['domains'].append('own-reserve.test')
    select(sr, 'own-reserve.test')
    preview = batch.build(db, [source, target], 'test')
    assert not preview['skipped']
    local = next(p for p in preview['plans'] if p['site_id'] == source.id)
    incoming = next(p for p in preview['plans'] if p['site_id'] == target.id)
    assert local['use_selected_reserve'] and local['new_main'] == 'own-reserve.test'
    assert incoming['source_site_id'] == source.id and incoming['new_main'] == 'next.test'
    runs = reserve(db, preview)
    finish(db, runs)
    assert sr.data['settings']['canon'] == 'own-reserve.test'
    assert remotes[target.id].data['settings']['canon'] == 'next.test'
    assert sum(path == '/site-config/delete' for path, _ in sr.calls) == 1
    assert not any(path == '/site-config/create' for path, _ in sr.calls)


def test_reserve_added_after_preview_blocks_extraction(setup):
    db, source, target, sr, tr = setup
    run = launch(setup)
    tr.data['settings']['domains'].append('local-reserve.test')
    select(tr, 'local-reserve.test')
    auto.execute(db, run.id)
    assert run.status == 'failed' and 'TARGET_HAS_RESERVE' in run.message
    assert not sr.calls and not tr.calls


def test_low_level_delete_rechecks_recipient_reserve(setup):
    db, source, target, sr, tr = setup
    run = launch(setup)
    state = network.read_network(db, source)
    select(tr, 'local-reserve.test')
    with pytest.raises(ValueError, match='TARGET_HAS_RESERVE'):
        network.change_network(db, source, network.NetworkChange(request_id=cross.receipt_id(run, 'delete_domain'),
            action='delete_domain', domain='next.test', revision=state['revision']), 'test', auto_run_id=run.id)
    assert not sr.calls


def test_invalid_selected_reserve_never_falls_back_to_other_network(setup):
    db, source, target, sr, tr = setup
    select(tr, 'missing.test')
    with pytest.raises(ValueError, match='резерв отсутствует'):
        auto.preview(db, target)
    assert not sr.calls and not tr.calls


def test_blank_primary_reserve_alias_is_still_protected(setup):
    db, source, target, sr, tr = setup
    sr.data['settings'].update(reserveOption='', reserve='next.test')
    state = network.read_network(db, source)
    assert source.cache_reserve == 'next.test'
    from app.schemas import SiteResponse
    assert SiteResponse.model_validate(source).cache_reserve == 'next.test'
    with pytest.raises(ValueError, match='занят'):
        cross.transferable(source, state, 'next.test')
    with pytest.raises(ValueError, match='резерв'):
        network.change_network(db, source, network.NetworkChange(request_id=uuid4(), action='delete_domain',
            domain='next.test', revision=state['revision']), 'test')
    observe_network(source, {'settings': {'canon': 'main.test'}})
    assert source.cache_reserve == 'next.test'


def test_fallback_uses_newreg_even_if_drop_is_first(setup):
    db, source, target, sr, tr = setup
    sr.data['settings']['domains'].insert(1, 'drop.test')
    source.domain_types = {**source.domain_types, 'drop.test': 'drop'}; db.commit()
    assert auto.preview(db, target)['new_main'] == 'next.test'
    source.domain_types = {'drop.test': 'drop', 'next.test': 'drop'}; db.commit()
    with pytest.raises(ValueError, match='Нет подходящего'):
        auto.preview(db, target)


def test_move_excludes_reserved_recipient_but_can_use_another(pool):
    from app import move_plus2 as plus
    db, sites, remotes, filters, roots = init(pool)
    recipient = sites[2]
    remotes[recipient.id].data['settings']['domains'].append('reserve.test')
    select(remotes[recipient.id], 'reserve.test')
    run, _ = plus.prepare(db, uuid4(), filters, [s.id for s in sites], 'test')
    assert run.site_id == sites[3].id
    assert all(d['domain'] != 'reserve.test' for d in run.plan['domains'])


def test_used_reserve_equal_to_main_is_not_a_new_reserve():
    assert not selected_reserve({'canon': 'current.test', 'reserve': 'www.current.test'})


def test_all_networks_with_reserves_only_change_their_own_main(pool):
    db, source, target, remotes, add = pool
    for site in (source, target):
        domain = 'reserve-' + site.name
        remotes[site.id].data['settings']['domains'].append(domain)
        select(remotes[site.id], domain)
    preview = batch.build(db, [source, target], 'test')
    assert len(preview['plans']) == 2 and all(p['use_selected_reserve'] for p in preview['plans'])
    finish(db, reserve(db, preview))
    assert not any(path in {'/site-config/create', '/site-config/delete'} for r in remotes.values() for path, _ in r.calls)


def test_report_check_of_local_reserve_never_creates_transfer_queue(setup):
    from app import transfer_report_check as check
    db, source, target, sr, tr = setup
    tr.data['settings']['domains'].append('local-reserve.test'); select(tr, 'local-reserve.test')
    run = launch(setup); auto.execute(db, run.id)
    job = models.BackgroundJob(id=str(uuid4()), kind=check.KIND, payload={'actor': 'test'})
    db.add(job); db.commit()
    result = check.check_run(db, job, run)
    assert result['domains'][0]['code'] == 'OK'
    assert not listing(db, target.brand, 'AZ')['entries']


def test_newreg_reclassified_after_preview_is_not_extracted(setup):
    db, source, target, sr, tr = setup
    run = launch(setup)
    source.domain_types = {'next.test': 'drop'}; db.commit()
    auto.execute(db, run.id)
    assert run.status == 'failed' and 'новорег' in run.message
    assert not sr.calls and not tr.calls


def test_local_reserve_failure_report_preserves_actual_reason(setup):
    from app.mass_action_reports import entry
    db, source, target, sr, tr = setup
    tr.data['settings']['domains'].append('local-reserve.test'); select(tr, 'local-reserve.test')
    run = launch(setup)
    select(tr, 'changed.test'); auto.execute(db, run.id)
    result = entry(run)
    assert run.status == 'failed' and 'резерв изменился' in result['message']
    assert not result['domain_errors']
