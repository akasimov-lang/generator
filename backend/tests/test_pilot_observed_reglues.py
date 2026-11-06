from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from app import models, auto_pilot, mass_reglue_launch as launch
from app import pilot_observed_reglues as observed
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_auto_pilot import preview, USER


def receipt(db, site_id, old, new='manual.test', **kwargs):
    at = datetime.now(timezone.utc) + timedelta(seconds=1)
    payload = {'source_domain': old, 'reserve': new, 'confirmed_at': at.isoformat(),
               'journal_before': {'main': old, 'fake_path': '/before/'},
               'journal_after': {'main': new, 'fake_path': '/after/'}, **kwargs}
    op = models.NetworkOperation(id=str(uuid4()), site_id=site_id, action='reglue',
                                 status='confirmed', initiator='another-user', request_payload=payload)
    db.add(op); db.commit()
    return op


def ready(db):
    job = preview(db)
    row = next(r for r in auto_pilot.view(db, job)['items'] if r['status'] == 'ready')
    return job, row


def test_all_plans_recognize_same_confirmed_move_without_writes_or_dispatch(pool):
    db, _, _, remotes, _ = pool
    first, row = ready(db)
    second, _ = ready(db)
    op = receipt(db, row['site_id'], row['old_main'])
    originals = [deepcopy(j.result) for j in (first, second)]
    for job in (first, second):
        view = auto_pilot.view(db, job)
        actual = next(r for r in view['items'] if r['site_id'] == row['site_id'])
        assert actual['status'] == 'completed' and actual['progress'] == 100
        assert actual['completed_elsewhere']['operation_id'] == op.id
        assert actual['completed_elsewhere']['before']['main'] == row['old_main']
        assert actual['completed_elsewhere']['after'] == {'main': 'manual.test', 'fake_path': '/after/'}
        assert actual['new_main'] == row['new_main']  # The reviewed plan is still intact.
        assert view['counts']['completed'] == 1 and view['ready'] == 0
        assert not view['launch_enabled']
    assert [first.result, second.result] == originals
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not remote.calls for remote in remotes.values())
    tasks = auto_pilot.tasks(db, USER)['items']
    assert all(t['counts']['completed'] == 1 for t in tasks if t['id'] in {first.id, second.id})


def test_open_plan_reads_new_receipt_on_next_request(pool):
    db, *_ = pool
    job, row = ready(db)
    assert not auto_pilot.view(db, job)['counts']['completed']
    receipt(db, row['site_id'], row['old_main'])
    assert auto_pilot.view(db, job)['counts']['completed'] == 1


def test_old_receipts_and_unconfirmed_cache_changes_do_not_complete_plan(pool):
    db, *_ = pool
    job, row = ready(db)
    receipt(db, row['site_id'], row['old_main'], confirmed_at=(job.created_at-timedelta(days=1)).isoformat())
    site = db.get(models.Site, row['site_id'])
    site.cache_canon = 'other.test'
    site.network_state = {**(site.network_state or {}), 'canon': 'other.test'}
    db.commit()
    assert not observed.evidence(db, job)


def test_other_baseline_and_donor_receipts_do_not_complete_recipient(pool):
    db, source, target, *_ = pool
    job, row = ready(db)
    receipt(db, row['site_id'], 'unrelated.test')
    other = target if row['site_id'] != target.id else source
    receipt(db, other.id, row['old_main'])
    assert row['site_id'] not in observed.evidence(db, job)


def test_pending_reglue_is_not_confirmation(pool):
    db, *_ = pool
    job, row = ready(db)
    op = receipt(db, row['site_id'], row['old_main'])
    op.status = 'unknown'; db.commit()
    assert not observed.evidence(db, job)


def test_receipt_for_own_run_is_not_external(pool):
    db, *_ = pool
    job, row = ready(db)
    result = deepcopy(job.result)
    result['items'][row['site_id']]['run_id'] = str(uuid4())
    job.result = result; db.commit()
    receipt(db, row['site_id'], row['old_main'], auto_run_id=result['items'][row['site_id']]['run_id'])
    assert not observed.evidence(db, job)


def test_start_archives_fulfilled_plan_and_never_dispatches_it(pool):
    db, _, _, remotes, _ = pool
    job, row = ready(db)
    receipt(db, row['site_id'], row['old_main'])
    with pytest.raises(ValueError, match='нет проектов'):
        auto_pilot.start(db, job.id, USER)
    saved = job.result['items'][row['site_id']]
    assert saved['status'] == 'completed'
    assert saved['completed_elsewhere_plan']['new_main'] == row['new_main']
    assert not any(g.get('plans') for g in job.result['groups'])
    assert not observed.retire(db, job, deepcopy(job.result))
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not remote.calls for remote in remotes.values())
    assert auto_pilot.view(db, job)['counts']['completed'] == 1


def test_execution_rechecks_confirmation_before_creating_run(pool):
    db, _, _, remotes, _ = pool
    job, row = ready(db)
    auto_pilot.start(db, job.id, USER)
    receipt(db, row['site_id'], row['old_main'])
    launch.execute_step(db, job.id, lambda _: pytest.fail('Already fulfilled move must not run'))
    assert job.result['items'][row['site_id']]['completed_elsewhere']
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not remote.calls for remote in remotes.values())
