from uuid import uuid4
import pytest
from app import models, auto_reglue as auto, auto_reglue_api as api, mass_action_reports as reports
from app.mass_action_scope import MassActionFilter, constrain
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, finish


def test_filtered_batch_cannot_take_domain_from_unselected_larger_network(pool):
    db,source,target,remotes,add=pool
    outside=add('outside-large.test',30,15)
    filters={'brand':'Pin-Up','geo':'AZ'}
    result=api.preview_batch(api.BatchPreview(site_ids=[source.id,target.id],filter=filters),{'username':'test'},db)
    assert result['plans']
    assert all(p['source_site_id'] in {source.id,target.id} and p['source_site_id']!=outside.id for p in result['plans'])
    assert not remotes[outside.id].calls


def test_scoped_report_records_source_paths_result_and_survives_new_session(pool,monkeypatch):
    db,source,target,remotes,add=pool
    filters={'brand':'Pin-Up','geo':'AZ'}
    user={'username':'test','allowed_site_ids':[source.id,target.id]}
    preview=api.preview_batch(api.BatchPreview(site_ids=[source.id,target.id],filter=filters),user,db)
    plan=preview['plans'][0]
    assert plan['mass_filter']['brand']=='Pin-Up'
    sent=[];monkeypatch.setattr(api,'dispatch',lambda db,run:sent.append(run.id))
    payload=api.BatchStart(batch_id=preview['batch_id'],filter=filters,items=[api.StartItem(site_id=plan['site_id'],request_id=uuid4(),preview_token=plan['preview_token'])])
    result=api.start(payload,user,db)
    run=db.get(models.AutoReglueRun,result['results'][0]['run']['id'])
    finish(db,[run])
    entries=reports.list_reports(db,'Pin-Up','AZ')[0]['entries']
    assert entries[0]['source_project']==source.name and entries[0]['target_project']==target.name
    assert entries[0]['old_main']=='target.test' and entries[0]['new_main']=='next.test'
    assert entries[0]['status']=='completed' and entries[0]['confirmed_at']
    assert entries[0]['domains']==['next.test']
    assert not reports.list_reports(db,'Pin-Up','PL') and not reports.list_reports(db,'Other','AZ')
    assert not reports.list_reports(db,'Pin-Up','AZ',{target.id})
    db.expire_all()
    assert reports.list_reports(db,'Pin-Up','AZ')[0]['entries']==entries
    assert api.start(payload,user,db)['results'][0]['run']['id']==run.id
    assert len(reports.list_reports(db,'Pin-Up','AZ'))==1 and len(sent)==1


def test_report_keeps_original_and_confirmed_fake_paths_and_groups_launch(pool):
    db,source,target,remotes,add=pool
    run=models.AutoReglueRun(id=str(uuid4()),site_id=target.id,initiator='test',status='completed',phase='completed',plan={
        'project':target.name,'source_project':source.name,'source_site_id':source.id,
        'old_main':'old.test','new_main':'planned.test','old_fake_main_path':'/old/',
        'new_fake_main_path':'/planned/','applied_result':{'new_main':'actual.test','fake_main_path':'/actual/','confirmed_at':'2026-10-19T12:00:00Z'}})
    db.add(run);db.commit()
    scope=MassActionFilter(brand='Pin-Up',geo='AZ',include_general=True).model_dump()
    report_id=str(uuid4())
    reports.save(db,report_id,scope,[{'site_id':target.id,'run_id':run.id}],'test')
    item=reports.list_reports(db,'Pin-Up','AZ')[0]
    assert item['filter']['include_general']
    entry=item['entries'][0]
    assert entry['old_fake_main_path']=='/old/' and entry['new_fake_main_path']=='/actual/'
    assert entry['new_main']=='actual.test'
    target.name='renamed.test';source.name='source-renamed.test';db.commit()
    assert reports.list_reports(db,'Pin-Up','AZ')[0]['entries'][0]['target_project']=='destination.test'
    db.delete(run);db.commit()
    retained=reports.list_reports(db,'Pin-Up','AZ')[0]['entries'][0]
    assert retained['new_fake_main_path']=='/actual/' and retained['new_main']=='actual.test'
    assert retained['source_project']!='source-renamed.test'
    with pytest.raises(ValueError):reports.save(db,report_id,{**scope,'geo':'PL'},[],'test')


def test_filter_change_after_preview_rejects_start_and_scope_change_blocks_worker(pool,monkeypatch):
    from fastapi import HTTPException
    db,source,target,remotes,add=pool
    filters={'brand':'Pin-Up','geo':'AZ'}
    preview=api.preview_batch(api.BatchPreview(site_ids=[source.id,target.id],filter=filters),{'username':'test'},db)
    p=preview['plans'][0]
    payload=api.BatchStart(batch_id=preview['batch_id'],filter={**filters,'include_general':True},items=[api.StartItem(site_id=p['site_id'],request_id=uuid4(),preview_token=p['preview_token'])])
    with pytest.raises(HTTPException):api.start(payload,{'username':'test'},db)
    payload.filter=MassActionFilter.model_validate(filters)
    monkeypatch.setattr(api,'dispatch',lambda *args:None)
    result=api.start(payload,{'username':'test'},db)
    run=db.get(models.AutoReglueRun,result['results'][0]['run']['id'])
    source.brand=target.brand='Other';db.commit()
    auto.execute(db,run.id)
    assert run.status in {'failed','partial'}
    assert not remotes[source.id].calls and not remotes[target.id].calls


def test_nonbatch_report_is_idempotent_and_does_not_claim_planned_values_as_actual(pool,monkeypatch):
    db,source,target,remotes,add=pool
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='within_network'))
    request_id=uuid4()
    def prepare(db,site,request_id,token,actor,scope):
        existing=db.get(models.AutoReglueRun,str(request_id))
        if existing:return existing,False
        run=models.AutoReglueRun(id=str(request_id),site_id=site.id,initiator=actor,status='queued',phase='prepared',plan={
            'project':site.name,'old_main':'old.test','new_main':'planned.test',
            'old_fake_main_path':'/old/','new_fake_main_path':'/planned/',
            'mass_filter':db.info['mass_action_filter']})
        db.add(run);db.commit()
        return run,True
    monkeypatch.setattr(auto,'prepare_run',prepare)
    sent=[];monkeypatch.setattr(api,'dispatch',lambda db,run:sent.append(run.id))
    payload=api.BatchStart(filter={'brand':'Pin-Up','geo':'AZ'},items=[api.StartItem(site_id=target.id,request_id=request_id,preview_token='a'*64)])
    api.start(payload,{'username':'test'},db)
    api.start(payload,{'username':'test'},db)
    values=reports.list_reports(db,'Pin-Up','AZ')
    assert len(values)==1 and len(sent)==1
    entry=values[0]['entries'][0]
    assert entry['old_fake_main_path']=='/old/' and entry['new_fake_main_path'] is None
    assert entry['new_main'] is None and entry['confirmed_at'] is None
