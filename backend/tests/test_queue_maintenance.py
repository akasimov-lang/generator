import json
from datetime import datetime,timezone
from uuid import uuid4
from app import models
from app.queue_maintenance import cleanup, inflight_job_ids
from test_project_network import env

class Broker:
    def __init__(self,data):self.data=data;self.removed=[];self.backups=[]
    def lrange(self,key,*args):return self.data.get(key,[])
    def rpush(self,key,value):self.backups.append((key,value))
    def expire(self,*args):pass
    def lrem(self,key,count,raw):self.removed.append((key,raw));self.data[key].remove(raw)

def message(id,task='app.worker.background_operation'):
    return json.dumps({'headers':{'id':id,'task':task}}).encode()


def test_cleanup_preserves_one_pending_delivery_and_active_work(env):
    db,site,_=env
    pending=models.BackgroundJob(kind='site_template',payload={},status='queued')
    running=models.BackgroundJob(kind='publication',payload={},status='running')
    completed=models.BackgroundJob(kind='cache_sync',payload={},status='completed')
    db.add_all([pending,running,completed]);db.commit()
    client=Broker({'generation':[message(pending.id),message(pending.id),message(running.id),message(completed.id)]})
    result=cleanup(db,client)
    assert result['removed_messages']==2 and not client.removed
    result=cleanup(db,client,apply=True)
    assert result['removed_messages']==2 and len(client.backups)==2
    assert client.data['generation']==[message(pending.id),message(running.id)]
    assert pending.status=='queued' and running.status=='running'


def test_obsolete_retry_is_cancelled_without_regenerating_published_text(env):
    db,site,_=env
    task=models.GenerationTask(title='Already published',geo='DE',language='de',topics_count=1)
    db.add(task);db.flush()
    item=models.ContentItem(task_id=task.id,site_id=site.id,topic='Done',slug='done',status='published',generated_json={},idempotency_key=str(uuid4()))
    db.add(item);db.flush()
    retry=models.BackgroundJob(kind='generation_retry',payload={'content_id':item.id},status='queued',error='old error')
    db.add(retry);db.commit()
    client=Broker({'generation':[message(retry.id)]})
    assert cleanup(db,client,apply=True)['obsolete_retry_jobs']==1
    assert retry.status=='cancelled' and retry.result['queue_cleanup']['previous_error']=='old error'
    assert item.status=='published' and client.data['generation']==[]


def test_cleanup_moves_waiting_menu_jobs_ahead_of_long_text_backlog(env):
    db,site,_=env
    job=models.BackgroundJob(kind='menu_generation',payload={'site_id':site.id},status='queued')
    db.add(job);db.commit()
    client=Broker({'generation':[message(job.id),message(job.id)]})
    sent=[]
    result=cleanup(db,client,apply=True,send=lambda *args:sent.append(args))
    assert result['rerouted_jobs']==1 and sent==[(job.id,'short_generation')]
    assert client.data['generation']==[] and job.status=='queued'
