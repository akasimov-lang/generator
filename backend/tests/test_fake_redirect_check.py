from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models, fake_redirect_check as feature
from app.db import Base
from app.fibery_client import FiberyError

AT = datetime(2026, 11, 12, 8, tzinfo=timezone.utc)
URL = 'https://project.test/contacts'


def op(db, site, **values):
    row = models.NetworkOperation(id=str(uuid4()), site_id=site.id, action='create_fake_main',
        status='confirmed', initiator='anton', created_at=AT, updated_at=AT,
        request_payload={'confirmed_at': AT.isoformat(),
            'fibery_before': {'main': 'project.test', 'fake_path': '/old/'},
            'alternate': {'currentFakeMain': '/contacts', 'enableDynamicRoutes': True}, **values})
    db.add(row); db.flush(); return row


@pytest.fixture
def setup():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='project.test', base_url='https://project.test', publication_endpoint='/',
            fibery_name='#1715_Lemon_PL', cache_canon='project.test',
            network_state={'canon':'project.test','fake_main_current':'/contacts','fake_main_enabled':True})
        db.add(site); db.flush(); operation = op(db, site); db.commit()
        yield db, site, operation


class Client:
    def __init__(self): self.tasks = {}; self.calls = []; self.timeout = False
    def task(self, task_id): return self.tasks.get(task_id)
    def ensure_webdev_task(self, **values):
        self.calls.append(values)
        self.tasks[values['task_id']] = {'workflow/state': {'enum/name': 'New'}}
        if self.timeout:
            self.timeout = False; raise FiberyError('HTTP timeout')
        return {'task_id':values['task_id'],'title':values['title'],'public_id':'20274','project_number':'1715',
            'url':'https://hzhz.fibery.io/favorites/Alfasearch_Config/Webdev_Tasks/20274','state':'New'}


def redirected(url):
    return {'url': url, 'chain': [{'url':url,'status':301,'location':url+'/'},
                               {'url':url+'/','status':200,'location':None}]}


def run(db, operation, client=None, **kwargs):
    job=feature.ensure_job(db,operation); db.commit()
    result=feature.execute(db,job.id,client=client or Client(),probe=redirected,now=AT+timedelta(seconds=20),**kwargs)
    return job,result


def test_exact_url_task_contains_correct_reverse_redirect_and_project(setup):
    db,site,operation=setup;client=Client();job,result=run(db,operation,client)
    request=client.calls[0]
    assert result['outcome']=='task_created' and request['project_number']=='1715'
    assert request['page_url']==URL and request['title']=='project.test — исправить редирект /contacts'
    assert URL+'/ → '+URL in request['description']
    assert URL+' должен возвращать HTTP 200' in request['description']
    assert 'Проект: https://project.test/' in request['description']


def test_redirect_to_root_does_not_invent_a_root_to_fake_redirect():
    title,description=feature.request_text({'url':URL,'chain':[{'status':301,'location':'https://project.test/'}]})
    assert 'обратном направлении' not in description
    assert 'HTTP 200 напрямую' in description


def test_selected_trailing_slash_is_preserved_and_reverse_target_follows_it():
    url=URL+'/'
    title,description=feature.request_text({'url':url,'chain':[{'status':301,'location':URL}]})
    assert f'HTTP 301 в обратном направлении: {URL} → {url}.' in description


def test_task_describes_confirmed_slash_redirect_loop():
    evidence={'url':URL,'chain':[{'url':URL,'status':301,'location':URL+'/'},
        {'url':URL+'/','status':301,'location':URL}]}
    _,description=feature.request_text(evidence)
    assert f'Обнаружена петля редиректов: {URL} → HTTP 301 → {URL}/ → HTTP 301 → {URL}.' in description
    assert f'{URL} должен возвращать HTTP 200 напрямую' in description


def test_reglue_checks_preserved_path_on_new_main_from_legacy_snapshot(setup):
    db,site,operation=setup
    operation.action='reglue'
    operation.request_payload={'reserve':'new.test','journal_before':{'main':'old.test',
        'fake_path':'/contacts','fake_enabled':True},'confirmed_at':AT.isoformat()}
    site.cache_canon='unrelated-cache.test';db.commit()
    job=feature.ensure_job(db,operation)
    assert job.status=='queued' and job.payload['url']=='https://new.test/contacts'


def test_reglue_confirmation_checks_even_when_snapshot_url_is_unchanged(setup):
    db,site,operation=setup
    operation.action='reglue'
    operation.request_payload={'fibery_before':{'main':'project.test','fake_path':'/contacts','fake_enabled':True},
        'journal_after':{'main':'project.test','fake_path':'/contacts','fake_enabled':True},'confirmed_at':AT.isoformat()}
    job=feature.ensure_job(db,operation)
    assert job.status=='queued' and job.payload['url']==URL


def test_healthy_url_does_not_create_task(setup):
    db,site,operation=setup;job=feature.ensure_job(db,operation);db.commit();client=Client()
    result=feature.execute(db,job.id,client=client,now=AT+timedelta(seconds=20),
        probe=lambda url:{'url':url,'chain':[{'url':url,'status':200,'location':None}]})
    assert result['outcome']=='no_301' and not client.calls


def test_changed_url_cancels_obsolete_check_before_network_io(setup):
    db,site,operation=setup;job=feature.ensure_job(db,operation)
    site.network_state={**site.network_state,'fake_main_current':'/new/'};db.commit()
    result=feature.execute(db,job.id,client=Client(),now=AT+timedelta(seconds=20),
        probe=lambda _:pytest.fail('Obsolete URL must not be fetched'))
    assert result['outcome']=='superseded'


def test_multiple_changes_to_same_url_reuse_open_task(setup):
    db,site,operation=setup;client=Client();first,_=run(db,operation,client)
    second,_=run(db,op(db,site),client)
    assert first.id!=second.id and len(client.tasks)==1
    assert client.calls[0]['task_id']==client.calls[1]['task_id']


def test_recurrence_after_closed_task_creates_a_new_request(setup):
    db,site,operation=setup;client=Client();first,_=run(db,operation,client)
    client.tasks[first.result['task']['task_id']]['workflow/state']['enum/name']='Closed'
    second,_=run(db,op(db,site),client)
    assert first.result['task']['task_id']!=second.result['task']['task_id'] and len(client.tasks)==2


def test_timeout_recovery_uses_saved_task_identity(setup):
    db,site,operation=setup;client=Client();client.timeout=True
    job,result=run(db,operation,client)
    assert result['status']=='queued'
    result=feature.execute(db,job.id,client=client,probe=redirected,now=AT+timedelta(seconds=81))
    assert result['status']=='completed' and len(client.tasks)==1
    assert client.calls[0]['task_id']==client.calls[1]['task_id']


def test_missing_project_relation_does_not_create_in_another_project(setup):
    db,site,operation=setup;site.fibery_name=None;client=Client();job,result=run(db,operation,client)
    assert result['status']=='queued' and not client.calls and 'номер Fibery' in job.error


def test_failed_http_probe_is_not_reported_as_a_redirect(setup):
    db,site,operation=setup;job=feature.ensure_job(db,operation);db.commit();client=Client()
    result=feature.execute(db,job.id,client=client,now=AT+timedelta(seconds=20),
        probe=lambda url:{'url':url,'chain':[{'url':url,'status':503,'location':None}]})
    assert result['status']=='queued' and not client.calls and 'HTTP 503' in job.error


def test_scanner_covers_head_confirmation_and_does_not_backfill_history(setup):
    db,site,operation=setup
    db.add(models.AutoReglueConfig(key=feature.START_KEY,value={'enabled_at':(AT-timedelta(seconds=1)).isoformat()}))
    old=op(db,site,confirmed_at=(AT-timedelta(days=1)).isoformat());old.updated_at=AT-timedelta(days=1)
    pending=op(db,site);pending.status='unknown';db.commit()
    assert feature.tick(db,AT)['created']==1
    assert feature.tick(db,AT)['created']==0
    assert [j.payload['operation_id']for j in db.scalars(select(models.BackgroundJob))]==[operation.id]


def test_unchanged_and_disabled_fake_paths_are_not_queued(setup):
    db,site,operation=setup
    operation.request_payload={**operation.request_payload,'fibery_before':{'main':'project.test','fake_path':'/contacts'}}
    job=feature.ensure_job(db,operation)
    assert job.status=='completed' and job.result['outcome']=='unchanged_or_disabled'
    disabled=op(db,site,alternate={'currentFakeMain':'/contacts','enableDynamicRoutes':False})
    assert feature.ensure_job(db,disabled).status=='completed'


def test_reconciled_history_does_not_starve_new_checks(setup):
    db,site,operation=setup
    db.add(models.AutoReglueConfig(key=feature.START_KEY,value={'enabled_at':(AT-timedelta(seconds=2)).isoformat()}))
    for _ in range(100):
        old=op(db,site,confirmed_at=(AT-timedelta(days=1)).isoformat())
        old.updated_at=AT-timedelta(seconds=1)
    db.commit()
    assert feature.tick(db,AT)['created']==0
    assert feature.tick(db,AT)['created']==1
    pending=list(db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.status=='queued')))
    assert len(pending)==1 and pending[0].payload['operation_id']==operation.id


def test_probe_uses_get_and_preserves_exact_path_without_offsite_follow(monkeypatch):
    called=[];original=httpx.Client
    def handler(request):
        called.append((request.method,str(request.url)))
        return httpx.Response(301,headers={'location':'https://other.test/contacts/'})
    monkeypatch.setattr(feature.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    result=feature.inspect_url(URL)
    assert called==[('GET',URL)] and result['chain'][0]['location']=='https://other.test/contacts/'


def test_task_is_linked_in_project_notes_and_dashboard(setup):
    from app.project_notifications import feed
    from app.fibery_tasks import feed as tasks
    db,site,operation=setup;job,_=run(db,operation)
    notes=feed(db,site)['items'];note=next(n for n in notes if n['code']=='FIBERY_WEBDEV_REDIRECT')
    assert note['task_url'].endswith('/Webdev_Tasks/20274')
    result=tasks(db,{'allowed_site_ids':None},site_id=site.id)
    assert result['total']==1 and result['items'][0]['kind']=='webdev'
    assert result['items'][0]['projects'][0]['id']==site.id


def test_dispatcher_waits_for_due_check_and_routes_it_to_maintenance(setup,monkeypatch):
    from app.background_jobs import dispatch_pending
    from app import menu_generation_jobs
    monkeypatch.setattr(menu_generation_jobs,'expire',lambda db:None)
    monkeypatch.setattr(menu_generation_jobs,'recover_interrupted',lambda db:None)
    db,site,operation=setup;job=feature.ensure_job(db,operation)
    job.payload={**job.payload,'due_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()}
    db.commit();sent=[];dispatch_pending(db,lambda *args:sent.append(args));assert not sent
    job.payload={**job.payload,'due_at':AT.isoformat()};db.commit()
    dispatch_pending(db,lambda *args:sent.append(args))
    assert sent==[(job.id,'maintenance')]
