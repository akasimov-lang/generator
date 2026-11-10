from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models, fibery_reglue as feature
from app.db import Base
from app.fibery_client import FiberyConflict, FiberyError
from app.fibery_reglue_evidence import build, network_snapshot
from app.project_notifications import feed
from app.reglue_journal import confirmed_at
from test_project_network import env

AT = datetime(2026, 11, 10, 9, 39, 33, tzinfo=timezone.utc)
BEFORE = '<link rel="alternate" hreflang="cs" href="https://{{settings.canon}}/old/" />'
AFTER = '<link rel="alternate" hreflang="cs" href="https://{{settings.canon}}/new/" />'


def operation(db, site, action='reglue', seconds=0, status='confirmed', **payload):
    at = AT + timedelta(seconds=seconds)
    row = models.NetworkOperation(id=str(uuid4()), site_id=site.id, initiator='anton', action=action,
        status=status, request_payload={'confirmed_at': at.isoformat(), **payload}, created_at=at, updated_at=at)
    db.add(row); db.flush()
    return row


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(feature, 'get_settings', lambda: SimpleNamespace(fibery_api_token=SecretStr('test')))
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='project.test', base_url='https://old.test', publication_endpoint='/', fibery_name='#626_BetOnRed_CZ')
        other = models.Site(name='other.test', base_url='https://other.test', publication_endpoint='/')
        db.add_all([site, other]); db.flush()
        op = operation(db, site, source_domain='old.test', reserve='new.test',
            fibery_before={'main':'old.test', 'fake_path':'/old/', 'alternates':{'markup':BEFORE,'enabled':True}},
            fibery_after={'main':'new.test', 'fake_path':'/old/', 'alternates':{'markup':BEFORE,'enabled':True}})
        db.commit()
        yield db, site, other, op


class Client:
    def __init__(self): self.calls = []
    def ensure_task(self, **values):
        self.calls.append(values)
        return dict(task_id=values['task_id'], public_id='33303', title=values['title'],
            url='https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Tasks/33303', description_verified=True)


def test_delay_is_exactly_180_seconds_and_repeated_execution_is_idempotent(setup):
    db, site, _, op = setup
    job = feature.ensure_job(db, op); db.commit()
    assert feature.ensure_job(db, op).id == job.id
    client = Client()
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(seconds=179))['status'] == 'waiting_or_claimed'
    assert not client.calls
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(seconds=180))['status'] == 'completed'
    assert feature.execute(db, job.id, client=client, now=AT+timedelta(seconds=181))['status'] == 'waiting_or_claimed'
    assert len(client.calls) == 1
    assert client.calls[0]['project_number'] == '626'
    assert client.calls[0]['title'] == 'Переклей: old.test → new.test'


def test_window_includes_boundaries_changes_and_edits_but_excludes_other_projects_and_later_work(setup):
    db, site, other, op = setup
    first = operation(db, site, 'reserve', -180, reserve='new.test')
    last = operation(db, site, 'alternates', 180, alternateMarkup=AFTER, enableAlternates=True,
        alternates_before={'markup': BEFORE, 'enabled': True}, journal_after={'fake_path':'/new/'})
    excluded = operation(db, site, 'reserve', 181, reserve='later.test')
    outside = operation(db, other, 'reserve', 20, reserve='foreign.test')
    edit = models.ProjectPageEdit(id=str(uuid4()),site_id=site.id,page_key='home',requested_by='anton',fingerprint='x',
        before_page={'title':'Old'},after_page={'title':'New'},status='confirmed',created_at=AT,updated_at=AT)
    db.add(edit); db.commit()
    # Current cache is deliberately unrelated and must never replace the historical snapshots.
    site.network_state={'canon':'later.test','alternateMarkup':'LATER_SECRET'}
    e = build(db,site,op)
    ids = {x['id'] for x in e['events']}
    assert {first.id,last.id,op.id,edit.id} <= ids
    assert excluded.id not in ids and outside.id not in ids
    assert e['old_path']=='/old/' and e['new_path']=='/new/'
    assert e['alternates_before']['markup']==BEFORE and e['alternates_after']['markup']==AFTER
    assert 'https://old.test/old/' in e['description'] and 'https://new.test/new/' in e['description']
    assert 'LATER_SECRET' not in e['description'] and 'foreign.test' not in e['description']


def test_retry_freezes_evidence_and_keeps_the_same_external_id(setup):
    db,site,_,op=setup
    job=feature.ensure_job(db,op);db.commit()
    class Failed(Client):
        def ensure_task(self,**values):
            self.calls.append(values)
            raise FiberyError('Fibery: HTTP 429.')
    failed=Failed();now=AT+timedelta(seconds=180)
    assert feature.execute(db,job.id,client=failed,now=now)['status']=='queued'
    original=job.result['evidence']['description']
    operation(db,site,'reserve',240,reserve='must-not-enter.test');db.commit()
    retry=Client()
    assert feature.execute(db,job.id,client=retry,now=now+timedelta(seconds=59))['status']=='waiting_or_claimed'
    assert feature.execute(db,job.id,client=retry,now=now+timedelta(seconds=60))['status']=='completed'
    assert retry.calls[0]['task_id']==failed.calls[0]['task_id']
    assert retry.calls[0]['description']==original


def test_late_confirmation_is_listed_as_started_but_does_not_change_window_result(setup):
    db,site,_,op=setup
    late=operation(db,site,'alternates',240,alternateMarkup=AFTER,enableAlternates=True)
    late.created_at=AT+timedelta(seconds=150);db.commit()
    evidence=build(db,site,op)
    event=next(x for x in evidence['events'] if x['id']==late.id)
    assert event['status']=='pending_at_window_end'
    assert evidence['alternates_after']['markup']==BEFORE


def test_missing_fibery_mapping_waits_and_never_creates_in_an_arbitrary_project(setup):
    db,site,_,op=setup;site.fibery_name=None
    job=feature.ensure_job(db,op);db.commit();client=Client()
    assert feature.execute(db,job.id,client=client,now=AT+timedelta(seconds=180))['status']=='queued'
    assert not client.calls and 'номер Fibery' in job.error
    site.fibery_name='#626_fixed';db.commit()
    assert feature.execute(db,job.id,client=client,now=AT+timedelta(seconds=240))['status']=='completed'


def test_external_human_edit_stops_retries_and_remains_visible_in_notes(setup):
    db,site,_,op=setup;job=feature.ensure_job(db,op);db.commit()
    class Conflict(Client):
        def ensure_task(self,**values): raise FiberyConflict('Описание изменено пользователем.')
    assert feature.execute(db,job.id,client=Conflict(),now=AT+timedelta(seconds=180))['status']=='failed'
    notice=next(x for x in feed(db,site)['items'] if x['source']=='fibery')
    assert notice['active'] and notice['severity']=='warning' and 'изменено' in notice['context']


def test_scanner_covers_manual_and_automatic_reglues_without_backfilling_old_history(setup):
    db,site,_,op=setup
    db.add(models.AutoReglueConfig(key=feature.START_KEY,value={'enabled_at':(AT-timedelta(seconds=1)).isoformat()}))
    auto=operation(db,site,seconds=1,source_domain='new.test',reserve='next.test',auto_run_id=str(uuid4()))
    old=operation(db,site,seconds=-200,source_domain='older.test',reserve='old.test')
    rejected=operation(db,site,seconds=2,status='unknown',source_domain='x.test',reserve='y.test')
    unchanged=operation(db,site,seconds=3,source_domain='same.test',reserve='same.test')
    db.commit()
    assert feature.tick(db,AT+timedelta(seconds=4))['created']==2
    assert feature.tick(db,AT+timedelta(seconds=5))['created']==0
    assert {j.payload['operation_id'] for j in db.scalars(select(models.BackgroundJob))}=={op.id,auto.id}


def test_stale_worker_is_recovered_after_restart(setup):
    db,site,_,op=setup;job=feature.ensure_job(db,op)
    job.status='running';job.started_at=AT
    db.add(models.AutoReglueConfig(key=feature.START_KEY,value={'enabled_at':AT.isoformat()}));db.commit()
    assert feature.tick(db,AT+timedelta(minutes=16))['recovered']==1
    assert job.status=='queued'


def test_notifications_expose_task_link_and_preserve_previous_task_history(setup):
    db,site,_,op=setup;job=feature.ensure_job(db,op);db.commit()
    feature.execute(db,job.id,client=Client(),now=AT+timedelta(seconds=180))
    notices=feed(db,site,active_only=True)['items']
    note=next(x for x in notices if x['source']=='fibery')
    assert note['task_url'].endswith('/33303') and note['task_title']=='Переклей: old.test → new.test'
    assert note['status']=='completed' and note['severity']=='info'
    assert not any(x['source']=='job' and job.id in x['id'] for x in notices)


def test_dispatcher_does_not_send_collecting_jobs_or_block_other_due_work(setup,monkeypatch):
    from app.background_jobs import dispatch_pending
    from app import menu_generation_jobs
    monkeypatch.setattr(menu_generation_jobs,'expire',lambda db:None)
    monkeypatch.setattr(menu_generation_jobs,'recover_interrupted',lambda db:None)
    db,site,_,op=setup;job=feature.ensure_job(db,op)
    future=datetime.now(timezone.utc)+timedelta(minutes=3)
    job.payload={**job.payload,'due_at':future.isoformat()}
    other=models.BackgroundJob(kind='cache_sync',payload={});db.add(other);db.commit();sent=[]
    dispatch_pending(db,lambda id,queue:sent.append((id,queue)))
    assert [x[0] for x in sent]==[other.id]


def test_snapshot_preserves_explicit_disabled_and_empty_values():
    snapshot=network_snapshot({'canon':'new.test','fake_main_current':'','fake_main_enabled':False,
        'alternateMarkup':'','enableAlternates':False})
    assert snapshot['fake_path']=='' and snapshot['alternates']=={'markup':'','enabled':False}


def test_network_confirmation_atomically_queues_task_with_before_after_snapshots(env,monkeypatch):
    from app import project_network as network
    from test_project_network import change
    monkeypatch.setattr(feature,'get_settings',lambda:SimpleNamespace(fibery_api_token=SecretStr('test')))
    db,site,remote=env
    site.fibery_name='#626_Project';db.commit()
    before=network.read_network(db,site)
    after=change(env,'reglue',before['revision'],domain='reserve.test')
    job=db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.kind==feature.KIND))
    assert job is not None and job.payload['title']=='Переклей: main.test → reserve.test'
    op=db.get(models.NetworkOperation,job.payload['operation_id'])
    assert op.request_payload['fibery_before']['main']=='main.test'
    assert op.request_payload['fibery_after']['main']=='reserve.test'
    assert feature.due(job,confirmed_at(op)+timedelta(seconds=179)) is False
