from uuid import uuid4
import pytest
from app import models, pilot_donors, cross_reglue_batch as batch, mass_action_scope as scope
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, reserve, finish


def grant(db, source, target):
    source.reglue_participation = False
    job = models.BackgroundJob(id=str(uuid4()), kind='auto_pilot_preview', status='queued',
        payload={'allowed': None, 'site_ids': [target.id, source.id]}, result={})
    db.add(job)
    db.add(models.AutoReglueConfig(key=pilot_donors.key(job.id), value={
        'sites': {source.id: {'approved': True, 'actor': 'test', 'at': '2026-11-06T17:00:00Z'}}}))
    db.commit()
    db.info.update(pilot_job_id=job.id, auto_pilot_preview=True, prefer_own_domains=True)
    scope.constrain(db, {'brand': target.brand, 'geo': target.cache_geo}, targets=[target])
    return job


def test_donor_only_grant_transfers_free_domain_without_promoting_donor(pool):
    db, source, target, remotes, _ = pool
    job = grant(db, source, target)
    before = remotes[source.id].data['settings']['canon']
    preview = batch.build(db, [target], 'test')
    assert len(preview['plans']) == 1
    plan = preview['plans'][0]
    assert plan['source_site_id'] == source.id and plan['site_id'] == target.id
    assert plan['donor_authorization']['plan_id'] == job.id
    assert not source.reglue_participation and all(not r.calls for r in remotes.values())
    finish(db, reserve(db, preview))
    assert remotes[source.id].data['settings']['canon'] == before
    assert remotes[target.id].data['settings']['canon'] == plan['new_main']
    assert not source.reglue_participation


def test_donor_grant_does_not_leak_to_another_plan(pool):
    db, source, target, remotes, _ = pool
    grant(db, source, target)
    db.info['pilot_job_id'] = str(uuid4())
    assert batch.build(db, [target], 'test')['plans'] == []
    assert all(not r.calls for r in remotes.values())


def test_donor_grant_does_not_bypass_geo_or_project_permissions(pool):
    db, source, target, remotes, _ = pool
    job = grant(db, source, target)
    job.payload = {**job.payload, 'allowed': [target.id]}; db.commit()
    assert batch.build(db, [target], 'test')['plans'] == []
    job.payload = {**job.payload, 'allowed': None}; source.cache_geo = 'PL'; db.commit()
    assert batch.build(db, [target], 'test')['plans'] == []
    assert all(not r.calls for r in remotes.values())


def test_revoked_donor_permission_stops_before_network_writes(pool):
    db, source, target, remotes, _ = pool
    job = grant(db, source, target)
    preview = batch.build(db, [target], 'test')
    run = reserve(db, preview)[0]
    db.get(models.AutoReglueConfig, pilot_donors.key(job.id)).value = {'sites': {}}; db.commit()
    with pytest.raises(ValueError, match='Участвует'):
        scope.require_run_scope(db, run)
    assert all(not r.calls for r in remotes.values())


def test_replanning_keeps_donor_out_of_recipient_groups(pool):
    from app.mass_reglue_launch import initial_job
    db, source, target, _, _ = pool
    job = grant(db, source, target)
    fresh = initial_job(db, job.id, [source.id,target.id], 'test', preview_only=True)
    assert fresh.result['items'][source.id]['status'] == 'skipped'
    assert 'только как донор' in fresh.result['items'][source.id]['reason']
    assert all(source.id not in group['site_ids'] for group in fresh.result['groups'])
