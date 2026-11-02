from datetime import datetime, timezone
from app import models, reglue_history as history, network_state
from test_project_network import env


def test_snapshot_backfill_detects_main_changes_not_membership(env):
    db, site, _ = env
    site.last_reglue_at = datetime(2026, 9, 23, tzinfo=timezone.utc)
    site.network_snapshot_history = [
        {'canon': 'old.test', 'observed_at': '2026-10-01T10:00:00Z'},
        {'canon': 'main.test', 'observed_at': '2026-10-21T14:10:04Z'},
        {'canon': 'main.test', 'observed_at': '2026-10-22T10:00:00Z', 'domains': ['new.test']},
    ]
    db.commit()
    history.backfill(db)
    assert history.utc(site.last_reglue_at) == datetime(2026, 10, 21, 14, 10, 4, tzinfo=timezone.utc)
    assert history.backfill(db) == 0


def test_initial_snapshot_and_addition_dates_are_not_reglue(env):
    db, site, _ = env
    site.network_snapshot_history = [{'canon': 'main.test', 'observed_at': '2026-10-21T10:00:00Z'}]
    site.network_state = {'domain_added_at': {'main.test': '2026-10-21T10:00:00Z'}}
    db.commit(); history.backfill(db)
    assert site.last_reglue_at is None


def test_newer_receipt_wins_over_old_snapshot(env):
    db, site, _ = env
    site.last_reglue_at = datetime(2026, 10, 23, 8, tzinfo=timezone.utc)
    site.network_snapshot_history = [
        {'canon': 'old.test', 'observed_at': '2026-10-01T10:00:00Z'},
        {'canon': 'main.test', 'observed_at': '2026-10-21T14:10:00Z'},
    ]
    db.commit(); history.backfill(db)
    assert history.utc(site.last_reglue_at) == datetime(2026, 10, 23, 8, tzinfo=timezone.utc)


def test_observed_webdev_change_is_recorded_but_initial_and_partial_are_not(env):
    db, site, remote = env
    network_state.observe_network(site, remote.project())
    assert site.last_reglue_at is None
    remote.data['settings']['canon'] = 'next.test'
    network_state.observe_network(site, remote.project())
    assert site.last_reglue_at is not None
    saved = site.last_reglue_at
    site.cache_canon = 'next.test'
    network_state.observe_network(site, remote.project())
    network_state.observe_network(site, {'settings': {'domains': ['next.test', 'new.test']}})
    assert site.last_reglue_at == saved
    site.cache_canon = None; site.last_reglue_at = None
    network_state.observe_network(site, remote.project())
    assert site.last_reglue_at is None
