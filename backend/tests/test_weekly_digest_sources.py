from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app import models
from app.weekly_digest_sources import collect, _ledgers
from test_project_network import env

START = datetime(2026, 11, 1, 21, tzinfo=timezone.utc)
END = START + timedelta(days=7)
AT = START + timedelta(days=3)


def network_op(db, site, *, at=AT, status='confirmed', action='reglue', payload=None):
    value = models.NetworkOperation(id=str(uuid4()), site_id=site.id, action=action, status=status,
        initiator='test', request_payload=payload or {'journal_before': {'main': 'old.test'}, 'journal_after': {'main': 'main.test'}},
        created_at=at, updated_at=at)
    db.add(value); db.flush()
    return value


def cached(site):
    site.cache_synced_at = AT
    site.site_type = 'general'
    site.network_state = {'canon': 'main.test', 'has_head': True, 'enableCanonical': True,
        'canonicalDefaultMarkup': '<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}">'}
    site.domain_types = {'main.test': 'drop'}


def test_collect_only_confirmed_work_half_open_interval_and_original_observation(env):
    db, site, remote = env; cached(site)
    inside = network_op(db, site, at=START)
    network_op(db, site, status='pending')
    network_op(db, site, at=END)
    network_op(db, site, at=START - timedelta(microseconds=1))
    db.commit(); before = deepcopy(site.network_state)
    result = collect(db, START, END)
    assert len(result['rows']) == 1
    row = result['rows'][0]
    assert [e['id'] for e in row['events']] == [inside.id]
    assert row['state_source'] == 'cache' and row['observed_at'] == AT.isoformat()
    assert row['site_type'] == 'general'
    assert [o['id'] for o in result['operations']] == [inside.id]
    assert remote.calls == [] and site.network_state == before and not db.dirty


def test_collect_keeps_hidden_work_but_excludes_test_and_empty_sites(env):
    db, site, _ = env; cached(site); site.hidden_from_projects = True; site.is_active = False
    network_op(db, site)
    test = models.Site(name='test.test', base_url='https://test.test', publication_endpoint='https://test.test/api', is_test_project=True)
    empty = models.Site(name='empty.test', base_url='https://empty.test', publication_endpoint='https://empty.test/api')
    db.add_all([test, empty]); db.flush(); network_op(db, test); db.commit()
    assert [r['site_id'] for r in collect(db, START, END)['rows']] == [site.id]


def test_missing_cache_never_claims_a_fresh_verified_scheme(env):
    db, site, _ = env; network_op(db, site); db.commit()
    row = collect(db, START, END)['rows'][0]
    assert row['status'] == 'partial' and row['state_source'] == 'cache'
    assert row['observed_at'] is None and row['state_error']


def test_operation_and_old_run_projections_keep_classification_without_private_data(env):
    db, site, _ = env; cached(site)
    run = models.AutoReglueRun(id=str(uuid4()), site_id=site.id, initiator='test', status='completed',
        plan={'balance_mode': 'reserve_pool', 'combination_id': 'scheme', 'original_project': {'secret': 'PRIVATE'}},
        created_at=START-timedelta(days=1), updated_at=START-timedelta(days=1))
    db.add(run); db.flush()
    network_op(db, site, payload={'auto_run_id': run.id, 'journal_before': {'main': 'old.test', 'secret': 'PRIVATE'},
        'journal_after': {'main': 'main.test'}, 'reserve': 'main.test', 'original_project': {'secret': 'PRIVATE'},
        'cross_network_transfer': {'source_site_id': 'donor', 'target_site_id': site.id, 'backup': 'PRIVATE'}})
    db.commit(); result = collect(db, START, END)
    assert result['runs'] == [{'id': run.id, 'site_id': site.id, 'status': 'completed', 'plan': {'balance_mode': 'reserve_pool', 'combination_id': 'scheme'}}]
    assert result['operations'][0]['types'] == {'main.test': 'drop'}
    assert result['operations'][0]['payload']['cross_network_transfer'] == {'source_site_id': 'donor', 'target_site_id': site.id}
    assert 'PRIVATE' not in str(result)


def test_native_receipts_and_menu_baseline_are_collected_without_backups(env):
    db, site, _ = env; cached(site)
    db.add(models.AutoReglueConfig(key='showcase-test:original', value={'site_id': site.id,
        'original_project': {'image': 'PRIVATE'}, 'receipts': [
            {'field': 'shortcode', 'status': 'confirmed', 'at': AT.isoformat(), 'upload': 'PRIVATE'},
            {'field': 'logo', 'status': 'pending', 'at': AT.isoformat()}]}))
    old = [{'title': 'Old', 'slug': '/old/'}]
    db.add(models.PublicationLog(endpoint_url='https://webdev.test/menu', response_status=200, created_at=START-timedelta(seconds=1),
        request_payload={'action': 'menu_sync', 'project_name': site.name, 'type': 'header', 'list': old, 'token': 'PRIVATE'}))
    db.add(models.PublicationLog(endpoint_url='https://webdev.test/menu', response_status=200, created_at=AT,
        request_payload={'action': 'menu_sync', 'project_name': site.name, 'type': 'header', 'list': old + [{'title': 'New', 'slug': '/new/'}]}))
    db.commit(); result = collect(db, START, END)
    row = result['rows'][0]
    assert row['layout_work'] and row['showcase_work'] and row['menu_work']
    assert [e['message'] for e in row['events'] if e['kind'] == 'menu'] == ['Добавлены пункты: New']
    assert 'PRIVATE' not in str(result)


def test_ledger_streams_raw_json_with_nul_backup_and_retains_only_receipts(env, monkeypatch):
    db, site, _ = env
    key = 'showcase-nul:original'
    receipt = {'field': 'shortcode', 'status': 'confirmed', 'at': AT.isoformat()}
    db.add(models.AutoReglueConfig(key=key, value={'site_id': site.id,
        'original_project': {'files': {'.DS_Store': 'PRIVATE\x00binary'}},
        'receipts': [{**receipt, 'upload': 'PRIVATE\x00upload'}]}))
    db.commit()
    site_id = site.id
    statements = []
    original_execute = db.execute
    def execute(statement, *args, **kwargs):
        statements.append(statement)
        return original_execute(statement, *args, **kwargs)
    monkeypatch.setattr(db, 'execute', execute)
    ledgers = _ledgers(db)
    assert len(ledgers[site_id]) == 1
    ledger = ledgers[site_id][0]
    assert ledger.key == key
    assert ledger.value == {'site_id': site_id, 'receipts': [receipt]}
    assert len(statements) == 1
    assert '->' not in str(statements[0].compile(dialect=postgresql.dialect()))
    assert statements[0].get_execution_options()['yield_per'] == 1
    assert not any(isinstance(obj, models.AutoReglueConfig) for obj in db.identity_map.values())
    stored = original_execute(models.AutoReglueConfig.__table__.select().where(
        models.AutoReglueConfig.key == key)).mappings().one()
    assert stored['value']['original_project']['files']['.DS_Store'] == 'PRIVATE\x00binary'


def test_collector_restores_caller_info_and_ignores_weekly_report_as_work(env):
    db, site, _ = env; cached(site)
    db.add(models.BackgroundJob(kind='maintenance_report', status='completed',
        payload={'task_type': 'project_state_report', 'name': 'Weekly'},
        result={'entries': [{'site_id': site.id, 'status': 'completed', 'confirmed_at': AT.isoformat()}]}))
    db.commit()
    sentinel = [object()]
    db.info['state_report_sources'] = sentinel
    result = collect(db, START, END)
    assert result['rows'] == [] and db.info['state_report_sources'] is sentinel
    assert 'state_report_ledgers' not in db.info and 'state_report_menu_logs' not in db.info
