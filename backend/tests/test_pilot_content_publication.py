from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app import models, pilot_content_publication as content, reglue_content, pilot_text_jobs, pilot_streaming
from test_project_network import env
from test_project_pages import setup


def workflow(db,site):
    plan={'site_id':site.id,'project':site.name,'old_main':'main.test','new_main':'next.test',
          'rewrite_title_h1':True,'rewrite_paragraphs':True,'title_rewrite_mode':'minimal','preview_token':'token'}
    parent=models.BackgroundJob(kind='mass_reglue_list',status='queued',payload={'manual_start':True,'streaming_start':True,'site_ids':[site.id],'actor':'test','allowed':None},
        result={'groups':[{'site_ids':[site.id],'plans':[plan],'filter':{},'status':'prepared'}],
                'items':{site.id:{'site_id':site.id,'project':site.name,'status':'pending'}},'sent':{}})
    db.add(parent);db.flush()
    run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='test',status='queued',phase='prepared',plan={**plan,'list_launch_id':parent.id})
    db.add(run);db.commit()
    return parent,run


def test_network_does_not_wait_for_unfinished_generation_in_launched_plan(env,monkeypatch):
    db,site,_=env;parent,run=workflow(db,site)
    monkeypatch.setattr('app.reglue_title_h1.finish',lambda *args,**kwargs:pytest.fail('must not generate or save inline'))
    assert reglue_content.before_network(db,run,{'canon':'main.test'})
    assert reglue_content.before_network(db,run,{'canon':'main.test'})
    assert len(content.states(db,parent.id))==2 and run.phase=='prepared'
    assert all(job.status=='queued' for job in content.states(db,parent.id))


def test_read_only_plan_cannot_opt_into_network_execution(env,monkeypatch):
    db,site,_=env;parent,run=workflow(db,site)
    parent.kind='auto_pilot_preview';db.commit()
    assert not content.attach(db,run) and content.states(db,parent.id)==[]


def test_text_job_remains_current_after_its_network_run_has_started(env):
    db,site,_=env;parent,run=workflow(db,site)
    result=deepcopy(parent.result);result['items'][site.id].update(run_id=run.id,status='completed');parent.result=result;db.commit()
    plan=parent.result['groups'][0]['plans'][0]
    child=models.BackgroundJob(kind='pilot_text',payload={'parent_id':parent.id,'site_id':site.id,
        'generation_id':parent.id,'fingerprint':pilot_text_jobs.fingerprint(plan)})
    db.add(child);db.commit()
    assert pilot_text_jobs.current(db,child) is parent


def test_publisher_waits_for_reviewed_generation_without_calling_provider(env,monkeypatch):
    db,site,_=env;parent,run=workflow(db,site);content.attach(db,run);db.commit()
    monkeypatch.setattr('app.auto_pilot.heading_mode_ready',lambda *args:False)
    monkeypatch.setattr('app.reglue_title_h1.finish',lambda *args,**kwargs:pytest.fail('not ready'))
    job=next(j for j in content.states(db,parent.id) if j.payload['field']=='title_h1')
    assert content.execute(db,job.id)=={'status':'waiting_generation'}
    assert run.phase=='prepared' and run.status=='queued'


def test_publication_status_does_not_overwrite_confirmed_reglue(env,monkeypatch):
    db,site,_=env;parent,run=workflow(db,site)
    result=deepcopy(parent.result);result['groups'][0]['plans'][0]['title_h1_preview']={'draft_id':'ready'};parent.result=result
    run.status='completed';run.phase='completed';content.attach(db,run);db.commit()
    monkeypatch.setattr('app.auto_pilot.heading_mode_ready',lambda *args:True)
    calls=[]
    def finish(db,work,**kwargs):
        calls.append(work.id);work.status='waiting';work.phase='title_h1';work.message='Waiting for receipt';return False
    monkeypatch.setattr('app.reglue_title_h1.finish',finish)
    job=next(j for j in content.states(db,parent.id) if j.payload['field']=='title_h1')
    assert content.execute(db,job.id)=={'status':'queued'}
    assert run.status=='completed' and run.phase=='completed'
    row={'site_id':site.id,'status':'completed'};content.merge_row(db,parent,row)
    assert row['status']=='running' and row['reglue_status']=='completed'
    def confirmed(db,work,**kwargs):work.plan={**work.plan,'title_h1_edit_id':'receipt'};return True
    monkeypatch.setattr('app.reglue_title_h1.finish',confirmed)
    assert content.execute(db,job.id)=={'status':'completed'}
    assert run.plan['title_h1_edit_id']=='receipt' and run.status=='completed'
    assert content.execute(db,job.id)=={'status':'skipped'}


def test_foreign_main_change_blocks_content_publication(env,monkeypatch):
    db,site,remote=env;parent,run=workflow(db,site)
    result=deepcopy(parent.result);result['groups'][0]['plans'][0]['title_h1_preview']={'draft_id':'ready'};parent.result=result
    content.attach(db,run);db.commit()
    remote.data['settings']['canon']='foreign.test'
    monkeypatch.setattr('app.auto_pilot.heading_mode_ready',lambda *args:True)
    monkeypatch.setattr('app.reglue_title_h1.finish',lambda *args,**kwargs:pytest.fail('foreign Main'))
    job=next(j for j in content.states(db,parent.id) if j.payload['field']=='title_h1')
    assert content.execute(db,job.id)=={'status':'failed'}
    assert 'вне этого запуска' in job.error and remote.calls==[]


def test_streaming_dispatches_prepared_network_while_texts_are_generating(env,monkeypatch):
    db,site,_=env;parent,run=workflow(db,site)
    monkeypatch.setattr('app.pilot_weekly.exclude',lambda *args,**kwargs:False)
    monkeypatch.setattr('app.mass_action_scope.constrain',lambda *args:None)
    monkeypatch.setattr('app.mass_reglue_launch.skip_reason',lambda *args:None)
    monkeypatch.setattr('app.pilot_versions.append_version',lambda *args:None)
    monkeypatch.setattr('app.auto_reglue.prepare_run',lambda *args,**kwargs:(run,True))
    sent=[]
    pilot_streaming.execute(db,parent,sent.append)
    assert sent==[run.id] and parent.status=='queued'
    assert len(content.states(db,parent.id))==2
    assert parent.result['items'][site.id]['run_id']==run.id


def test_ready_heading_uses_real_save_receipt_and_preserves_network_outcome(setup,monkeypatch):
    from app import project_pages as pages
    _,db,site,remote=setup
    parent,run=workflow(db,site)
    home=deepcopy(remote['project']['data']['pages'][1])
    changed=deepcopy(home['content'])
    changed['blocks'].append({'type':'header','data':{'level':1,'text':'Updated home heading'}})
    draft=models.ProjectPageDraft(site_id=site.id,page_key=pages.page_key(home),requested_by='test',
        action='auto_title_h1',status='ready',input_content=home['content'],result_content=changed,
        input_metadata={'title':home['title'],'description':home['description'],'revision':pages.digest(home)},
        result_metadata={'title':'Brand Home updated','description':home['description'],'revision':pages.digest(home)})
    db.add(draft);db.flush()
    result=deepcopy(parent.result)
    result['groups'][0]['plans'][0].update(rewrite_paragraphs=False,title_h1_preview={'draft_id':draft.id,'title_after':'Brand Home updated','mode':'minimal'})
    parent.result=result
    run.plan={**run.plan,'rewrite_paragraphs':False};run.status='completed';run.phase='completed'
    content.attach(db,run);db.commit()
    monkeypatch.setattr('app.project_network.read_network',lambda *args:{'canon':'main.test'})
    monkeypatch.setattr('app.services.call_gemini',lambda *args:pytest.fail('Publication never regenerates'))
    job=content.states(db,parent.id)[0]
    assert content.execute(db,job.id)=={'status':'completed'}
    assert remote['project']['data']['pages'][1]['title']=='Brand Home updated'
    assert remote['project']['data']['pages'][1]['banners']==home['banners']
    assert run.status=='completed' and run.phase=='completed'
    assert db.get(models.ProjectPageEdit,run.plan['title_h1_edit_id']).status=='confirmed'
    content.execute(db,job.id)
    assert len(remote['requests'])==1


def test_text_sync_does_not_change_reserved_network_manifest(env):
    from app.cross_reglue_batch import key, authorize
    db,site,_=env;parent,run=workflow(db,site)
    result=deepcopy(parent.result);plan=result['groups'][0]['plans'][0]
    plan.update(local_target=True,source_site_id=site.id,batch_id=str(uuid4()),rewrite_paragraphs=False,title_h1_preview=None)
    original=deepcopy(plan)
    result['groups'][0]['batch_id']=plan['batch_id'];result['items'][site.id]['run_id']=run.id
    parent.result=result;run.plan={**plan,'list_launch_id':parent.id}
    ledger=models.AutoReglueConfig(key=key(plan['batch_id']),value={'plans':[deepcopy(plan)],'run_ids':{site.id:run.id}})
    child=models.BackgroundJob(id=pilot_text_jobs.identity(parent,plan,'title_h1'),kind='pilot_text',status='completed',payload={},
        result={'preview':{'draft_id':str(uuid4())}})
    db.add_all([ledger,child]);db.commit()
    pilot_text_jobs.sync(db,parent,result)
    assert ledger.value['plans']==[original]
    run.plan={**run.plan,'title_h1_preview':result['groups'][0]['plans'][0]['title_h1_preview']}
    authorize(db,run)
    run.plan={**run.plan,'new_main':'unapproved.test'}
    with pytest.raises(ValueError,match='план распределения изменён'):authorize(db,run)


def test_failed_content_is_partial_in_report_metadata(env):
    from app.pilot_internal_pages import report_metadata
    db,site,_=env;parent,run=workflow(db,site);content.attach(db,run)
    parent.status='completed'
    for job in content.states(db,parent.id):job.status='failed'
    db.commit()
    assert report_metadata(db,parent)['status']=='partial'
