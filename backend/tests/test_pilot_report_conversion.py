from copy import deepcopy
from uuid import uuid4
import pytest
from app import models, maintenance_reports, auto_pilot, mass_reglue_launch as launch, pilot_variations
from app.pilot_report_conversion import convert, build_preserved
from app.project_network import NetworkConflict
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_auto_pilot import preview, USER

SHARES=dict(subdomains=100,without_alternates=0,redirects=0,title_h1=0,paragraphs=50,internal_pages=0)

def saved_report(db):
    source=preview(db)
    plan=deepcopy(next(p for g in source.result['groups'] for p in g.get('plans',[])))
    job=maintenance_reports.upsert(db,str(uuid4()),'Saved plan','test',[plan['site_id']],[{'site_id':plan['site_id'],'status':'waiting','plan':plan}],status='partial')
    job.payload={**job.payload,'planning_only':True,'excluded_site_ids':['removed'],'excluded_projects':[{'site_id':'removed','project':'removed.test'}]};db.commit()
    return job,plan


def test_conversion_preserves_identity_targets_exclusions_and_history(pool,monkeypatch):
    db,source,target,remotes,add=pool
    job,plan=saved_report(db);old=deepcopy(job.result);identity=job.id
    convert(db,job.id,USER,percentages=SHARES)
    assert job.id==identity and job.kind==launch.PREVIEW_KIND
    assert job.payload['percentages']['paragraphs']==50
    assert job.payload['preserved_target_plans'][plan['site_id']]['new_main']==plan['new_main']
    assert job.payload['excluded_site_ids']==['removed']
    assert db.get(models.AutoReglueConfig,job.payload['maintenance_archive_key']).value['result']==old
    assert convert(db,job.id,USER,percentages=SHARES).id==identity
    monkeypatch.setattr(pilot_variations,'allocate_subdomains',lambda *a,**k:pytest.fail('Pinned domains must never be replaced'))
    monkeypatch.setattr(pilot_variations,'prepare_titles',lambda db,job,result:result.update(variations_finalized=True))
    launch.execute_step(db,job.id,lambda _:pytest.fail('Planning cannot execute'))
    assert job.status=='completed'
    actual=[p for g in job.result['groups'] for p in g.get('plans',[])]
    assert [p['new_main'] for p in actual]==[plan['new_main']]
    assert actual[0]['rewrite_paragraphs'] is True
    assert all(not r.calls for r in remotes.values())


def test_executed_report_cannot_be_converted(pool):
    db,source,target,remotes,add=pool
    job,plan=saved_report(db)
    result=deepcopy(job.result);result['entries'][0]['run_id']=str(uuid4());job.result=result;db.commit()
    with pytest.raises(NetworkConflict):convert(db,job.id,USER,percentages=SHARES)
    assert job.kind==maintenance_reports.KIND


def test_missing_pinned_domain_is_reported_without_substitution(pool):
    db,source,target,remotes,add=pool
    job,plan=saved_report(db);convert(db,job.id,USER,percentages=SHARES)
    pinned=job.payload['preserved_target_plans'][plan['site_id']]
    remotes[pinned['source_site_id']].data['settings']['domains'].remove(pinned['new_main'])
    result=build_preserved(db,job,[db.get(models.Site,plan['site_id'])])
    assert result['plans']==[]
    assert 'больше не находится' in result['skipped'][0]['error']
    assert job.payload['preserved_target_plans'][plan['site_id']]['new_main']==plan['new_main']
    assert all(not r.calls for r in remotes.values())


def test_old_report_link_redirects_and_archive_keeps_saved_evidence(pool):
    from app.auto_reglue_api import maintenance_report
    from uuid import UUID
    db,source,target,remotes,add=pool
    job,plan=saved_report(db);old=deepcopy(job.result)
    convert(db,job.id,USER,percentages=SHARES)
    assert maintenance_report(UUID(job.id),USER,db)['pilot_report_url']==f'/auto-reglue/pilot?id={job.id}'
    archive=maintenance_report(UUID(job.id),USER,db,archive=True)
    assert archive['entries'][0]['plan']==old['entries'][0]['plan']
    assert archive['can_exclude'] is False


def test_replanning_retains_pinned_targets_and_applies_new_content_percentage(pool,monkeypatch):
    from app.pilot_replanning import request
    from app.pilot_scope import selection
    db,source,target,remotes,add=pool
    job,plan=saved_report(db);convert(db,job.id,USER,percentages=SHARES)
    request(db,job.id,uuid4(),USER,scope=selection(),percentages={**SHARES,'paragraphs':0},title_rewrite_mode='minimal')
    monkeypatch.setattr(pilot_variations,'allocate_subdomains',lambda *a,**k:pytest.fail('Pinned targets must remain'))
    monkeypatch.setattr(pilot_variations,'prepare_titles',lambda db,job,result:result.update(variations_finalized=True))
    launch.execute_step(db,job.id,lambda _:pytest.fail('Planning cannot execute'))
    actual=[p for g in job.result['groups'] for p in g.get('plans',[])]
    assert [p['new_main'] for p in actual]==[plan['new_main']]
    assert actual[0]['rewrite_paragraphs'] is False
    assert job.payload['maintenance_archive_key']
