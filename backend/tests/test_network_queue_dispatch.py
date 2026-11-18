from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import models, network_queue_dispatch as dispatch
from app.background_jobs import dispatch_pending, run_job
from test_project_network import env


def queued(db, site_id, offset=0, kind='fake_main_queue'):
    job = models.BackgroundJob(kind=kind, payload={'site_id': site_id},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=offset))
    db.add(job)
    db.commit()
    return job


def test_thirty_projects_dispatch_together_without_one_sites_tail_filling_slots(env):
    db, site, _ = env
    first = queued(db, site.id)
    tails = [queued(db, site.id, n + 1, 'network_edit_queue') for n in range(40)]
    others = [queued(db, f'other-{n}') for n in range(29)]
    sent = []
    assert dispatch_pending(db, lambda job_id, queue: sent.append((job_id, queue))) == {'dispatched': 30}
    assert {job_id for job_id, _ in sent} == {first.id, *(job.id for job in others)}
    assert {queue for _, queue in sent} == {'network_changes'}
    assert all(job.dispatched_at is None for job in tails)


def test_immediate_dispatch_advances_to_next_kind_only_after_completion(env):
    db, site, _ = env
    first = queued(db, site.id)
    second = queued(db, site.id, 1, 'network_edit_queue')
    sent = []
    assert dispatch.dispatch_ready(db, sent.append, site.id) == 1
    assert sent == [first.id]
    assert dispatch.dispatch_ready(db, sent.append, site.id) == 0
    first.status = 'completed'; db.commit()
    assert dispatch.dispatch_ready(db, sent.append, site.id) == 1
    assert sent == [first.id, second.id]


def test_queue_sequence_wins_over_clock_skew(env):
    db, site, _ = env
    first = queued(db, site.id, 10)
    second = queued(db, site.id, 0)
    first.payload = {**first.payload, 'sequence': 1}
    second.payload = {**second.payload, 'sequence': 2}
    db.commit()
    sent = []
    assert dispatch.dispatch_ready(db, sent.append, site.id) == 1
    assert sent == [first.id]
    first.status = 'completed'; db.commit()
    assert dispatch.dispatch_ready(db, sent.append, site.id) == 1
    assert sent == [first.id, second.id]


def test_broker_failure_retains_job_for_periodic_recovery(env):
    db, site, _ = env
    job = queued(db, site.id)
    def offline(_):
        raise ConnectionError('offline')
    assert dispatch.dispatch_ready(db, offline, site.id) == 0
    assert job.status == 'queued' and job.dispatched_at is None
    sent = []
    assert dispatch_pending(db, lambda *args: sent.append(args)) == {'dispatched': 1}
    assert sent == [(job.id, 'network_changes')]


def test_old_broker_delivery_cannot_overtake_other_kind_on_same_project(env, monkeypatch):
    db, site, _ = env
    first = queued(db, site.id)
    second = queued(db, site.id, 1, 'network_edit_queue')
    second.dispatched_at = datetime.now(timezone.utc); db.commit()
    monkeypatch.setattr('app.network_edit_queue.execute_step', lambda *_: (_ for _ in ()).throw(AssertionError('Overtaking')))
    assert run_job(db, second.id) == {'status': 'waiting'}
    assert second.dispatched_at is None and first.status == 'queued'


def test_worker_kicks_next_after_releasing_session(env, monkeypatch):
    from app.worker import background_operation_job
    db, site, _ = env
    job = queued(db, site.id)
    closed = []
    @contextmanager
    def session():
        try:
            yield db
        finally:
            closed.append(True)
    def complete(db, job_id):
        db.get(models.BackgroundJob, job_id).status = 'completed'
        db.commit()
        return {'status': 'completed'}
    kicked = []
    def kick(site_id):
        assert closed
        kicked.append(site_id)
    monkeypatch.setattr('app.worker.SessionLocal', session)
    monkeypatch.setattr('app.background_jobs.run_job', complete)
    monkeypatch.setattr(dispatch, 'kick', kick)
    assert background_operation_job.run(job.id) == {'status': 'completed'}
    assert kicked == [site.id]


def test_worker_waiting_for_remote_confirmation_does_not_busy_loop(env, monkeypatch):
    from app.worker import background_operation_job
    db, site, _ = env
    job = queued(db, site.id)
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr('app.worker.SessionLocal', session)
    monkeypatch.setattr('app.background_jobs.run_job', lambda *_: {'status': 'waiting'})
    monkeypatch.setattr(dispatch, 'kick', lambda *_: (_ for _ in ()).throw(AssertionError('Busy loop')))
    assert background_operation_job.run(job.id) == {'status': 'waiting'}


def test_thread_worker_has_connection_capacity_and_does_not_dispose_shared_pool():
    import yaml
    config = yaml.safe_load((Path(__file__).resolve().parents[2] / 'docker-compose.yml').read_text())
    worker = config['services']['network_worker']
    assert '--pool=threads --concurrency=30' in worker['command']
    settings = worker['environment']
    assert settings['WORKER_SHARED_DB_POOL'] == '1'
    assert int(settings['DB_POOL_SIZE']) + int(settings['DB_MAX_OVERFLOW']) >= 60
