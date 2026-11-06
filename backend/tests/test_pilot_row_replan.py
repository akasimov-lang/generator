from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, auto_pilot as pilot, auto_reglue as auto, mass_reglue_launch as launch
from app import pilot_row_replan as replan
from app.job_queues import queue_for
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_pilot_variations import make_preview, USER


@pytest.fixture
def launched(pool,monkeypatch):
    monkeypatch.setattr('app.reglue_title_h1.prepare_for_plan',lambda *a,**k:None)
    db,sites,remotes,job=make_preview(pool,2)
    job.kind=launch.KIND;job.status='completed'
    job.payload={**job.payload,'manual_start':True,'launched_at':datetime.now(timezone.utc).isoformat(),'streaming_start':True}
    result=deepcopy(job.result)
    for row in result['items'].values():row.update(status='skipped',reason='Дропы из хранилища выключены для этого плана.')
    job.result=result;db.commit()
    return db,sites,remotes,job


def test_prepare_after_launch_is_durable_idempotent_and_has_no_remote_writes(launched,monkeypatch):
    db,sites,remotes,parent=launched;site=sites[0];before=deepcopy(parent.result);request=uuid4()
    calls=[]
    def metadata(db,plan,request_id,**options):
        calls.append((plan['site_id'],options))
        plan['title_h1_preview']={'title_before':'old','title_after':'New title','h1_before':'old','h1_after':'New H1'}
    monkeypatch.setattr('app.reglue_title_h1.prepare_for_plan',metadata)
    replan.request(db,parent.id,site.id,request,USER)
    replan.request(db,parent.id,site.id,request,USER)
    child=db.get(models.BackgroundJob,str(request))
    assert queue_for(db,child)=='planning'
    assert replan.execute(db,child.id)['phase']=='headings'
    assert queue_for(db,child)=='short_generation' and not calls
    assert replan.execute(db,child.id)['status']=='completed',child.error
    assert len(calls)==1 and calls[0][1]['force']
    assert parent.result['groups']==before['groups']
    assert parent.result['items'][sites[1].id]==before['items'][sites[1].id]
    assert child.result['plan']['local_target'] and not child.result['plan'].get('reserve_pool_id')
    assert parent.result['items'][site.id]['alternative']['status']=='ready'
    assert not list(db.scalars(select(models.AutoReglueRun)))
    assert all(not r.calls for r in remotes.values())
    replan.execute(db,child.id)
    assert len(calls)==1


def test_start_alternative_changes_only_selected_row_and_uses_new_run_identity(launched):
    db,sites,remotes,parent=launched;site=sites[0];before=deepcopy(parent.result)
    request=uuid4();replan.request(db,parent.id,site.id,request,USER)
    replan.execute(db,str(request));replan.execute(db,str(request))
    child=db.get(models.BackgroundJob,str(request));assert child.status=='completed',child.error
    replan.start(db,parent.id,site.id,request,USER)
    selected=next(p for g in parent.result['groups'] for p in g.get('plans',[]) if p['site_id']==site.id)
    assert parent.status=='queued' and parent.result['items'][site.id]['status']=='ready'
    assert parent.result['items'][sites[1].id]==before['items'][sites[1].id]
    assert parent.result['alternative_history'][0]['row']['reason']==before['items'][site.id]['reason']
    expected=replan.run_id(parent,selected)
    from uuid import uuid5,UUID
    assert expected!=str(uuid5(UUID(parent.id),site.id))
    run=models.AutoReglueRun(id=expected,site_id=site.id,initiator=USER['username'],status='queued',plan={**selected,'list_launch_id':parent.id})
    assert launch.manual_pilot_allowed(db,site.id,run)
    count=len(parent.result['alternative_history'])
    replan.start(db,parent.id,site.id,request,USER)
    assert len(parent.result['alternative_history'])==count
    assert all(not r.calls for r in remotes.values())


def test_completed_project_cannot_be_replanned(launched):
    db,sites,remotes,parent=launched;result=deepcopy(parent.result)
    result['items'][sites[0].id]['status']='completed';parent.result=result;db.commit()
    with pytest.raises(ValueError,match='уже выполнен'):
        replan.request(db,parent.id,sites[0].id,uuid4(),USER)
    assert all(not r.calls for r in remotes.values())


def test_foreign_request_cannot_start_an_alternative(launched):
    db,sites,remotes,parent=launched
    request=uuid4();replan.request(db,parent.id,sites[0].id,request,USER)
    replan.execute(db,str(request));replan.execute(db,str(request))
    with pytest.raises(ValueError,match='не найден'):
        replan.start(db,parent.id,sites[1].id,request,USER)


def test_alternative_dispatch_ignores_historical_skipped_donor_row(launched):
    db,sites,remotes,parent=launched;target,source=sites
    remote=remotes[target.id]
    remote.data['settings']['domains']=[target.cache_canon]
    request=uuid4();replan.request(db,parent.id,target.id,request,USER)
    replan.execute(db,str(request));replan.execute(db,str(request))
    child=db.get(models.BackgroundJob,str(request))
    assert child.status=='completed',child.error
    assert child.result['plan']['source_site_id']==source.id
    donor_before=deepcopy(parent.result['items'][source.id])
    replan.start(db,parent.id,target.id,request,USER)
    sent=[]
    launch.execute_step(db,parent.id,sent.append)
    assert len(sent)==1,parent.result['items'][target.id]
    run=db.get(models.AutoReglueRun,sent[0])
    assert run.site_id==target.id and run.status=='queued'
    assert parent.result['items'][source.id]==donor_before
    assert remotes[source.id].data['settings']['canon']==source.cache_canon


def test_bulk_replan_keeps_reviewed_headings_without_forcing_generation(launched,monkeypatch):
    db,sites,remotes,parent=launched
    site=sites[0];result=deepcopy(parent.result)
    old=next(p for g in result['groups'] for p in g.get('plans',[]) if p['site_id']==site.id)
    old.update(rewrite_title_h1=True,title_h1_preview={'draft_id':'saved-heading','title_after':'Kept title','h1_after':'Kept H1'})
    parent.result=result;db.commit()
    # The restore guard is separately covered by test_pilot_saved_headings.
    def restore(db,result,plan):
        saved=result['saved_project_headings'][site.id]
        plan['title_h1_preview']=deepcopy(saved['title_h1_preview'])
    monkeypatch.setattr('app.pilot_saved_headings.restore',restore)
    calls=[]
    def metadata(db,plan,request_id,**options):
        calls.append(options)
        assert plan['title_h1_preview']==old['title_h1_preview']
    monkeypatch.setattr('app.reglue_title_h1.prepare_for_plan',metadata)
    request=uuid4();replan.request(db,parent.id,site.id,request,USER,regenerate_metadata=False)
    replan.execute(db,str(request));replan.execute(db,str(request))
    child=db.get(models.BackgroundJob,str(request))
    assert child.status=='completed',child.error
    assert calls==[{'force':False}]
    assert all(not r.calls for r in remotes.values())


def test_donor_reglued_this_week_can_supply_multiple_recipients(launched):
    from app.pilot_weekly import exclusions
    db,sites,_,_=launched;target,donor=sites
    donor.last_reglue_at=datetime.now(timezone.utc);target.last_reglue_at=None;db.commit()
    assert exclusions(db,[{'site_id':target.id,'source_site_id':donor.id,'new_main':'free.test'}])=={}


def test_recipient_reglued_this_week_still_cannot_restart(launched):
    from app.pilot_weekly import exclusions
    db,sites,_,_=launched;target,donor=sites
    target.last_reglue_at=datetime.now(timezone.utc);db.commit()
    result=exclusions(db,[{'site_id':target.id,'source_site_id':donor.id}])
    assert 'уже переклеен' in result[target.id]
