from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models, gsc_fibery as feature
from app.db import Base
from app.fibery_client import FiberyConflict, FiberyError

AT = datetime.now(timezone.utc)


@pytest.fixture
def setup():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='project.test', cache_canon='main.test', base_url='https://server.test',
                           publication_endpoint='/', fibery_name='#1715_Project')
        db.add(site); db.flush()
        job = feature.enqueue(db, site, 'account@example.test verification=value', 'anton')
        db.commit()
        yield db, site, job
    engine.dispose()


class Client:
    def __init__(self): self.calls = []
    def ensure_task(self, **values):
        self.calls.append(values)
        return {'task_id': values['task_id'], 'public_id': '123', 'title': values['title'],
                'project_number': values['project_number'], 'description_verified': True,
                'url': 'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Tasks/123'}


def test_snapshot_survives_domain_change_and_completed_receipt_is_visible(setup):
    from app.fibery_tasks import feed
    db, site, job = setup
    site.cache_canon = 'new.test'; site.fibery_name = '#999_other'; db.commit()
    client = Client()
    assert feature.execute(db, job.id, client=client)['status'] == 'completed'
    assert client.calls[0]['project_number'] == '1715'
    assert client.calls[0]['title'] == 'main.test - Добавлен в GSC'
    assert 'account@example.test verification=value' in client.calls[0]['description']
    assert feature.execute(db, job.id, client=client)['status'] == 'waiting_or_claimed'
    assert len(client.calls) == 1
    result = feed(db, {'username':'anton', 'allowed_site_ids':None}, site_id=site.id)
    assert any(row['url'].endswith('/123') for row in result['items'])


def test_timeout_retries_same_task_and_keeps_saved_value(setup):
    db, site, job = setup
    class Timeout(Client):
        def ensure_task(self, **values):
            self.calls.append(values)
            raise FiberyError('Ответ не получен.')
    failed = Timeout()
    assert feature.execute(db, job.id, client=failed, now=AT)['status'] == 'queued'
    client = Client()
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(seconds=59))['status'] == 'waiting_or_claimed'
    assert not client.calls
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(seconds=61))['status'] == 'completed'
    assert failed.calls == client.calls
    assert len(db.scalars(select(models.BackgroundJob)).all()) == 1


def test_missing_mapping_waits_then_uses_restored_mapping(setup):
    db, site, job = setup
    job.payload = {**job.payload, 'project_number': None}; site.fibery_name = None; db.commit()
    client = Client()
    assert feature.execute(db, job.id, client=client, now=AT)['status'] == 'queued'
    assert not client.calls
    site.fibery_name = '#1715_restored'; db.commit()
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(seconds=61))['status'] == 'completed'


def test_conflicting_human_edit_stops_automatic_retry(setup):
    db, _, job = setup
    class Conflict(Client):
        def ensure_task(self, **values): raise FiberyConflict('Изменено вручную.')
    assert feature.execute(db, job.id, client=Conflict())['status'] == 'failed'
    client = Client()
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(hours=1))['status'] == 'waiting_or_claimed'
    assert not client.calls


def test_lost_worker_recovery_requires_absent_delivery(setup):
    db, _, job = setup
    job.status = 'running'; job.started_at = AT; db.commit()
    later = AT+timedelta(minutes=16)
    feature.recover(db, None, later)
    feature.recover(db, {job.id}, later)
    assert job.status == 'running'
    feature.recover(db, set(), later)
    assert job.status == 'queued'


def test_dispatcher_routes_gsc_work_and_respects_retry_backoff(setup, monkeypatch):
    from app.background_jobs import dispatch_pending, run_job
    db, _, job = setup
    calls = []
    dispatch_pending(db, lambda id_, queue: calls.append((id_, queue)), set())
    assert calls == [(job.id, 'maintenance')]
    monkeypatch.setattr(feature, 'execute', lambda db_, id_: {'status':'routed', 'id':id_})
    assert run_job(db, job.id) == {'status':'routed', 'id':job.id}
    job.dispatched_at = None
    job.result = {'next_attempt_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    db.commit(); calls.clear()
    dispatch_pending(db, lambda id_, queue: calls.append((id_, queue)), set())
    assert not calls
