from uuid import uuid4
from sqlalchemy import select
import pytest
from app import models, auto_reglue as auto, move_plus2 as plus, domain_redistribution as move
from app.mass_action_scope import MassActionFilter
from test_cross_reglue_batch import pool
from test_cross_reglue import setup
from test_project_network import env


def init(pool):
    db, source, target, remotes, add = pool
    for site in (source, target):
        site.site_type = 'monobrand'
        site.hidden_from_projects = False
    def roots(site, count):
        names = [f'r{i}-{site.id[:4]}.test' for i in range(count)]
        remotes[site.id].data['settings']['domains'] = [remotes[site.id].data['settings']['canon'], *names]
        site.domain_types = {n: 'newreg' for n in names}
        db.commit()
    roots(source, 10)
    other = add('other-big.test', 1, 0)
    small = add('other-small.test', 1, 0)
    for site in (other, small):
        site.site_type = 'monobrand'; site.hidden_from_projects = False
    roots(other, 8)
    db.commit()
    filters = MassActionFilter(brand=source.brand, geo='AZ')
    return db, [source, other, target, small], remotes, filters, roots


def test_one_click_rotates_donors_and_small_recipients_without_enabling_schedule(pool):
    db, sites, remotes, filters, roots = init(pool)
    original = auto.config(db).model_dump()
    ids = [s.id for s in sites]
    first, fresh = plus.prepare(db, uuid4(), filters, ids, 'test')
    assert fresh and first.plan['source_site_id'] == sites[0].id
    same, fresh = plus.prepare(db, first.id, filters, ids, 'test')
    assert same.id == first.id and not fresh
    auto.execute(db, first.id)
    assert first.status == 'completed', first.message
    second, _ = plus.prepare(db, uuid4(), filters, ids, 'test')
    assert second.plan['source_site_id'] == sites[1].id
    assert second.site_id != first.site_id
    auto.execute(db, second.id)
    assert second.status == 'completed', second.message
    assert all(d['domain_type'] == 'newreg' for r in (first, second) for d in r.plan['domains'])
    assert auto.config(db).model_dump() == original
    inverse, _ = move.prepare_rollback(db, first, 'test')
    auto.execute(db, inverse.id)
    assert inverse.status == 'completed', inverse.message


def test_two_big_one_small_uses_second_donor_on_next_click(pool):
    db, sites, remotes, filters, roots = init(pool)
    ids = [s.id for s in sites[:3]]
    first, _ = plus.prepare(db, uuid4(), filters, ids, 'test')
    auto.execute(db, first.id)
    second, _ = plus.prepare(db, uuid4(), filters, ids, 'test')
    assert second.plan['source_site_id'] == sites[1].id
    assert second.site_id == first.site_id


def test_scope_tampering_and_double_click_are_blocked(pool):
    db, sites, remotes, filters, roots = init(pool)
    with pytest.raises(ValueError):
        plus.prepare(db, uuid4(), MassActionFilter(brand='Other', geo='AZ'), [s.id for s in sites], 'test')
    run, _ = plus.prepare(db, uuid4(), filters, [s.id for s in sites], 'test')
    with pytest.raises(Exception, match='Дождитесь'):
        plus.prepare(db, uuid4(), filters, [s.id for s in sites], 'test')
    run.plan = {**run.plan, 'domains': [{'domain': 'bad.test', 'domain_type': 'newreg'}]}
    db.commit()
    auto.execute(db, run.id)
    assert run.status == 'failed' and all(not r.calls for r in remotes.values())


def test_free_newregs_do_not_have_membership_cooldown(pool):
    from datetime import datetime, timezone
    db, sites, remotes, filters, roots = init(pool)
    source = sites[0]
    source.network_state = {'domain_added_at': {d: datetime.now(timezone.utc).isoformat() for d in source.domain_types}}
    db.commit()
    run, _ = plus.prepare(db, uuid4(), filters, [s.id for s in sites], 'test')
    assert len(run.plan['domains']) == 2


def test_move_one_and_two_share_rotation_and_rollback_support(pool):
    db, sites, remotes, filters, roots = init(pool)
    ids = [s.id for s in sites]
    first, _ = plus.prepare(db, uuid4(), filters, ids, 'test', count=1)
    assert len(first.plan['domains']) == 1
    auto.execute(db, first.id)
    assert first.status == 'completed', first.message
    second, _ = plus.prepare(db, uuid4(), filters, ids, 'test', count=2)
    assert second.plan['source_site_id'] != first.plan['source_site_id']
    assert len(second.plan['domains']) == 2
    inverse, _ = move.prepare_rollback(db, first, 'test')
    # The other queued run uses the other donor/recipient, so it does not block rollback.
    auto.execute(db, inverse.id)
    assert inverse.status == 'completed', inverse.message


def test_size_bands_switch_only_when_a_network_reaches_twenty():
    from types import SimpleNamespace
    sites = [SimpleNamespace(id=str(i)) for i in range(8)]
    states = {s.id: {'domains': list(range(size))} for s, size in zip(sites, [1, 5, 6, 9, 10, 11, 13, 19])}
    bands, expanded = plus.size_bands(sites, states)
    assert not expanded and list(bands.values()) == [0, 0, 1, 1, 1, 2, 2, 2]
    states[sites[-1].id]['domains'].append('twentieth')
    bands, expanded = plus.size_bands(sites, states)
    assert expanded and list(bands.values()) == [0, 0, 0, 0, 1, 1, 1, 2]


def test_button_endpoint_requires_scope_preserves_receipt_and_dispatches_once(pool, monkeypatch):
    from pydantic import ValidationError
    from app import auto_reglue_api as api
    db, sites, remotes, filters, roots = init(pool)
    user = {'id': 'user', 'username': 'test', 'allowed_site_ids': [s.id for s in sites]}
    calls = []
    monkeypatch.setattr(api, 'dispatch', lambda db, run: calls.append(run.id))
    with pytest.raises(ValidationError):
        api.MovePlus2Request.model_validate({})
    payload = api.MovePlus2Request(request_id=uuid4(), filter=filters, site_ids=[s.id for s in sites])
    response = api.move_plus2(payload, user, db)
    assert response['id'] == str(payload.request_id)
    assert api.move_plus2(payload, user, db)['id'] == response['id']
    assert len(calls)==2 and calls[0]==str(payload.request_id)
    assert len(response['runs'])==2 and set(calls)=={r['id'] for r in response['runs']}


def test_drop_fallback_does_not_require_a_surplus_of_newregs(pool):
    db, sites, remotes, filters, roots = init(pool)
    source, _, target, _ = sites
    names = remotes[source.id].data['settings']['domains'][1:]
    source.domain_types = {d:'drop' for d in names}
    target.domain_types = {target.cache_canon:'newreg'}
    db.commit()
    run, _ = plus.prepare(db, uuid4(), filters, [source.id,target.id], 'test', count=2)
    assert len(run.plan['domains']) == 1
    assert run.plan['domains'][0]['domain_type'] == 'drop'
    assert run.plan['source_site_id'] == source.id
