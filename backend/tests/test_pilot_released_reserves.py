from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import models, auto_reglue as auto, auto_pilot as pilot, mass_reglue_launch as launch
from app import pilot_variations as variations, reglue_reserves as stock, cross_reglue_batch as batch
from app.domain_transfer_policy import set_ban
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, finish

USER = {'username': 'test', 'allowed_site_ids': None}


def prepared(pool, monkeypatch, count=2, reserves=1, subdomains=50):
    db, source, target, remotes, add = pool
    source.project_status = target.project_status = 'working'
    cfg = auto.config(db); cfg.scheme_mode = 'locale_base'; auto.save_config(db, cfg)
    sites = [add(name + '.test', brand='Общие ключи', geo='PL', site_type='general', cache_language='pl')
             for name in ('alpha', 'bravo', 'charlie')[:count]]
    for site in sites:
        current = 'current-' + site.name
        site.domain_types = {site.name:'newreg', current:'newreg'}
        site.cache_canon = current
        site.main_domain_history = [current]
        remotes[site.id].data['settings'].update(canon=current, domains=[site.name,current])
        remotes[site.id].data['head']['alternateMarkup'] = f'<link rel="alternate" hreflang="pl" href="https://{current}/" />'
    db.commit()
    stock.import_domains(db, '\n'.join(('spare.test', 'backup.test')[:reserves]), 'drop', '', 'test')
    job = pilot.create(db, uuid4(), USER, percentages={'subdomains':subdomains, 'without_alternates':0,
        'redirects':0, 'title_h1':0, 'paragraphs':0, 'internal_pages':0})
    with monkeypatch.context() as patch:
        patch.setattr(variations, 'finalize', lambda *args: None)
        launch.execute_step(db, job.id, lambda _: pytest.fail('Preview must not dispatch'))
    assert job.status == 'queued'
    assert sum(item['status'] == 'skipped' for item in job.result['items'].values()) == count - reserves
    assert all(item.get('retry_state') for item in job.result['items'].values() if item['status'] == 'skipped')
    return db, sites, remotes, job


def finalize(db, job):
    launch.execute_step(db, job.id, lambda _: pytest.fail('Preview must not dispatch'))
    assert job.status == 'completed', job.error
    if job.payload['percentages']['subdomains']:
        assert any(p.get('create_subdomain') for g in job.result['groups'] for p in g.get('plans', []))
    return [p for g in job.result['groups'] for p in g.get('plans', [])]


def test_released_stock_recovers_skipped_project_and_saved_manifest(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    plans = finalize(db, job)
    assert len(plans) == 2
    assert len({p['new_main'] for p in plans}) == 2
    assert sum(bool(p.get('create_subdomain')) for p in plans) == 1
    recovered = next(p for p in plans if p.get('reserve_pool_id'))
    assert recovered['site_id'] == sites[1].id and recovered['new_main'] == 'spare.test'
    assert recovered['reallocated_from_site_id'] == sites[0].id
    assert recovered['mass_filter']['geo'] == 'PL'
    ledger = db.get(models.AutoReglueConfig, batch.key(job.result['groups'][0]['batch_id']))
    assert ledger.value['plans'] == plans and ledger.value['skipped'] == []
    assert job.result['items'][sites[1].id]['status'] == 'ready'
    assert job.result['reserve_reallocation'][0]['previous_reason']
    assert db.scalar(select(models.ReglueReserveDomain)).status == 'available'
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not remote.calls for remote in remotes.values())
    before = deepcopy(job.result)
    finalize(db, job)
    assert job.result == before


def test_recovery_recomputes_global_subdomain_share(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch, count=3, reserves=2)
    plans = finalize(db, job)
    assert len(plans) == 3
    assert sum(bool(p.get('create_subdomain')) for p in plans) == 2
    assert job.result['variation_summary']['total'] == 3
    assert job.result['variation_summary']['subdomains_requested'] == 2
    assert len({p['new_main'] for p in plans}) == 3
    assert all(not remote.calls for remote in remotes.values())


def test_disabled_participation_is_not_recovered(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    sites[1].reglue_participation = False; db.commit()
    plans = finalize(db, job)
    assert len(plans) == 1
    assert job.result['items'][sites[1].id]['status'] == 'skipped'


def test_banned_released_stock_is_not_reused(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    set_ban(db, sites[1], 'spare.test', True, 'test')
    assert len(finalize(db, job)) == 1


def test_stock_claimed_by_another_launch_is_not_reused(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    reserve = db.scalar(select(models.ReglueReserveDomain))
    reserve.status = 'reserved'; reserve.run_id = str(uuid4()); db.commit()
    assert len(finalize(db, job)) == 1


def test_used_main_is_not_recovered_from_released_stock(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    sites[1].main_domain_history = ['spare.test']; db.commit()
    assert len(finalize(db, job)) == 1


def test_changed_brand_does_not_cross_saved_scope(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    sites[1].brand = 'Different'; sites[1].site_type = 'monobrand'; db.commit()
    assert len(finalize(db, job)) == 1


def test_retained_stock_is_not_assigned_twice(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch, subdomains=0)
    plans = finalize(db, job)
    assert len(plans) == 1 and plans[0]['new_main'] == 'spare.test'
    assert not job.result.get('reserve_reallocation')


def test_az_restriction_remains_in_recovery(pool, monkeypatch):
    from app.pilot_released_reserves import recover
    db, sites, remotes, job = prepared(pool, monkeypatch)
    old = deepcopy(job.result['groups'][0]['plans'])
    plans = [{**old[0], 'new_main':'pl.alpha.test', 'reserve_pool_id':None, 'parent_domain':'alpha.test'}]
    sites[1].cache_geo = 'AZ'
    result = deepcopy(job.result)
    result['groups'][0]['filter']['geo'] = 'AZ'
    db.commit()
    assert recover(db, job, result, old, plans) == []


def test_non_capacity_failure_has_no_retry_snapshot():
    from app.priority_main_targets import retry_snapshot
    assert retry_snapshot('Webdev недоступен', {'canon':'old.test'}) is None


def test_one_released_reserve_cannot_recover_two_targets(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch, count=3, reserves=1)
    plans = finalize(db, job)
    assert len(plans) == 2
    assert sum(bool(p.get('reserve_pool_id')) for p in plans) == 1
    assert sum(item['status'] == 'skipped' for item in job.result['items'].values()) == 1


def test_changed_stock_record_is_not_treated_as_released_domain(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    row = db.scalar(select(models.ReglueReserveDomain))
    row.domain = 'different.test'; db.commit()
    assert len(finalize(db, job)) == 1


def test_recovery_does_not_expand_saved_project_access(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    job.payload = {**job.payload, 'allowed': [sites[0].id]}; db.commit()
    assert len(finalize(db, job)) == 1


def test_recovered_plan_is_reserved_and_executes_as_reviewed(pool, monkeypatch):
    db, sites, remotes, job = prepared(pool, monkeypatch)
    plans = finalize(db, job)
    recovered = next(p for p in plans if p.get('reserve_pool_id'))
    for remote in remotes.values():
        original = remote.request
        def request(method, path, payload, original=original, remote=remote):
            if path == '/site-config/create-subdomains':
                remote.data['settings']['domains'] += payload['domains']
                return 200, {'ok':True}
            return original(method, path, payload)
        remote.request = request
    pilot.start(db, job.id, USER)
    sent = []
    launch.execute_step(db, job.id, sent.append)
    assert len(sent) == 2
    runs = [db.get(models.AutoReglueRun, id) for id in sent]
    finish(db, runs)
    assert remotes[recovered['site_id']].data['settings']['canon'] == recovered['new_main']
    reserve = db.get(models.ReglueReserveDomain, recovered['reserve_pool_id'])
    assert reserve.status == 'assigned' and reserve.site_id == recovered['site_id']
