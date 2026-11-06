from copy import deepcopy
from uuid import uuid4

from app import models, mass_reglue_launch as launch
from app.pilot_error_recovery import retry_former_main_rows
from test_project_network import env


def test_retry_selects_only_matching_unstarted_rows_and_preserves_targets(env):
    db, site, remote = env
    wanted, other, completed, started = [str(uuid4()) for _ in range(4)]
    error = 'Выбранный домен уже использовался как Main в этой сетке.'
    rows = {
        wanted: {'status': 'failed', 'reason': error},
        other: {'status': 'failed', 'reason': 'БАН'},
        completed: {'status': 'completed', 'reason': error},
        started: {'status': 'failed', 'reason': error, 'run_id': str(uuid4())},
    }
    plans = [{'site_id': sid, 'new_main': sid + '.test'} for sid in rows]
    job = models.BackgroundJob(id=str(uuid4()), kind=launch.KIND, status='completed',
        payload={'streaming_start': True},
        result={'items': rows, 'groups': [{'site_ids': list(rows), 'status': 'done', 'plans': plans}]})
    db.add(job); db.commit()
    before = deepcopy(job.result)
    receipt = retry_former_main_rows(db, job.id, 'test')
    assert receipt['retried'] == [wanted]
    assert job.status == 'queued' and job.result['items'][wanted]['status'] == 'pending'
    assert job.result['groups'][0]['plans'] == before['groups'][0]['plans']
    assert job.result['items'][other] == before['items'][other]
    assert job.result['items'][completed] == before['items'][completed]
    assert job.result['items'][started] == before['items'][started]
    assert db.get(models.AutoReglueConfig, receipt['backup_key']).value['result_before'] == before
    assert retry_former_main_rows(db, job.id, 'test')['retried'] == []


def test_transient_recovery_reuses_alternative_identity_and_leaves_real_errors(env):
    from app.pilot_error_recovery import retry_transient_rows
    from app.pilot_row_replan import run_id
    db,site,_=env
    wanted,invalid,done,started=[str(uuid4()) for _ in range(4)]
    reason='С сеткой уже выполняется операция. Обновите данные через несколько секунд.'
    plans=[{'site_id':sid,'new_main':sid+'.test','pilot_alternative_id':str(uuid4())} for sid in [wanted,invalid,done,started]]
    rows={wanted:{'status':'failed','reason':reason},invalid:{'status':'failed','reason':'Домен отмечен БАН'},done:{'status':'completed','reason':reason},started:{'status':'failed','reason':reason}}
    job=models.BackgroundJob(id=str(uuid4()),kind=launch.KIND,status='completed',payload={'streaming_start':True},result={'items':rows,'groups':[{'site_ids':list(rows),'plans':plans,'status':'done'}]})
    db.add(job);db.flush()
    db.add(models.AutoReglueRun(id=run_id(job,plans[-1]),site_id=site.id,initiator='test',status='waiting',plan=plans[-1]));db.commit()
    before=deepcopy(job.result)
    assert retry_transient_rows(db,job.id,'test')['retried']==[wanted]
    assert job.result['groups'][0]['plans']==before['groups'][0]['plans']
    assert job.result['items'][invalid]==before['items'][invalid]
    assert job.result['items'][done]==before['items'][done]
    assert job.result['items'][started]==before['items'][started]
    assert retry_transient_rows(db,job.id,'test')['retried']==[]


def test_transient_recovery_requeues_unstarted_receipt_instead_of_creating_another(env):
    from app.pilot_error_recovery import retry_transient_rows
    from app.pilot_row_replan import run_id
    db,site,_=env
    plan={'site_id':site.id,'new_main':'next.test'};reason='Одна из сеток уже участвует в другом запуске.'
    parent=models.BackgroundJob(id=str(uuid4()),kind=launch.KIND,status='completed',payload={'streaming_start':True},result={'items':{site.id:{'status':'failed','reason':reason}},'groups':[{'site_ids':[site.id],'plans':[plan],'status':'done'}]})
    db.add(parent);db.flush()
    run=models.AutoReglueRun(id=run_id(parent,plan),site_id=site.id,initiator='test',status='failed',phase='prepared',message=reason,plan=plan)
    db.add(run);db.commit()
    assert retry_transient_rows(db,parent.id,'test')['retried']==[site.id]
    assert run.status=='queued' and parent.result['items'][site.id]['run_id']==run.id
    assert retry_transient_rows(db,parent.id,'test')['retried']==[]
