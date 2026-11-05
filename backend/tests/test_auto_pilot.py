from datetime import datetime,timezone
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models,auto_pilot as pilot,mass_reglue_launch as launch,auto_reglue as auto,reglue_reserves as stock
from app.project_network import NetworkConflict
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool,finish
USER={'username':'test','allowed_site_ids':None}


def test_heading_audit_updates_display_without_changing_saved_plan_or_drafts(pool):
    from copy import deepcopy
    from app.homepage_headings import audit_key
    db,source,target,remotes,add=pool
    job=preview(db)
    saved=deepcopy(job.result)
    row=next(r for r in pilot.view(db,job)['items'] if r['status']=='ready')
    site=db.get(models.Site,row['site_id']);site.cache_canon=row['old_main']
    db.add(models.AutoReglueConfig(key=audit_key(site.id),value={'main':row['old_main'],
        'metadata':{'h1':'Casino online banner heading','h1_source':'shortcode:banner','heading_version':2,'h1_status':'found'}}));db.commit()
    updated=next(r for r in pilot.view(db,job)['items'] if r['site_id']==site.id)
    assert updated['title_h1_current']['h1']=='Casino online banner heading'
    assert updated['new_main']==row['new_main'] and updated['alternate']==row['alternate']
    assert job.result==saved and not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not remote.calls for remote in remotes.values())
    # Neither another Main nor an already-started execution can use this overlay.
    site.cache_canon='changed.test';db.commit()
    assert next(r for r in pilot.view(db,job)['items'] if r['site_id']==site.id).get('title_h1_current')==row.get('title_h1_current')

    site.cache_canon=row['old_main'];job.kind=launch.KIND;db.commit()
    assert next(r for r in pilot.view(db,job)['items'] if r['site_id']==site.id).get('title_h1_current')==row.get('title_h1_current')


def test_long_legacy_h1_requires_review_before_manual_start(pool):
    from copy import deepcopy
    db,source,target,remotes,add=pool
    job=preview(db);result=deepcopy(job.result)
    p=next(p for g in result['groups'] for p in g.get('plans',[]))
    p.update(rewrite_title_h1=True,title_h1_preview={'h1_before':'Casino Brand the best games online today','h1_after':'Casino Brand the best online games today'})
    job.result=result;db.commit()
    assert pilot.view(db,job)['title_h1_outdated'] and not pilot.view(db,job)['launch_enabled']
    with pytest.raises(NetworkConflict,match='Правило H1'):pilot.start(db,job.id,USER)
    assert not list(db.scalars(select(models.AutoReglueRun)))


def preview(db):
    job=pilot.create(db,uuid4(),USER)
    launch.execute_step(db,job.id,lambda _:pytest.fail('Preview must never dispatch a reglue'))
    return job


def test_read_only_preview_persists_exact_allocation_and_runs_it_once(pool):
    db,source,target,remotes,add=pool
    job=preview(db);view=pilot.view(db,job)
    assert job.kind==launch.PREVIEW_KIND and job.status=='completed'
    assert view['mode']=='preview' and view['ready']==1 and view['progress']['percent']==100
    ready=next(r for r in view['items'] if r['status']=='ready')
    assert ready['new_main']=='next.test' and ready['geo']=='AZ' and 'своей сетки' in ready['scheme']
    assert 'next.test' in ready['alternate']
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not r.calls for r in remotes.values())
    assert pilot.create(db,job.id,USER).id==job.id
    pilot.start(db,job.id,USER);pilot.start(db,job.id,USER)
    sent=[];launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1
    run=db.get(models.AutoReglueRun,sent[0]);assert run.plan['new_main']==ready['new_main'] and run.plan['alternateMarkup']==ready['alternate']
    finish(db,[run]);launch.execute_step(db,job.id,sent.append)
    final=pilot.view(db,job)
    assert final['mode']=='execution' and final['progress']['percent']==100 and final['counts']['completed']==1
    assert any(e['action']=='reglue' and e['status']=='confirmed' for e in final['events'])
    assert len(sent)==1


def test_stale_network_never_substitutes_another_domain(pool):
    db,source,target,remotes,add=pool
    job=preview(db)
    remotes[source.id].data['settings']['domains'].remove('next.test')
    remotes[source.id].data['settings']['domains'].append('replacement.test')
    source.domain_types={**source.domain_types,'replacement.test':'newreg'};db.commit()
    pilot.start(db,job.id,USER)
    launch.execute_step(db,job.id,lambda _:pytest.fail('Stale plan should not dispatch'))
    final=pilot.view(db,job)
    assert final['counts']['failed']==1
    assert next(r for r in final['items'] if r.get('new_main')=='next.test')['status']=='failed'
    assert all(not r.calls for r in remotes.values())


@pytest.mark.parametrize('status', ['completed', 'partial'])
def test_close_notes_preserves_history_active_errors_and_new_notes(pool, status):
    from app.reglue_dns import note
    db,source,target,remotes,add=pool
    job=preview(db);pilot.start(db,job.id,USER)
    sent=[];launch.execute_step(db,job.id,sent.append)
    run=db.get(models.AutoReglueRun,sent[0])
    run.status=status
    run.plan={**run.plan, 'list_launch_id':job.id, 'backup_note':'Backup note',
        'dns_warnings':[{'domain':'next.test','message':'Old DNS note','checked_at':'2026-10-23T12:00:00+00:00'}]}
    db.commit()
    before_calls={key:list(remote.calls) for key,remote in remotes.items()}
    closed=pilot.archive_resolved_notes(db,job,USER)
    view=pilot.view(db,job);row=next(r for r in view['items'] if r.get('run_id')==run.id)
    if status=='partial':
        assert not closed and len(row['notes'])==2 and row['status']=='partial'
        assert not run.plan.get('archived_notes')
    else:
        assert closed[0]['notes']==2 and row['notes']==[] and row['status']=='completed'
        events=[e for e in view['events'] if e['action']=='Примечание закрыто']
        assert len(events)==2 and 'Old DNS note' in events[0]['message']
        assert run.plan['archived_notes'][0]['checked_at']=='2026-10-23T12:00:00+00:00'
        assert pilot.archive_resolved_notes(db,job,USER)==[]
        note(db,run,'next.test','New DNS note')
        row=next(r for r in pilot.view(db,job)['items'] if r.get('run_id')==run.id)
        assert [n['message'] for n in row['notes']]==['New DNS note']
    assert {key:list(remote.calls) for key,remote in remotes.items()}==before_calls


def test_update_labels_require_saved_fields_and_include_removed_alternates(pool):
    from uuid import UUID,uuid5
    db,source,target,remotes,add=pool
    job=preview(db)
    assert all('updated_fields' not in row for row in pilot.view(db,job)['items'])
    pilot.start(db,job.id,USER);sent=[];launch.execute_step(db,job.id,sent.append)
    run=db.get(models.AutoReglueRun,sent[0])
    run.status='partial'
    run.plan={**run.plan,'rewrite_title_h1':True,'enableAlternates':False,'alternateMarkup':'',
        'title_h1_preview':{'title_before':'Old title','title_after':'New title','h1_before':'Same heading','h1_after':'Same heading'}}
    db.commit()
    assert pilot.confirmed_updates(db,run)=={'title':False,'h1':False,'alternates':False}
    edit=models.ProjectPageEdit(id=str(uuid5(UUID(run.id),'title-h1-save')),site_id=run.site_id,page_key='home',
        requested_by='test',fingerprint='test',before_page={},after_page={},status='pending')
    db.add(edit);db.commit()
    assert not pilot.confirmed_updates(db,run)['title']
    edit.status='confirmed'
    run.plan={**run.plan,'verification':{'status':'confirmed','checks':[{'code':'ALTERNATES','ok':True},{'code':'TITLE_H1','ok':True}]}}
    db.commit()
    assert pilot.confirmed_updates(db,run)=={'title':True,'h1':False,'alternates':True}
    run.plan={**run.plan,'verification':{'status':'mismatch','checks':[{'code':'ALTERNATES','ok':False},{'code':'TITLE_H1','ok':False}]}}
    db.commit()
    assert pilot.confirmed_updates(db,run,True)=={'title':False,'h1':False,'alternates':False}


def test_preview_settings_and_authorization_are_rechecked(pool):
    db,source,target,remotes,add=pool
    job=preview(db)
    with pytest.raises(ValueError):pilot.get(db,job.id,{'username':'another','allowed_site_ids':None})
    with pytest.raises(ValueError):pilot.start(db,job.id,{'username':'test','allowed_site_ids':[target.id]})
    cfg=auto.config(db);cfg.scheme_mode='clean';auto.save_config(db,cfg)
    with pytest.raises(NetworkConflict,match='Настройки'):pilot.start(db,job.id,USER)
    assert not list(db.scalars(select(models.AutoReglueRun)))


def test_pool_domains_unique_across_brands_without_claiming_them(pool):
    db,source,target,remotes,add=pool
    source.project_status='working';target.cache_geo='PL';db.commit()
    other=add('other.test',brand='Other',geo='CZ')
    stock.import_domains(db,'first-drop.test second-drop.test','drop','','test')
    job=preview(db);ready=[r for r in pilot.view(db,job)['items'] if r['status']=='ready']
    assert len(ready)==2 and len({r['new_main'] for r in ready})==2
    assert all(r.status=='available' for r in db.scalars(select(models.ReglueReserveDomain)))
    assert all(not r.calls for r in remotes.values())


def test_no_participation_and_weekly_limit_visible_in_preview(pool):
    db,source,target,remotes,add=pool
    source.reglue_participation=False;target.last_reglue_at=datetime.now(timezone.utc);db.commit()
    job=preview(db);view=pilot.view(db,job)
    assert view['ready']==0 and view['counts']['skipped']==2
    with pytest.raises(ValueError):pilot.start(db,job.id,USER)
    assert all(not r.calls for r in remotes.values())


def test_start_rechecks_participation_before_remote_writes(pool):
    db,source,target,remotes,add=pool
    job=preview(db);source.reglue_participation=False;db.commit()
    pilot.start(db,job.id,USER)
    launch.execute_step(db,job.id,lambda _:pytest.fail('Disabled project must not dispatch'))
    assert pilot.view(db,job)['counts']['failed']==1
    assert all(not r.calls for r in remotes.values())


def test_preview_job_uses_automation_worker_without_launching(pool,monkeypatch):
    from app import background_jobs
    db,source,target,remotes,add=pool
    job=pilot.create(db,uuid4(),USER);sent=[]
    background_jobs.dispatch_pending(db,lambda *args:sent.append(args))
    assert sent==[(job.id,'automation')]
    monkeypatch.setattr('app.worker.auto_reglue_job.delay',lambda _:pytest.fail('Preview cannot launch'))
    background_jobs.run_job(db,job.id)
    assert pilot.view(db,job)['ready']==1


@pytest.mark.parametrize('execution_mode',['cross_network','within_network'])
def test_manual_preview_launch_does_not_enable_automation(pool,execution_mode):
    db,source,target,remotes,add=pool
    cfg=auto.config(db);cfg.enabled=False;cfg.execution_mode=execution_mode;auto.save_config(db,cfg)
    if execution_mode=='within_network':
        source.project_status=target.project_status='working'
        source=add('manual-own.test',free=2,brand='Test',geo='PL');source.cache_language='pl'
        cfg.scheme_mode='locale_base';auto.save_config(db,cfg)
        auto.save_config(db,auto.ProjectConfig(domain_layout='root_main',parent_kind='newreg',create_fake_main=True),source.id)
        db.commit()
    job=preview(db)
    assert pilot.view(db,job)['ready']==1
    assert pilot.view(db,job)['launch_enabled']
    assert not db.info.get('auto_pilot_preview')
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not r.calls for r in remotes.values())
    pilot.start(db,job.id,USER)
    sent=[];launch.execute_step(db,job.id,sent.append)
    assert len(sent)==1
    run=db.get(models.AutoReglueRun,sent[0])
    finish(db,[run]);launch.execute_step(db,job.id,sent.append)
    assert run.status=='completed',run.message
    assert not auto.config(db).enabled and not auto.config(db).schedule_enabled
    assert not db.info.get('manual_pilot_job_id')


def test_manual_permission_cannot_be_forged_or_used_for_another_project(pool):
    db,source,target,remotes,add=pool
    job=preview(db)
    fake=models.AutoReglueRun(id=str(uuid4()),site_id=source.id,initiator='test',plan={'list_launch_id':job.id},status='queued',phase='prepared')
    assert not launch.manual_pilot_allowed(db,source.id,fake)
    pilot.start(db,job.id,USER)
    assert not launch.manual_pilot_allowed(db,source.id,fake)


def test_domain_summary_counts_reserve_as_subset_of_drops(pool):
    db,source,target,remotes,add=pool
    source.project_status='working';target.cache_geo='PL';db.commit()
    stock.import_domains(db,'pool-drop.test','drop','','test')
    view=pilot.view(db,preview(db))
    assert view['domain_summary']=={'reserve_drops':1,'drops':1,'newregs':0,'other':0}
    assert len(view['domain_projects']['reserve_drops']) == 1
    assert view['domain_projects']['reserve_drops'] == view['domain_projects']['drops']


def test_new_preview_cancels_only_own_unfinished_preview_and_retries_are_idempotent(pool):
    db,source,target,remotes,add=pool
    previous=pilot.create(db,uuid4(),USER)
    other=pilot.create(db,uuid4(),{**USER,'username':'other'})
    request=uuid4();new=pilot.create(db,request,USER)
    assert previous.status=='cancelled' and other.status=='queued'
    assert db.get(models.AutoReglueConfig,launch.cancel_key(previous.id)).value['replacement']==new.id
    assert pilot.create(db,request,USER).id==new.id and new.status=='queued'
    launch.execute_step(db,previous.id,lambda _:pytest.fail('Cancelled preview must not run'))
    assert not list(db.scalars(select(models.AutoReglueRun)))


def test_preview_failure_is_visible_and_allows_a_new_attempt(pool,monkeypatch):
    db,source,target,remotes,add=pool
    job=pilot.create(db,uuid4(),USER)
    monkeypatch.setattr('app.pilot_variations.finalize',lambda *a:(_ for _ in ()).throw(ValueError('Ошибка подготовки схемы')))
    launch.execute_step(db,job.id,lambda _:pytest.fail('Preview cannot dispatch'))
    assert job.status=='failed' and job.error=='Ошибка подготовки схемы'
    assert pilot.create(db,uuid4(),USER).id!=job.id


def test_task_history_only_launches_with_access_pagination_and_no_side_effects(pool):
    db,source,target,remotes,add=pool
    first=preview(db)
    assert pilot.tasks(db,USER)['total']==0
    pilot.start(db,first.id,USER)
    second=preview(db)
    # History excludes previews and another user's launches.
    from copy import deepcopy
    foreign=models.BackgroundJob(id=str(uuid4()),kind=launch.KIND,status='completed',payload={**first.payload,'actor':'other'},result=deepcopy(first.result))
    db.add(foreign);db.commit()
    history=pilot.tasks(db,USER,0,1)
    assert history['total']==1 and not history['has_more']
    assert history['items'][0]['id']==first.id
    assert history['items'][0]['launched_at']==first.payload['launched_at']
    assert pilot.tasks(db,{**USER,'allowed_site_ids':[]})['total']==0
    assert pilot.tasks(db,USER,1,1)['items']==[]
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not remote.calls for remote in remotes.values())


def test_execution_date_comes_from_confirmed_reglue_not_plan_creation(pool):
    db,source,target,remotes,add=pool
    job=preview(db);pilot.start(db,job.id,USER)
    sent=[];launch.execute_step(db,job.id,sent.append)
    run=db.get(models.AutoReglueRun,sent[0])
    assert not next(r for r in pilot.view(db,job)['items'] if r.get('run_id')==run.id)['performed_at']
    finish(db,[run]);launch.execute_step(db,job.id,sent.append)
    row=next(r for r in pilot.view(db,job)['items'] if r.get('run_id')==run.id)
    assert row['performed_at']
    assert pilot.tasks(db,USER)['items'][0]['counts']['completed']==1
