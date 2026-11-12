from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, maintenance_reports, sitemap_row_recheck as recheck, network_sitemap, background_jobs
from test_project_network import env

USER = {'username': 'anton', 'allowed_site_ids': None}


def setup(env, monkeypatch):
    db, site, remote = env
    site.project_status = 'mass_actions'; db.commit()
    remote.data.update(data={'pages': [{'slug': '/'}, {'slug': '/bonus/'}]})
    remote.data['sitemap'] = network_sitemap.document(network_sitemap.expected(remote.data)[1])
    monkeypatch.setattr(recheck, 'Remote', lambda *args: nullcontext(remote))
    monkeypatch.setattr(recheck.sitemap_maintenance, 'public_snapshot', lambda main, urls: {'status': 200, 'valid': True, 'count': len(urls)})
    row = {'site_id': site.id, 'project': site.name, 'main': 'old.test', 'status': 'partial', 'error': 'Old failure',
           'sitemap': {'before': {'template': 'BACKUP', 'public': {'count': 1}}, 'action': 'saved_unconfirmed'}}
    report = maintenance_reports.upsert(db, str(uuid4()), 'Sitemap', 'anton', [site.id], [row], status='partial')
    report.payload = {**report.payload, 'task_type': 'sitemap_repair'}; db.commit()
    return db, site, remote, report


def start(db, site, report, request=None):
    recheck.prepare(db, report.id, site.id, request or str(uuid4()), USER)
    return db.get(models.BackgroundJob, report.result['entries'][0]['recheck']['id'])


def test_refresh_uses_new_main_and_pages_and_keeps_backup_without_remote_writes(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    remote.data['settings']['canon'] = 'new.test'
    remote.data['data']['pages'].append({'slug': '/games/'})
    job = start(db, site, report)
    assert report.status == 'running'
    background_jobs.run_job(db, job.id)
    row = report.result['entries'][0]
    assert row['status'] == 'completed' and row['main'] == 'new.test' and row['error'] is None
    assert row['sitemap']['internal_pages'] == 2 and row['sitemap']['expected_count'] == 3
    assert row['sitemap']['before']['template'] == 'BACKUP'
    assert row['recheck_history'][0]['error'] == 'Old failure'
    assert report.status == 'completed' and not remote.calls
    assert {j.kind for j in db.scalars(select(models.BackgroundJob))} == {'maintenance_report', recheck.KIND}


def test_duplicate_clicks_and_retries_reuse_same_job(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    request = str(uuid4()); job = start(db, site, report, request)
    assert start(db, site, report, request).id == job.id
    assert start(db, site, report).id == job.id
    background_jobs.run_job(db, job.id)
    assert start(db, site, report, request).id == job.id
    assert len(report.result['entries'][0]['recheck_history']) == 1
    assert background_jobs.run_job(db, job.id)['status'] == 'skipped'


def test_refresh_failure_replaces_obsolete_error_and_stays_retryable(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    monkeypatch.setattr(recheck.sitemap_maintenance, 'public_snapshot', lambda *args: {'status': 301, 'valid': False, 'location': 'https://www.main.test/sitemap.xml'})
    job = start(db, site, report); background_jobs.run_job(db, job.id)
    row = report.result['entries'][0]
    assert row['status'] == 'partial' and 'www.main.test' in row['error'] and report.status == 'partial'
    assert start(db, site, report).id != job.id
    assert not remote.calls


def test_scope_change_during_public_check_cannot_confirm_old_main(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    def moved(*args):
        remote.data['settings']['canon'] = 'moved.test'
        return {'valid': True, 'status': 200}
    monkeypatch.setattr(recheck.sitemap_maintenance, 'public_snapshot', moved)
    job = start(db, site, report); background_jobs.run_job(db, job.id)
    assert report.result['entries'][0]['status'] == 'failed'
    assert 'изменились' in report.result['entries'][0]['error']


def test_denied_report_and_wrong_row_cannot_enqueue(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    with pytest.raises(ValueError, match='Отчёт не найден'):
        recheck.prepare(db, report.id, site.id, uuid4(), {'username': 'other', 'allowed_site_ids': None})
    with pytest.raises(ValueError, match='доступную группу'):
        recheck.prepare(db, report.id, uuid4(), uuid4(), USER)
    assert not db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == recheck.KIND)).all()


def test_removed_mass_action_site_is_rejected(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    site.project_status = 'vitalina'; db.commit()
    with pytest.raises(ValueError, match='массовых действий'):
        start(db, site, report)


def test_other_report_type_is_rejected(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    report.payload = {**report.payload, 'task_type': 'showcase_inventory'}; db.commit()
    with pytest.raises(ValueError, match='sitemap'):
        start(db, site, report)


def test_other_rows_and_last_moment_results_are_preserved(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    job = start(db, site, report)
    other = {'site_id': str(uuid4()), 'status': 'completed', 'project': 'other.test', 'new': True}
    report.result = {**report.result, 'entries': [report.result['entries'][0], other]}; db.commit()
    background_jobs.run_job(db, job.id)
    assert report.result['entries'][1] == other


def test_network_error_cannot_be_success_or_stale_after_evidence(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    def failed(*args): raise OSError('DNS resolution failed')
    monkeypatch.setattr(recheck.sitemap_maintenance, 'public_snapshot', failed)
    job = start(db, site, report); background_jobs.run_job(db, job.id)
    row = report.result['entries'][0]
    assert row['status'] == 'failed' and 'DNS' in row['error'] and row['sitemap']['after'] == {}


def test_lost_worker_readonly_job_recovers_but_active_worker_is_untouched(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    job = start(db, site, report)
    job.status = 'running'; job.started_at = datetime.now(timezone.utc)-timedelta(minutes=11); db.commit()
    recheck.recover(db, {job.id}); assert job.status == 'running'
    recheck.recover(db, None); assert job.status == 'running'
    recheck.recover(db, set()); assert job.status == 'queued'
    background_jobs.run_job(db, job.id)
    assert report.result['entries'][0]['status'] == 'completed'


def test_terminal_worker_failure_unsticks_row(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    job = start(db, site, report); job.status = 'failed'; db.commit()
    recheck.recover(db, set())
    assert report.result['entries'][0]['status'] == 'failed'
    assert job.result['row_reconciled']


def test_compact_api_preserves_recheck_receipt_and_omits_backup(env, monkeypatch):
    db, site, remote, report = setup(env, monkeypatch)
    job = start(db, site, report)
    view = maintenance_reports.view(report, db)
    assert view['entries'][0]['recheck']['id'] == job.id
    assert 'BACKUP' not in str(view)
