from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models, project_notifications as notices
from app.db import Base, get_db
from app.project_notifications_api import router, Notice
from app.security import require_auth


@pytest.fixture
def setup():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site=models.Site(name='logs.test',base_url='https://logs.test',publication_endpoint='/')
        other=models.Site(name='other.test',base_url='https://other.test',publication_endpoint='/')
        db.add_all([site,other]);db.commit()
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_db]=lambda:db
        app.dependency_overrides[require_auth]=lambda:{'id':'user','username':'anton','is_admin':True}
        yield db,site,other,TestClient(app)


def test_client_error_is_durable_deduplicated_and_resolved(setup):
    db,site,other,client=setup
    url=f'/sites/{site.id}/notifications'
    payload={'key':'save-canonical','code':'HTTP_502','message':'Webdev временно недоступен','context':'PATCH /head'}
    first=client.post(url,json=payload);assert first.status_code==200,first.text
    assert client.post(url,json=payload).json()['id']==first.json()['id']
    feed=client.get(url).json()
    assert feed['active_count']==1 and feed['total']==1 and feed['items'][0]['occurrences']==2
    assert feed['items'][0]['client_key']=='save-canonical'
    assert client.get(f'/sites/{other.id}/notifications').json()['total']==0
    client.post(url,json={**payload,'active':False,'message':'Сохранение подтверждено'})
    feed=client.get(url).json()
    assert feed['active_count']==0 and feed['total']==1 and feed['items'][0]['status']=='resolved'
    assert feed['items'][0]['message']==payload['message'] and feed['items'][0]['code']=='HTTP_502'
    assert client.get(url+'?active_only=true').json()['items']==[]
    assert db.scalar(select(models.ProjectNotification)).resolved_at is not None
    assert client.post(url,json=payload).json()['id']!=first.json()['id']
    assert client.get(url).json()['total']==2


def test_logs_include_sources_without_secrets_or_cross_project_errors(setup):
    db,site,other,client=setup
    task=models.GenerationTask(title='Generation',site_id=site.id,geo='PL',language='pl')
    db.add(task);db.flush()
    item=models.ContentItem(task_id=task.id,site_id=site.id,topic='Topic',slug='/bonus/',generated_json={},
        status='generation_failed',generation_error='Gemini failed',idempotency_key=str(uuid4()))
    db.add(item);db.flush()
    db.add_all([
        models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='reserve',status='failed',initiator='anton',request_payload={'reserve':'target.test','username':'PRIVATE_USER','password':'PRIVATE_PASS'},message='Reserve failed'),
        models.NetworkOperation(id=str(uuid4()),site_id=other.id,action='reserve',status='failed',initiator='other',request_payload={},message='OTHER_PROJECT_SECRET'),
        models.AutoLbGeneration(site_id=site.id,created_by_user_id='user',provider_id='provider',kind='topics',context={},prompt='PRIVATE_PROMPT',status='failed',error='AutoLB failed'),
        models.PublicationLog(content_item_id=item.id,endpoint_url='https://site.test?token=PRIVATE_TOKEN',request_payload={'api_key':'PRIVATE_KEY'},response_status=502,error_message='Gateway failed api_key=REMOVE_ME'),
        models.BackgroundJob(kind='sync',status='failed',payload={'site_id':site.id},error='Sync failed'),
    ]);db.commit()
    feed=client.get(f'/sites/{site.id}/notifications').json()
    assert {'network','generation','auto_lb','publication','job'} <= {n['source'] for n in feed['items']}
    assert feed['active_count']==5
    text=str(feed)
    assert all(value not in text for value in ['OTHER_PROJECT_SECRET','PRIVATE_USER','PRIVATE_PASS','PRIVATE_PROMPT','PRIVATE_TOKEN','PRIVATE_KEY','REMOVE_ME'])
    item.status='published';item.published_at=datetime.now(timezone.utc);db.commit()
    feed=client.get(f'/sites/{site.id}/notifications').json()
    assert not any(n['active'] for n in feed['items'] if n['source'] in {'generation','publication'})


def test_confirmed_final_network_state_does_not_count_old_domain_error(setup):
    db,site,other,client=setup
    site.network_state={'domains':['present.test']}
    db.add(models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='create_domains',status='failed',initiator='anton',
        request_payload={'domains':[{'domain':'present.test'}]},message='Old DNS error'))
    db.commit()
    feed=client.get(f'/sites/{site.id}/notifications').json()
    assert feed['active_count']==0 and feed['total']==1


def test_empty_footer_is_not_an_error_but_populated_missing_menu_is(setup):
    db,site,_,client=setup
    site.footer_menu_rendered=False;db.commit()
    assert client.get(f'/sites/{site.id}/notifications').json()['active_count']==0
    site.default_menu={'header':[],'footer':[{'title':'Terms','url':'/terms/'}]};db.commit()
    feed=client.get(f'/sites/{site.id}/notifications').json()
    assert feed['active_count']==1 and feed['items'][0]['code']=='MENU_NOT_RENDERED'
    site.footer_menu_rendered=True;db.commit()
    assert client.get(f'/sites/{site.id}/notifications').json()['active_count']==0


def test_full_history_is_paginated_and_searchable(setup):
    db,site,_,client=setup
    for i in range(111):
        db.add(models.ProjectNotification(site_id=site.id,event_key=f'client:anton:{i}',code=f'ERROR_{i}',message=f'Failure number {i}',context='',severity='error',active=True))
    db.commit();url=f'/sites/{site.id}/notifications'
    feed=client.get(url+'?offset=100&limit=50').json()
    assert feed['total']==feed['active_count']==111 and len(feed['items'])==11
    assert len(feed['active_client_keys'])==111
    assert client.get(url+'?q=ERROR_110').json()['total']==1
    assert client.get(url+'?limit=200').status_code==422
    assert client.get('/sites/missing/notifications').status_code==404


def test_redaction_handles_json_headers_and_query_parameters():
    text=notices.safe_text('Authorization: Bearer abc.def?token=secret &key=x {"api_key":"private"} password=hidden')
    assert all(value not in text for value in ['abc.def','secret','private','hidden'])


def test_failed_replacement_of_published_content_is_still_active(setup):
    db,site,_,client=setup
    task=models.GenerationTask(title='Published task',site_id=site.id,geo='PL',language='pl')
    db.add(task);db.flush()
    item=models.ContentItem(task_id=task.id,site_id=site.id,topic='Published',slug='/published/',generated_json={},
        status='published',generation_error='Replacement failed',idempotency_key=str(uuid4()))
    db.add(item);db.flush()
    db.add(models.ContentRevision(content_item_id=item.id,remarks='Regenerate',source_json={},status='failed',error_message='Replacement failed',source_status='published'))
    db.commit();url=f'/sites/{site.id}/notifications'
    feed=client.get(url).json()
    assert feed['active_count']==1
    assert any(n['active'] and n['code']=='CONTENT_REVISION' for n in feed['items'])
    db.add(models.ContentRevision(content_item_id=item.id,remarks='Retry',source_json={},status='completed'))
    db.commit()
    assert client.get(url).json()['active_count']==0


def test_project_isolation_uses_request_scopes(setup):
    db,site,other,client=setup
    notices.record(db,other,'anton',Notice(key='private',code='PRIVATE',message='Other private issue'))
    site_id,other_id=site.id,other.id
    db.expunge_all()
    db.info['allowed_site_ids']=[site_id]
    response=client.get(f'/sites/{other_id}/notifications')
    assert response.status_code==404
    db.info.clear()


def test_successful_publication_resolves_older_retry_and_publication_jobs_but_keeps_history(setup):
    from datetime import timedelta
    db, site, _, client = setup
    task = models.GenerationTask(title='Recovered', site_id=site.id, geo='PL', language='pl')
    db.add(task); db.flush()
    now = datetime.now(timezone.utc)
    item = models.ContentItem(task_id=task.id, site_id=site.id, topic='Recovered', slug='/ok/',
        generated_json={}, status='published', published_at=now, idempotency_key=str(uuid4()))
    db.add(item); db.flush()
    db.add_all([models.BackgroundJob(kind='generation_retry', status='failed', payload={'content_id': item.id}, error='Old generation failure', updated_at=now-timedelta(hours=1)),
                models.BackgroundJob(kind='publication', status='failed', payload={'content_id': item.id}, error='Old publication failure', updated_at=now-timedelta(minutes=30))])
    db.commit()
    data = client.get(f'/sites/{site.id}/notifications').json()
    assert data['active_count'] == 0
    assert len([r for r in data['items'] if r['source'] == 'job' and r['status'] == 'failed']) == 2


def test_failure_after_previous_publication_remains_active(setup):
    from datetime import timedelta
    db, site, _, client = setup
    task = models.GenerationTask(title='New attempt', site_id=site.id, geo='PL', language='pl')
    db.add(task); db.flush()
    item = models.ContentItem(task_id=task.id, site_id=site.id, topic='New attempt', slug='/old/',
        generated_json={}, status='published', published_at=datetime.now(timezone.utc)-timedelta(days=1), idempotency_key=str(uuid4()))
    db.add(item); db.flush()
    db.add(models.BackgroundJob(kind='publication', status='failed', payload={'content_id': item.id}, error='New failure'))
    db.commit()
    assert client.get(f'/sites/{site.id}/notifications').json()['active_count'] == 1


def test_archived_generation_errors_remain_in_history_without_active_badge(setup):
    db, site, _, client = setup
    task = models.GenerationTask(title='Archived', site_id=site.id, geo='PL', language='pl', archived_at=datetime.now(timezone.utc))
    db.add(task); db.flush()
    item = models.ContentItem(task_id=task.id, site_id=site.id, topic='Archived', slug='/old/',
        generated_json={}, status='generation_failed', generation_error='Old error', idempotency_key=str(uuid4()))
    db.add(item); db.flush()
    db.add(models.BackgroundJob(kind='generation_retry', status='failed', payload={'content_id': item.id}, error='Old retry'))
    db.commit()
    data = client.get(f'/sites/{site.id}/notifications').json()
    assert data['active_count'] == 0 and data['total'] == 2
