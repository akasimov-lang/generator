import copy
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, auto_reglue as auto, cross_reglue as cross, cross_reglue_batch as batch, project_network as network
from app.domain_transfer_policy import record_transfer_cooldown, require_transfer_allowed, set_ban, policy_key
from test_project_network import env
from test_cross_reglue import setup


@pytest.fixture
def pool(setup, monkeypatch):
    db, source, target, sr, tr = setup
    remotes = {source.id: sr, target.id: tr}
    monkeypatch.setattr(network, 'Remote', lambda db, site: nullcontext(remotes[site.id]))
    def add(name, size=1, free=0, **kwargs):
        site = models.Site(name=name, base_url='https://' + name, publication_endpoint='/',
            cache_canon=name, brand=kwargs.pop('brand', 'Pin-Up'), cache_geo=kwargs.pop('geo', 'AZ'),
            project_status=kwargs.pop('status', 'mass_actions'), **kwargs)
        db.add(site); db.commit()
        domains = [name, *[f'free-{i}-{name}' for i in range(free)]]
        domains += [f'sub{i}.{name}' for i in range(size - len(domains))]
        site.domain_types = {d: 'newreg' for d in domains[1:free+1]}; db.commit()
        remotes[site.id] = sr.__class__({'settings': {'redirects': [], 'canon': name, 'domains': domains, 'port': 1234},
            'head': {'alternateMarkup': f'<link rel="alternate" hreflang="az" href="https://{name}/" />', 'enableAlternates': True}})
        return site
    return db, source, target, remotes, add


def reserve(db, preview):
    return [run for run, _ in batch.reserve(db, preview['batch_id'], [dict(site_id=p['site_id'], request_id=uuid4(), preview_token=p['preview_token']) for p in preview['plans']], 'test')]


def finish(db, runs):
    for _ in range(len(runs) + 3):
        for run in runs:
            auto.execute(db, run.id)
        if all(run.status == 'completed' for run in runs):
            return
    assert False, [(run.status, run.message) for run in runs]


def test_selects_largest_donor_instead_of_first_name(pool):
    db, source, target, remotes, add = pool
    big = add('z-big.test', 25, 15)
    plan = auto.preview(db, target)
    assert plan['source_site_id'] == big.id
    assert plan['source_count'] == 25 and plan['target_count'] == 1
    assert all(not r.calls for r in remotes.values())


def test_all_available_domains_one_in_and_no_mutations_during_preview(pool):
    db, source, target, remotes, add = pool
    source.project_status = target.project_status = 'working'; db.commit()
    donor = add('large.test', 30, 20)
    recipients = [add(f'small-{i}.test') for i in range(15)]
    preview = batch.build(db, recipients, 'test')
    assert len(preview['plans']) == 15 and not preview['skipped']
    assert Counter(p['source_site_id'] for p in preview['plans']) == {donor.id: 15}
    assert len({p['site_id'] for p in preview['plans']}) == 15
    assert len({p['new_main'] for p in preview['plans']}) == 15
    directions = {(p['source_site_id'], p['site_id']) for p in preview['plans']}
    assert not any((b, a) in directions for a, b in directions)
    assert all(not r.calls for r in remotes.values())


def test_pinup_shape_gives_every_network_one_domain_and_large_networks_exchange(pool):
    db, source, target, remotes, add = pool
    source.project_status = target.project_status = 'working'; db.commit()
    large = [add(f'large-{i}.test', size, min(15, size-1)) for i, size in enumerate([73, 28, 27, 20, 19])]
    small = [add(f'small-{i}.test', 3) for i in range(11)]
    preview = batch.build(db, large + small, 'test')
    plans = preview['plans']
    assert not preview['skipped']
    assert len(plans) == 16
    assert Counter(p['site_id'] for p in plans) == {site.id: 1 for site in large + small}
    assert all(p['source_site_id'] in {s.id for s in large} for p in plans)
    assert any(p['site_id'] == large[0].id and p['balance_mode'] == 'peer_exchange' for p in plans)
    exchange = [p for p in plans if p['site_id'] in {s.id for s in large}]
    assert Counter(p['source_site_id'] for p in exchange) == {s.id: 1 for s in large}
    assert all(p['balance_mode'] == 'peer_exchange' for p in exchange)
    batch.validate(plans)


def test_odd_large_group_forms_a_cycle_and_waits_for_all_extractions(pool):
    db, source, target, remotes, add = pool
    source.project_status = target.project_status = 'working'; db.commit()
    sites = [add(f'peer-{i}.test', 4, 2) for i in range(3)]
    preview = batch.build(db, sites, 'test')
    assert len(preview['plans']) == 3
    assert Counter(p['source_site_id'] for p in preview['plans']) == {site.id: 1 for site in sites}
    assert all(p['balance_mode'] == 'peer_exchange' for p in preview['plans'])
    runs = reserve(db, preview)
    auto.execute(db, runs[0].id)
    assert runs[0].status == 'waiting' and runs[0].plan['source_released']
    assert any(path == '/site-config/create' for r in remotes.values() for path, _ in r.calls)
    assert all(r.data['settings']['canon'] == sites[i].name for i,r in enumerate([remotes[s.id] for s in sites]))
    finish(db, runs)
    for site in sites:
        assert len(remotes[site.id].data['settings']['domains']) == 4
    before = sum(len(r.calls) for r in remotes.values())
    finish(db, runs)
    assert before == sum(len(r.calls) for r in remotes.values())


def test_one_donor_serves_multiple_recipients_without_stale_revision_or_duplicate_requests(pool):
    db, source, target, remotes, add = pool
    remotes[source.id].data['settings']['domains'] += ['third.test', 'fourth.test']
    source.domain_types = {**source.domain_types, 'third.test': 'newreg', 'fourth.test': 'newreg'}; db.commit()
    others = [target, add('second-recipient.test'), add('third-recipient.test')]
    preview = batch.build(db, others, 'test')
    runs = reserve(db, preview)
    finish(db, runs)
    assert Counter(path for path, _ in remotes[source.id].calls)['/site-config/delete'] == 3
    assert len(remotes[source.id].data['settings']['domains']) == 1
    for site in others:
        assert Counter(path for path, _ in remotes[site.id].calls)['/site-config/create'] == 1
    for run in runs:
        row = db.get(models.AutoReglueConfig, policy_key(run.plan['new_main']))
        assert row.value['last_reglued_at'] == run.plan['reglued_at']
        assert row.value['transfer_not_before']


@pytest.mark.parametrize('change', ['brand', 'geo', 'status', 'personal', 'inactive'])
def test_ineligible_donor_never_supplies_domains(pool, change):
    db, source, target, remotes, add = pool
    if change == 'brand': source.brand = 'Different'
    if change == 'geo': source.cache_geo = 'PL'
    if change == 'status': source.project_status = 'working'
    if change == 'personal': auto.save_config(db, auto.ProjectConfig(scope='personal', enabled=True), source.id)
    if change == 'inactive': source.is_active = False
    db.commit()
    preview = batch.build(db, [target], 'test')
    assert not preview['plans']
    assert all(not r.calls for r in remotes.values())


def test_webdev_project_name_is_globally_protected_even_if_owner_is_hidden(pool):
    db, source, target, remotes, add = pool
    hidden = add('next.test', status='working')
    db.info['cross_allowed_site_ids'] = {source.id, target.id}
    preview = batch.build(db, [target], 'test')
    assert not preview['plans']
    with pytest.raises(ValueError, match='именем проекта Webdev'):
        require_transfer_allowed(db, source, 'https://www.next.test/')


def test_ban_after_preview_prevents_all_mutations(pool):
    db, source, target, remotes, add = pool
    preview = batch.build(db, [target], 'test')
    set_ban(db, source, 'next.test', True, 'user')
    with pytest.raises(ValueError, match='БАН'):
        reserve(db, preview)
    assert all(not r.calls for r in remotes.values())
    assert not db.scalar(select(models.AutoReglueRun.id))


def test_ban_after_extraction_blocks_addition(pool):
    db, source, target, remotes, add = pool
    preview = batch.build(db, [target], 'test')
    runs = reserve(db, preview)
    remotes[source.id].job_ready = False
    auto.execute(db, runs[0].id)
    set_ban(db, source, 'next.test', True, 'user')
    remotes[source.id].job_ready = True
    auto.execute(db, runs[0].id)
    assert runs[0].status == 'partial' and 'БАН' in runs[0].message
    assert not remotes[target.id].calls


def test_cooldown_uses_later_event_and_calendar_month_and_survives_history_clear(pool):
    db, source, target, remotes, add = pool
    record_transfer_cooldown(db, 'next.test', '2026-01-31T08:00:00+00:00', '2026-02-02T09:00:00+00:00'); db.commit()
    source.network_state = {}; db.commit()
    assert require_transfer_allowed(db, source, 'next.test', datetime(2026, 3, 2, 8, 59, tzinfo=timezone.utc)) is None
    require_transfer_allowed(db, source, 'next.test', datetime(2026, 3, 2, 9, tzinfo=timezone.utc))
    record_transfer_cooldown(db, 'month-end.test', '2026-01-31T08:00:00+00:00', '2026-01-31T08:00:00+00:00'); db.commit()
    assert db.get(models.AutoReglueConfig, policy_key('month-end.test')).value['transfer_not_before'] == '2026-02-28T08:00:00+00:00'


def test_batch_receipt_is_idempotent_and_second_incoming_is_rejected(pool):
    db, source, target, remotes, add = pool
    preview = batch.build(db, [target], 'test')
    item = dict(site_id=target.id, request_id=uuid4(), preview_token=preview['plans'][0]['preview_token'])
    first = batch.reserve(db, preview['batch_id'], [item], 'test')
    again = batch.reserve(db, preview['batch_id'], [item], 'test')
    assert again[0][0].id == first[0][0].id and not again[0][1]
    with pytest.raises(network.NetworkConflict, match='уже включена'):
        batch.reserve(db, preview['batch_id'], [{**item, 'request_id': uuid4()}], 'test')


def test_scheduler_preserves_one_allocation_across_portions_and_restarts(pool):
    db, source, target, remotes, add = pool
    remotes[source.id].data['settings']['domains'] += ['third.test', 'fourth.test', 'fifth.test']
    source.domain_types = {**source.domain_types, **{d: 'newreg' for d in ['third.test', 'fourth.test', 'fifth.test']}}; db.commit()
    recipients = [target, add('small-two.test'), add('small-three.test'), add('small-four.test')]
    auto.save_config(db, auto.GlobalConfig(selection_filter={'brand':'Pin-Up','geo':'AZ'}, enabled=True, execution_mode='cross_network', schedule_enabled=True, interval_days=0, max_projects=2))
    queued = []
    first = auto.schedule_tick(db, queued.append)
    assert len(first) == 2
    runs = db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.status.in_(['queued','planned']))).all()
    assert len(runs) == 4 and len({r.plan['batch_id'] for r in runs}) == 1
    for run in runs:
        if run.status == 'queued': auto.execute(db, run.id)
    db.expire_all()
    second = auto.schedule_tick(db, queued.append)
    assert len(second) == 2 and not set(second).intersection(first)
    finish(db, runs)
    assert auto.schedule_tick(db, queued.append) == []
    assert Counter(path for path, _ in remotes[source.id].calls)['/site-config/delete'] == 4


def test_two_available_peers_transfer_one_way_without_reciprocal_return(pool):
    db, source, target, remotes, add = pool
    source.project_status = target.project_status = 'working'; db.commit()
    a, b = add('peer-a.test', 4, 2), add('peer-b.test', 4, 2)
    preview = batch.build(db, [a, b], 'test')
    assert len(preview['plans']) == 1 and len(preview['skipped']) == 1
    finish(db, reserve(db, preview))


def test_two_selected_peers_can_receive_from_a_third_project_without_return(pool):
    db, source, target, remotes, add = pool
    source.project_status = target.project_status = 'working'; db.commit()
    a, b, c = [add(f'peer-{letter}.test', 4, 2) for letter in 'abc']
    preview = batch.build(db, [a, b], 'test')
    assert len(preview['plans']) == 2
    assert {(p['source_site_id'], p['site_id']) for p in preview['plans']} == {(c.id, a.id), (a.id, b.id)}
    finish(db, reserve(db, preview))


@pytest.mark.parametrize('field,value', [('project_status','working'), ('brand','Different'), ('cache_geo','PL')])
def test_changed_pair_after_extraction_cannot_add_to_target(pool, field, value):
    db, source, target, remotes, add = pool
    preview = batch.build(db, [target], 'test')
    run = reserve(db, preview)[0]
    remotes[source.id].job_ready = False
    auto.execute(db, run.id)
    setattr(target, field, value); db.commit()
    remotes[source.id].job_ready = True
    auto.execute(db, run.id)
    assert run.status == 'partial'
    assert not remotes[target.id].calls


def test_manifest_rejects_direct_return_and_quota_tampering(pool):
    db, source, target, remotes, add = pool
    state = network.read_network(db, source)
    target_state = network.read_network(db, target)
    p = cross.make_plan(auto.config(db), target, target_state, source, state, 'next.test')
    with pytest.raises(ValueError, match='Встречный перенос'):
        batch.validate([p, {**p, 'site_id': source.id, 'source_site_id': target.id, 'new_main': 'return.test', 'balance_mode':'peer_exchange'}])
    with pytest.raises(ValueError, match='одно назначение'):
        batch.validate([p, {**p, 'new_main':'another.test'}])
    too_many = [{**p, 'site_id':str(i), 'new_main':f'free-{i}.test'} for i in range(11)]
    batch.validate(too_many)
    with pytest.raises(ValueError, match='Один домен'):
        batch.validate([p,{**p,'site_id':'other-recipient'}])


def test_batch_api_previews_once_and_dispatches_only_after_complete_reservation(pool, monkeypatch):
    from app import auto_reglue_api as api
    from fastapi import HTTPException
    db, source, target, remotes, add = pool
    user = {'username':'test', 'allowed_site_ids':[source.id, target.id]}
    preview = api.preview_batch(api.BatchPreview(site_ids=[source.id,target.id],filter={'brand':'Pin-Up','geo':'AZ'}), user, db)
    assert len(preview['plans']) == 1
    assert all(not r.calls for r in remotes.values())
    sent = []
    monkeypatch.setattr(api, 'dispatch', lambda db, run: sent.append(run.id))
    item = api.StartItem(site_id=target.id, request_id=uuid4(), preview_token=preview['plans'][0]['preview_token'])
    payload = api.BatchStart(batch_id=preview['batch_id'], items=[item],filter={'brand':'Pin-Up','geo':'AZ'})
    result = api.start(payload, user, db)
    assert len(result['results']) == len(sent) == 1
    assert api.start(payload, user, db)['results'][0]['run']['id'] == sent[0]
    assert len(sent) == 1
    restricted = {'username':'test', 'allowed_site_ids':[target.id]}
    with pytest.raises(HTTPException) as error:
        api.start(payload, restricted, db)
    assert error.value.status_code == 404


def test_scheduler_disabled_does_not_dispatch_reserved_group(pool):
    db, source, target, remotes, add = pool
    auto.save_config(db, auto.GlobalConfig(selection_filter={'brand':'Pin-Up','geo':'AZ'}, enabled=True, execution_mode='cross_network', schedule_enabled=True, interval_days=0, max_projects=1))
    queued = []
    auto.schedule_tick(db, queued.append)
    auto.save_config(db, auto.GlobalConfig(enabled=True, execution_mode='cross_network', schedule_enabled=False, interval_days=0, max_projects=1))
    assert auto.schedule_tick(db, queued.append) == []


def test_hidden_target_reservation_blocks_visible_donor(pool):
    db, source, target, remotes, add = pool
    hidden = add('hidden.test')
    run = models.AutoReglueRun(id=str(uuid4()), site_id=hidden.id, initiator='other', status='queued',
        phase='prepared', plan={'source_site_id':source.id})
    db.add(run); db.commit()
    db.info['allowed_site_ids'] = [source.id, target.id]
    assert auto.active_run(db, source.id).id == run.id
    assert not batch.build(db, [target], 'test')['plans']


def test_hidden_membership_and_cooldown_cannot_be_bypassed_by_project_grants(pool):
    db, source, target, remotes, add = pool
    hidden = add('hidden.test')
    hidden.cache_domains = ['next.test']
    hidden.network_state = {'domain_added_at':{'next.test':datetime.now(timezone.utc).isoformat()}}
    db.commit()
    db.info['allowed_site_ids'] = [source.id, target.id]
    with pytest.raises(ValueError, match='ещё в одной сетке'):
        cross.unique_membership(db, 'next.test', {source.id})
    assert require_transfer_allowed(db, source, 'next.test') is None
