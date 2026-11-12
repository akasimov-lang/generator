from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models, domain_placeholder_check as feature
from app.db import Base
from app.fibery_client import FiberyError

AT = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
URL = 'https://added.test/'


@pytest.fixture
def setup():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='project.test', base_url='https://project.test', publication_endpoint='/',
            fibery_name='#2069_Project_CZ', network_state={'domains': ['project.test']})
        db.add(site); db.flush()
        op = models.NetworkOperation(id=str(uuid4()), site_id=site.id, action='create_domains',
            status='pending', initiator='anton', created_at=AT, updated_at=AT,
            request_payload={'job_id': 'accepted', 'domain_added_at': AT.isoformat(),
                             'domains': [{'domain': 'added.test'}]})
        db.add(op); db.commit()
        yield db, site, op


class Client:
    def __init__(self):
        self.tasks, self.calls, self.manual = {}, [], None
        self.timeout = False
    def task(self, id_): return self.tasks.get(id_)
    def existing_domain_task(self, **kw): return self.manual
    def ensure_webdev_task(self, **kw):
        self.calls.append(kw)
        self.tasks[kw['task_id']] = {'workflow/state': {'enum/name': 'New'}}
        if self.timeout:
            self.timeout = False
            raise FiberyError('Timed out')
        return {'task_id': kw['task_id'], 'title': kw['title'], 'project_number': '2069', 'public_id': '20280',
                'state': 'New', 'url': 'https://hzhz.fibery.io/favorites/Alfasearch_Config/Webdev_Tasks/20280'}


def placeholder(url):
    row = {'url': url, 'final_url': url, 'http_status': 200, 'outcome': 'placeholder'}
    return {**row, 'previous_attempt': row.copy()}


def prepare(db, op):
    job, = feature.ensure_jobs(db, op)
    db.commit()
    return job


def run(db, job, client, **kw):
    return feature.execute(db, job.id, client=client, probe=kw.pop('probe', placeholder),
        now=kw.pop('now', AT + timedelta(seconds=120)), **kw)


def test_no_public_request_before_two_minutes_then_create_even_if_domain_missing(setup):
    db, site, op = setup; job = prepare(db, op); client = Client()
    assert run(db, job, client, now=AT+timedelta(seconds=119),
        probe=lambda _: pytest.fail('Must wait'))['status'] == 'waiting_or_claimed'
    assert run(db, job, client)['outcome'] == 'task_created'
    request = client.calls[0]
    assert request['title'] == 'added.test не добавился в сетку'
    assert request['page_url'] == URL and request['project_number'] == '2069'
    assert request['priority'] == 'Medium'
    assert 'https://ai-seo-content-panel.site/project-network/project.test/' in request['description']
    assert 'Проверить и добавить домен.' in request['description']
    assert run(db, job, client)['status'] == 'waiting_or_claimed'


def test_scanner_ignores_old_requests_and_unaccepted_failures_and_covers_batch(setup):
    db, site, op = setup
    db.add(models.AutoReglueConfig(key=feature.START_KEY,value={'enabled_at':(AT-timedelta(seconds=1)).isoformat()}))
    op.request_payload={**op.request_payload, 'domains': [{'domain': 'added.test'}, {'domain': 'two.test'}, {'domain': 'added.test'}]}
    old=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='create_domains',status='confirmed',
        initiator='anton',created_at=AT-timedelta(days=1),request_payload=deepcopy(op.request_payload))
    failed=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='create_domains',status='failed',
        initiator='anton',created_at=AT,request_payload={'domains':[{'domain':'failed.test'}]})
    db.add_all([old,failed]);db.commit()
    assert feature.tick(db,AT)['created']==2
    assert feature.tick(db,AT)['created']==0
    assert {j.payload['domain'] for j in db.scalars(select(models.BackgroundJob))}=={'added.test','two.test'}


def test_recovered_worker_preserves_job_identity(setup):
    db, site, op=setup;job=prepare(db,op)
    job.status='running';job.started_at=AT-timedelta(minutes=16);db.commit()
    assert feature.tick(db,AT)['recovered']==1
    assert job.status=='queued' and job.id==feature.identity(op.id+':added.test')


def test_normal_site_does_not_create_a_task(setup):
    db, site, op=setup;job=prepare(db,op);client=Client()
    assert run(db,job,client,probe=lambda url:{'url':url,'outcome':'review'})['outcome']=='no_placeholder'
    assert not client.calls


@pytest.mark.parametrize('outcome',['unreachable','blocked','http_error','redirect_loop'])
def test_uncertain_public_response_retries_without_fibery_task(setup,outcome):
    db,site,op=setup;job=prepare(db,op);client=Client()
    assert run(db,job,client,probe=lambda url:{'url':url,'outcome':outcome})['status']=='queued'
    assert not client.calls


def test_single_placeholder_or_offsite_redirect_cannot_trigger_task():
    row=placeholder(URL)
    assert feature.confirmed_placeholder(row,URL)
    assert not feature.confirmed_placeholder({**row,'previous_attempt':{}},URL)
    assert not feature.confirmed_placeholder({**row,'final_url':'https://other.test/'},URL)


def test_removed_domain_cancels_obsolete_job(setup):
    db,site,op=setup;job=prepare(db,op)
    db.add(models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='delete_domain',status='confirmed',
        initiator='anton',created_at=AT+timedelta(seconds=30),request_payload={'domains':['added.test']}));db.commit()
    assert run(db,job,Client(),probe=lambda _:pytest.fail('Removed domain'))['outcome']=='superseded'


def test_existing_manual_task_is_reused_without_changes(setup):
    db,site,op=setup;job=prepare(db,op);client=Client()
    client.manual={'task_id':'manual','public_id':'20273','title':job.payload['title'],'existing':True,
        'url':'https://hzhz.fibery.io/favorites/Alfasearch_Config/Webdev_Tasks/20273'}
    assert run(db,job,client)['outcome']=='task_reused' and not client.calls
    assert job.result['task']['task_id']=='manual'


def test_uncertain_creation_reuses_persisted_task_id(setup):
    db,site,op=setup;job=prepare(db,op);client=Client();client.timeout=True
    assert run(db,job,client)['status']=='queued'
    assert run(db,job,client,now=AT+timedelta(seconds=181))['outcome']=='task_created'
    assert len(client.tasks)==1 and client.calls[0]['task_id']==client.calls[1]['task_id']


def test_missing_fibery_relation_prevents_wrong_project_task(setup):
    db,site,op=setup;site.fibery_name=None;job=prepare(db,op);client=Client()
    assert run(db,job,client)['status']=='queued' and not client.calls
    assert 'номер Fibery' in job.error


def test_dispatch_waits_routes_maintenance_and_runs_special_handler(setup,monkeypatch):
    from app.background_jobs import dispatch_pending,run_job
    db,site,op=setup;job=prepare(db,op)
    job.payload={**job.payload,'due_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()};db.commit()
    sent=[]
    assert dispatch_pending(db,lambda *args:sent.append(args))['dispatched']==0
    job.payload={**job.payload,'due_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()};db.commit()
    assert dispatch_pending(db,lambda *args:sent.append(args))['dispatched']==1
    assert sent==[(job.id,'maintenance')]
    monkeypatch.setattr(feature,'execute',lambda db,id_:{'job_id':id_})
    assert run_job(db,job.id)=={'job_id':job.id}


def test_verified_receipt_is_visible_in_project_feed_and_notifications(setup):
    from app.fibery_tasks import feed
    from app.project_notifications import collect
    db,site,op=setup;job=prepare(db,op);run(db,job,Client())
    result=feed(db,{'username':'anton','allowed_site_ids':None},site_id=site.id)
    assert result['total']==1 and result['items'][0]['number']=='20280'
    notices=collect(db,site)
    assert any(n.get('task_url','').endswith('/Webdev_Tasks/20280') for n in notices)
