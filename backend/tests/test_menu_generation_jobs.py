from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_project_pages import setup
from app import api, models, menu_generation_jobs as jobs
from app.schemas import GeneratedMenuStructureApply

PREVIEW={'menu_type':'header','levels':1,'top_level_count':1,'mode':'thematic','geo':'DE','language':'de','items':[{'title':'Guide','slug':'/guide/','children':[]}]}

def enqueue(db,site,auto=False):
    return jobs.create(db,site,jobs.Request(request_id=uuid4(),settings={'levels':1,'top_level_count':1},create_pages=auto),{'id':'user','username':'anton'})

def test_preview_is_durable_and_duplicate_delivery_does_not_regenerate(setup,monkeypatch):
    _,db,site,_=setup
    calls=[]
    async def preview(*args):calls.append(1);return PREVIEW
    monkeypatch.setattr(api,'preview_site_menu_structure',preview)
    job=enqueue(db,site)
    assert job['status']=='queued' and calls==[]
    jobs.execute(db,job['id']);jobs.execute(db,job['id'])
    saved=db.get(models.BackgroundJob,job['id'])
    assert saved.status=='awaiting_review' and saved.result['preview']==PREVIEW and calls==[1]

def test_expired_preview_is_removed_and_cannot_be_applied(setup):
    _,db,site,_=setup
    job=enqueue(db,site);row=db.get(models.BackgroundJob,job['id'])
    row.status='awaiting_review';row.result={'preview':PREVIEW,'expires_at':(jobs.now()-timedelta(seconds=1)).isoformat()};db.commit()
    with pytest.raises(HTTPException) as error:jobs.accept(db,site.id,row.id,GeneratedMenuStructureApply.model_validate(PREVIEW))
    assert error.value.status_code==409
    assert row.status=='expired' and 'preview' not in row.result

def test_auto_publish_queues_apply_once_and_preserves_completed_result(setup,monkeypatch):
    _,db,site,_=setup
    calls=[]
    async def preview(*args):return PREVIEW
    async def apply(*args):calls.append(args[1].create_pages);return {'success':True,'created_count':1}
    monkeypatch.setattr(api,'preview_site_menu_structure',preview);monkeypatch.setattr(api,'apply_site_generated_menu_structure',apply)
    job=enqueue(db,site,True)
    jobs.execute(db,job['id']);assert db.get(models.BackgroundJob,job['id']).status=='queued'
    jobs.execute(db,job['id']);jobs.execute(db,job['id'])
    row=db.get(models.BackgroundJob,job['id']);row.result={**row.result,'expires_at':(jobs.now()-timedelta(days=2)).isoformat()};db.commit();jobs.expire(db)
    assert row.status=='completed' and row.result['preview']==PREVIEW and calls==[True]

def test_generation_failure_never_applies_menu(setup,monkeypatch):
    _,db,site,_=setup
    async def fail(*args):raise ValueError('AI unavailable')
    monkeypatch.setattr(api,'preview_site_menu_structure',fail)
    job=enqueue(db,site,True);jobs.execute(db,job['id'])
    row=db.get(models.BackgroundJob,job['id'])
    assert row.status=='failed' and 'AI unavailable' in row.error and not row.payload.get('accepted')

def test_changed_menu_blocks_apply(setup,monkeypatch):
    _,db,site,_=setup
    job=enqueue(db,site);row=db.get(models.BackgroundJob,job['id'])
    row.payload={**row.payload,'accepted':GeneratedMenuStructureApply.model_validate(PREVIEW).model_dump()}
    site.default_menu={'header':[{'title':'User edit','path':'/new/'}],'footer':[]};db.commit()
    jobs.execute(db,row.id)
    assert row.status=='failed' and 'Меню изменилось' in row.error


def test_menu_progress_distinguishes_stub_generated_published_and_failed_pages(setup):
    _,db,site,_=setup
    task=models.GenerationTask(title='Menu pages',geo='DE',language='de',topics_count=4)
    db.add(task);db.flush()
    for i,(status,generated) in enumerate([('draft',False),('generated',True),('published',True),('generation_failed',False)]):
        db.add(models.ContentItem(task_id=task.id,site_id=site.id,topic=str(i),slug=f'/page-{i}/',
            generated_json={'pages':[{'slug':f'/page-{i}/'}]},status=status,
            generated_at=jobs.now() if generated else None,idempotency_key=str(uuid4())))
    job=enqueue(db,site,True);row=db.get(models.BackgroundJob,job['id'])
    row.status='completed';row.result={'applied':{'page_task_id':task.id}};db.commit()
    result=jobs.view(db,row)
    assert result['progress']=={'total':4,'generated':2,'published':1,'deleted':0,'errors':1}
    assert len(result['pages'])==4


def test_interrupted_generation_retries_once_and_keeps_event_history(setup):
    _,db,site,_=setup
    job=enqueue(db,site);row=db.get(models.BackgroundJob,job['id'])
    row.status='generating';row.started_at=jobs.now()-timedelta(minutes=6);row.result={**row.result,'attempts':1};db.commit()
    jobs.recover_interrupted(db)
    assert row.status=='queued' and row.dispatched_at is None
    assert len(row.result['events'])==2
    row.status='generating';row.result={**row.result,'attempts':2};db.commit()
    jobs.recover_interrupted(db)
    assert row.status=='failed' and 'повторно' in row.error


def test_interrupted_apply_requires_verification_without_repeating_write(setup):
    _,db,site,_=setup
    job=enqueue(db,site);row=db.get(models.BackgroundJob,job['id'])
    row.status='applying';row.started_at=jobs.now()-timedelta(minutes=6);db.commit()
    jobs.recover_interrupted(db)
    assert row.status=='failed' and 'проверка результата' in row.error


def test_journal_filters_project_access_before_returning_jobs(setup):
    _,db,site,_=setup
    job=enqueue(db,site)
    assert api.menu_generation_journal({'allowed_site_ids':[]},db)==[]
    assert api.menu_generation_journal({'allowed_site_ids':[site.id]},db)[0]['id']==job['id']
    assert api.menu_generation_journal({'allowed_site_ids':None},db)[0]['project_name']==site.name
