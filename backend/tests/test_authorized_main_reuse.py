from copy import deepcopy
from uuid import uuid4

import pytest
from app import models, auto_reglue as auto, cross_reglue as cross, cross_reglue_batch as batch
from app.reglue_reserves import require_unused
from app.mass_main_targets import require_target
from app.domain_transfer_policy import set_ban
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, reserve, finish


def approved_plan(db, site, remote):
    remote.data['settings']['domains'].append('former.test')
    site.domain_types = {'former.test': 'drop'}
    site.main_domain_history = ['former.test']
    db.commit()
    state = cross.network.read_network(db, site)
    plan = cross.make_plan(auto.config(db), site, state, site, state, 'former.test', db=db)
    report_id = str(uuid4())
    plan.update(local_target=True, main_target_kind='drop', domain_type='drop',
        requires_newreg=False, maintenance_report_id=report_id,
        reuse_main_authorization={'report_id': report_id, 'site_id': site.id,
            'domain': 'former.test', 'actor': 'test', 'authorized_at': '2026-11-06T10:49:33+00:00',
            'scope': 'own_drop_only'})
    plan['preview_token'] = auto.digest({k: v for k, v in plan.items() if k != 'preview_token'})
    return plan, state


def test_approved_own_drop_reserves_executes_and_does_not_repeat(pool):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    batch_id = str(uuid4())
    plan['batch_id'] = batch_id
    db.add(models.AutoReglueConfig(key=batch.key(batch_id), value={
        'plans': [plan], 'run_ids': {}, 'skipped': [], 'created_by': 'test'}))
    db.commit()
    runs = reserve(db, {'batch_id': batch_id, 'plans': [plan]})
    finish(db, runs)
    assert remotes[target.id].data['settings']['canon'] == 'former.test'
    calls = deepcopy(remotes[target.id].calls)
    finish(db, runs)
    assert remotes[target.id].calls == calls
    assert not remotes[source.id].calls


def test_unapproved_former_main_stays_excluded(pool):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    plan.pop('reuse_main_authorization')
    with pytest.raises(ValueError, match='Main'):
        require_unused(target, state, 'former.test', plan=plan)


@pytest.mark.parametrize('field,value', [('domain', 'other.test'), ('site_id', 'other'),
    ('report_id', 'other'), ('scope', 'stock'), ('actor', '')])
def test_reuse_approval_is_bound_to_exact_plan_and_target(pool, field, value):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    plan['reuse_main_authorization'][field] = value
    with pytest.raises(ValueError, match='Main'):
        require_unused(target, state, 'former.test', plan=plan)


def test_reuse_cannot_switch_to_current_main(pool):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    state['canon'] = 'former.test'
    with pytest.raises(ValueError, match='Main'):
        require_target(db, target, state, plan)


def test_reuse_cannot_bypass_ban(pool):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    set_ban(db, target, 'former.test', True, 'test')
    with pytest.raises(ValueError, match='БАН'):
        require_target(db, target, state, plan)


def test_reuse_cannot_bypass_amp(pool):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    state['amp_domains'] = ['former.test']
    with pytest.raises(ValueError, match='AMP'):
        require_target(db, target, state, plan)


def test_reuse_does_not_apply_to_newregs(pool):
    db, source, target, remotes, add = pool
    plan, state = approved_plan(db, target, remotes[target.id])
    target.domain_types = {'former.test': 'newreg'}
    plan['main_target_kind'] = 'newreg'
    with pytest.raises(ValueError, match='Main'):
        require_target(db, target, state, plan)
