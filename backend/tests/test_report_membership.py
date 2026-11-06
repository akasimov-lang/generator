from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app import report_membership, report_status, maintenance_reports, auto_pilot
from app.project_network import NetworkConflict
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_auto_pilot import preview, USER


def test_plan_completion_is_not_execution_completion():
    job=SimpleNamespace(kind='auto_pilot_preview',status='completed',payload={},finished_at='2026-11-06T12:00:00Z')
    result=report_status.metadata(job,finished_at=job.finished_at)
    assert result['display_status']=='План готов'
    assert result['finished_at'] is None
    assert result['planning_finished_at']==job.finished_at


def test_finished_rows_resolve_stale_running_status():
    job=SimpleNamespace(kind='maintenance_report',status='running',payload={},result={'entries':[
        {'status':'completed','finished_at':'2026-11-06T12:00:00Z'},
        {'status':'failed','finished_at':'2026-11-06T12:03:00Z'}]})
    result=report_status.metadata(job)
    assert result['display_status']=='Выполнено частично'
    assert result['finished_at']=='2026-11-06T12:03:00Z'


def test_active_rows_do_not_show_end_date():
    job=SimpleNamespace(kind='maintenance_report',status='partial',payload={},result={'entries':[{'status':'waiting'}]})
    result=report_status.metadata(job,finished_at='2026-11-06T12:00:00Z')
    assert result['display_status']=='Выполняется'
    assert result['finished_at'] is None


def test_exclusion_preserves_plan_audit_and_blocks_donor_dependency(pool):
    db,source,target,remotes,add=pool
    job=maintenance_reports.upsert(db,str(uuid4()),'Plan','test',[source.id,target.id],[
        {'site_id':source.id,'status':'waiting','plan':{'new_main':'next.test'}},
        {'site_id':target.id,'status':'waiting','plan':{'source_site_id':source.id},'planning_status':'ready'}],status='partial')
    job.payload={**job.payload,'planning_only':True,'planning_finished_at':'2026-11-06T12:00:00Z'};db.commit()
    before=deepcopy(job.result['entries'][0])
    report_membership.exclude(db,job.id,source.id,USER)
    assert job.payload['site_ids']==[target.id]
    assert job.payload['excluded_projects'][0]['entry']==before
    assert job.result['entries'][0]['planning_status']=='blocked'
    report_membership.exclude(db,job.id,source.id,USER)
    assert len(job.payload['excluded_projects'])==1
    assert all(not r.calls for r in remotes.values())
    with pytest.raises(ValueError):maintenance_reports.get(db,job.id,{'username':'test','allowed_site_ids':[target.id]})


def test_preview_exclusion_replans_remaining_scope_and_cannot_start_stale_plan(pool):
    db,source,target,remotes,add=pool
    job=preview(db);old=deepcopy(job.result)
    report_membership.exclude(db,job.id,source.id,USER)
    assert source.id not in job.payload['site_ids']
    assert job.payload['excluded_projects'][0]['previous_result']==old
    assert job.status=='queued'
    assert not any(g.get('plans') for g in job.result['groups'])
    with pytest.raises(NetworkConflict):auto_pilot.start(db,job.id,USER)
    with pytest.raises(ValueError):auto_pilot.get(db,job.id,{'username':'test','allowed_site_ids':job.payload['site_ids']})
    assert all(not r.calls for r in remotes.values())
