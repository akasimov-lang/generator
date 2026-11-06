from uuid import uuid4
from copy import deepcopy
from app import models, report_evidence as evidence, maintenance_reports
from test_project_network import env


def test_observed_current_state_never_becomes_completed_result(env):
    db,site,remote=env
    observed=evidence.capture(db,site,{**remote.data,'data':{'pages':[{'slug':'/','title':'Current title','description':'Current description','content':{}}]}})
    db.commit()
    rows=[{'site_id':site.id,'before':{'title':'Historical title'},'plan':{'new_main':'planned.test'}}]
    evidence.enrich(db,rows)
    assert rows[0]['current_observation']['values']['title']=='Current title'
    assert rows[0]['before']['title']=='Historical title'
    assert 'after' not in rows[0]
    assert observed['source']=='cache'


def test_new_report_freezes_baseline_before_current_observation_changes(env):
    db,site,remote=env
    evidence.capture(db,site,remote.data);db.commit()
    job=maintenance_reports.upsert(db,str(uuid4()),'Plan','test',[site.id])
    before=deepcopy(job.result['entries'][0]['before'])
    changed=deepcopy(remote.data);changed['settings']['canon']='changed.test'
    evidence.capture(db,site,changed);db.commit()
    row=maintenance_reports.view(job,db)['entries'][0]
    assert row['before']==before
    assert row['current_observation']['values']['main']=='changed.test'
    assert not row.get('after')


def test_confirmed_run_fills_after_but_not_from_plan_or_other_site(env):
    db,site,remote=env
    run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='test',status='completed',plan={'old_main':'old.test','new_main':'planned.test','applied_result':{'new_main':'actual.test','confirmed_at':'2026-11-06T12:00:00Z','alternateMarkup':''}})
    db.add(run);db.commit()
    rows=[{'site_id':site.id,'run_id':run.id},{'site_id':'other','run_id':run.id}]
    evidence.enrich(db,rows)
    assert rows[0]['after']['main']=='actual.test'
    assert rows[0]['after']['alternates']==''
    assert 'after' not in rows[1]


def test_partial_data_refresh_preserves_network_observation(env):
    db,site,remote=env
    evidence.capture(db,site,remote.data);db.commit()
    observed=evidence.capture(db,site,{'data':{'pages':[{'slug':'/','title':'New title'}]}},source='webdev')
    assert observed['values']['main']=='main.test'
    assert observed['values']['title']=='New title'


def test_saved_network_snapshot_restores_missing_before_fields(env):
    db,site,remote=env
    rows=[{'site_id':site.id,'before':{'main':'old.test'},'source_state':{'canon':'old.test','alternateMarkup':'saved markup','canonicalFakeMainMarkup':'saved canonical','fake_main_current':'/old/'}}]
    evidence.enrich(db,rows)
    assert rows[0]['before']=={'main':'old.test','alternates':'saved markup','canonical':'saved canonical','fake_path':'/old/'}
