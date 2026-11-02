"""Explicit report reconciliation and one receipted add retry for missing domains."""
from contextlib import ExitStack
from datetime import datetime,timezone
from uuid import UUID,uuid5
import time
import httpx
from sqlalchemy import select
from app import models,project_network as network,cross_reglue as cross,domain_redistribution as move
from app import mass_action_reports as reports,domain_transfer_queue as queue
from app.domain_transfer_policy import banned_domains,require_main_destination,require_non_project_domain,policy_key
from app.mass_action_scope import MassActionFilter,matches

KIND='transfer_report_check'
POLL_ATTEMPTS=8
POLL_SECONDS=2

def names(run):return [d['domain'] for d in run.plan.get('domains',[])] or [run.plan.get('new_main')]
def retry_key(request_id):return 'transfer-retry:'+str(request_id)
def retry_id(job,run):return str(uuid5(UUID(job.id),'retry:'+run.id))
def deletion_operations(db,run):
 actions=move.deletion_actions(run) if run.plan.get('execution_mode')=='transfer_only' else ['delete_domain']
 return [db.get(models.NetworkOperation,move.receipt(run,a) if run.plan.get('execution_mode')=='transfer_only' else cross.receipt_id(run,a)) for a in actions]
def deletion_ready(db,run,source,domains=None):
 selected=set(domains or names(run))
 for op in deletion_operations(db,run):
  if op is None or op.site_id!=source.id:return False
  relevant=selected.intersection(op.request_payload.get('domains',[]))
  if not relevant:continue
  try:
   if cross.completed_job(db,source,op):continue
  except ValueError:
   with network.Remote(db,source) as remote:job=remote.job_state(op.request_payload.get('job_id'))
   result=(job or {}).get('result') or {}
   outcomes={d.get('domain'):d.get('status') for d in ((job or {}).get('domains') or result.get('domains') or [])}
   if job and job.get('state')=='completed' and all(outcomes.get(d) in {'success','completed','done'} for d in relevant):continue
  return False
 return True
def valid_retry(db,run,site,payload):
 row=db.get(models.AutoReglueConfig,retry_key(payload.request_id))
 if not row:return False
 value=row.value;job=db.get(models.BackgroundJob,value.get('job_id'))
 return bool(job and job.kind==KIND and job.status=='running' and run.id in job.payload['run_ids']
  and value['run_id']==run.id and site.id==run.site_id and payload.action=='create_domains'
  and str(payload.request_id)==retry_id(job,run) and payload.domains==value['domains']
  and set(payload.domains).issubset(names(run)) and deletion_ready(db,run,db.get(models.Site,run.plan['source_site_id']),payload.domains))
def error_details(error):
 if isinstance(error,httpx.HTTPStatusError):return 'HTTP_'+str(error.response.status_code),str(error)[:800]
 if isinstance(error,httpx.TimeoutException):return 'WEBDEV_TIMEOUT',str(error)[:800]
 return ('TRANSFER_QUEUE_FULL' if 'TRANSFER_QUEUE_FULL' in str(error) else 'TRANSFER_GUARD'),str(error)[:800]
def provisioning(db,site,op):
 if not op:return None
 if op.response_status and op.response_status>=400:return {'code':'HTTP_'+str(op.response_status),'message':op.message or 'Webdev отклонил запрос.'}
 try:
  with network.Remote(db,site) as remote:job=remote.job_state(op.request_payload.get('job_id')) if op.request_payload.get('job_id') else None
 except Exception as error:return {'code':error_details(error)[0],'message':'Не удалось проверить настройку домена: '+str(error)[:500]}
 result=(job or {}).get('result') or {}
 failures=[d for d in ((job or {}).get('domains') or result.get('domains') or []) if d.get('status')=='error']
 if op.status=='failed' or (job or {}).get('state')=='failed' or failures or result.get('errorCount'):
  message='; '.join(str(d.get('errorMessage') or next((s for s in reversed(d.get('logs') or []) if 'ошиб' in str(s).lower()),'Ошибка Webdev')) for d in failures) or str((job or {}).get('error') or op.message or result)
  message=message[:500]
  return {'code':'WEBDEV_DNS' if 'dns' in message.lower() else 'WEBDEV_JOB_FAILED','message':message,'job_id':op.request_payload.get('job_id'),**({'domains':[d['domain'] for d in failures]} if failures else {})}
 if job and not job.get('state'):return {'code':'WEBDEV_JOB_UNKNOWN','message':'Домен в целевой сетке; статус старой задачи Webdev недоступен.','job_id':op.request_payload.get('job_id')}
 if job and job.get('state')!='completed':return {'code':'WEBDEV_PROVISIONING','message':'Домен в целевой сетке; настройка Webdev ещё выполняется.','job_id':op.request_payload.get('job_id')}
 return None

def check_run(db,job,run):
 if run.plan.get('use_selected_reserve'):
  try:
   target=db.get(models.Site,run.site_id)
   state=network.read_network(db,target)
   ok=state['canon']==run.plan['new_main'] and run.plan['new_main'] in state['domains']
   code,message=('OK','Выбранный резерв стал Main своей сетки.') if ok else ('MAIN_NOT_CONFIRMED','Смена Main на выбранный резерв пока не подтверждена.')
  except Exception as error:
   db.rollback();db.refresh(run)
   ok=False;code,message=error_details(error)
  result={'checked_at':queue.now(),'job_id':job.id,'actor':job.payload['actor'],
   'domains':[{'domain':run.plan['new_main'],'status':'confirmed' if ok else 'failed',
    'code':code,'message':message}]}
  run.plan={**run.plan,'report_verification':result,'report_checks':[*run.plan.get('report_checks',[]),result]}
  reports.refresh_run(db,run);db.commit()
  return result
 source=db.get(models.Site,run.plan['source_site_id']);target=db.get(models.Site,run.site_id)
 domains=names(run);entries=[{'domain':d,'status':'failed','code':'NOT_CHECKED','message':'Не проверен'} for d in domains]
 try:
  with ExitStack() as locks:
   locks.enter_context(network.network_lock(db,'auto-run:'+run.id))
   for domain in sorted(domains):locks.enter_context(network.network_lock(db,policy_key(domain)))
   locks.enter_context(cross.participant_locks(db,target.id,run.plan))
   cross.require_pair(source,target)
   filters=MassActionFilter(brand=job.payload['brand'],geo=job.payload['geo'])
   if not all(matches(s,filters) for s in (source,target)):raise ValueError('Проекты больше не соответствуют бренду и GEO отчёта.')
   if run.plan.get('rolled_back_at') or run.status=='cancelled':
    for e in entries:e.update(status='skipped',code='RUN_ROLLED_BACK' if run.plan.get('rolled_back_at') else 'RUN_CANCELLED',message='Перенос отменён; повторное добавление не выполняется.')
   else:
    source_state=network.read_network(db,source);target_state=network.read_network(db,target)
    missing=[]
    for entry in entries:
     d=entry['domain']
     if d in target_state['domains']:entry.update(status='confirmed',code='OK',source_removed=d not in source_state['domains'],message='В целевой сетке, из исходной удалён.' if d not in source_state['domains'] else 'В целевой сетке.')
     elif d in source_state['domains']:entry.update(code='SOURCE_NOT_DELETED',message='Домен всё ещё находится в исходной сетке.')
     else:missing.append(d)
    if missing:
     rid=retry_id(job,run)
     op=db.get(models.NetworkOperation,rid)
     if op is None:
      if not deletion_ready(db,run,source,missing):raise ValueError('Удаление ещё не подтверждено задачей Webdev; добавление ожидает.')
      if db.scalar(select(models.NetworkOperation.id).where(models.NetworkOperation.site_id.in_([source.id,target.id]),models.NetworkOperation.status.in_(['pending','unknown'])).limit(1)):
       raise ValueError('WEBDEV_PENDING: есть операция без подтверждения; повторная отправка заблокирована.')
      for d in missing:
       require_non_project_domain(db,d);require_main_destination(db,target,[d]);cross.unique_membership(db,d,set())
       if banned_domains(db,target,[d])[d]:raise ValueError('Домен отмечен БАН.')
       for later in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.created_at>run.created_at)):
        if d in names(later) and later.id!=run.id:raise ValueError('DOMAIN_MOVED_LATER: домен участвует в более позднем переносе.')
      queue.reserve(db,run,missing,None,removed=True)
      db.add(models.AutoReglueConfig(key=retry_key(rid),value={'job_id':job.id,'run_id':run.id,'domains':missing}))
      db.commit() # Explicit retry intent precedes the network receipt and write.
      network.change_network(db,target,network.NetworkChange(request_id=rid,action='create_domains',revision=target_state['revision'],domains=missing),job.payload['actor'],auto_run_id=run.id)
      op=db.get(models.NetworkOperation,rid)
     for attempt in range(POLL_ATTEMPTS):
      target_state=network.read_network(db,target)
      if all(d in target_state['domains'] for d in missing) or op.status=='failed':break
      if attempt+1<POLL_ATTEMPTS:time.sleep(POLL_SECONDS)
     warning=provisioning(db,target,op) if any(d not in target_state['domains'] for d in missing) else None
     for entry in entries:
      if entry['domain'] not in missing:continue
      if entry['domain'] in target_state['domains']:entry.update(status='confirmed',code='OK',source_removed=entry['domain'] not in source_state['domains'],message='В целевой сетке, из исходной удалён.' if entry['domain'] not in source_state['domains'] else 'В целевой сетке.',retry_request_id=rid)
      else:
       code=warning['code'] if warning else ('HTTP_'+str(op.response_status) if op.response_status and op.response_status>=400 else 'DOMAIN_NOT_ADDED')
       entry.update(code=code,message=(warning or {}).get('message') or op.message or 'Домен не появился в целевой сетке.',retry_request_id=rid)
       queue.failure(db,run,[entry['domain']],code,entry['message'])
    else:warning=None
    if run.plan.get('execution_mode')=='transfer_only':
     from app.move_batch import domain_errors,clear_destination_errors
     clear_destination_errors(db,run,[e['domain'] for e in entries if e['status']=='confirmed'])
     errors=domain_errors(db,run,target_state['domains'])
     run.plan={**run.plan,'domain_errors':errors}
    if all(e['status']=='confirmed' for e in entries):
     queue.confirmed(db,run,domains)
     # Destination membership is the user's sole transfer completion criterion.
     if run.plan.get('execution_mode')=='transfer_only':
      at=queue.now()
      run.plan={**run.plan,'execution_before_report_check':run.plan.get('execution_before_report_check') or {'status':run.status,'message':run.message},
       'source_after':run.plan.get('source_after') or move.snapshot(source_state),'target_after':run.plan.get('target_after') or move.snapshot(target_state),
       'completed_at':run.plan.get('completed_at') or at,'completion_basis':'verified_destination_membership',
       'applied_result':run.plan.get('applied_result') or {'new_main':target_state['canon'],'fake_main_path':target_state.get('fake_main_current') or None,'confirmed_at':at}}
      for item in run.plan.get('domains',[]):
       if item['domain'] not in (target.domain_types or {}):target.domain_types={**(target.domain_types or {}),item['domain']:item['domain_type']}
      run.status='completed';run.phase='completed';run.message=f'Состав сеток подтверждён: {len(entries)} доменов.'
     if warning:
      for entry in entries:
       if 'domains' not in warning or entry['domain'] in warning['domains']:entry['warning']={k:v for k,v in warning.items() if k!='domains'}
    elif run.status=='completed' and run.plan.get('execution_mode')=='transfer_only':run.status='partial';run.message='Повторная проверка выявила отсутствующие домены.'
 except Exception as error:
  db.rollback();db.refresh(run)
  code,message=error_details(error)
  if 'WEBDEV_PENDING' in message:code='WEBDEV_PENDING'
  if 'DOMAIN_MOVED_LATER' in message:code='DOMAIN_MOVED_LATER'
  for entry in entries:
   if entry['status']!='confirmed' and entry['code']=='NOT_CHECKED':entry.update(code=code,message=message)
  queue.failure(db,run,[e['domain'] for e in entries if e['status']!='confirmed'],code,message)
 at=queue.now()
 result={'checked_at':at,'job_id':job.id,'actor':job.payload['actor'],'domains':entries}
 run.plan={**run.plan,'report_verification':result,'report_checks':[*run.plan.get('report_checks',[]),result]}
 reports.refresh_run(db,run);db.commit()
 return result

def execute(db,job):
 results=[]
 for run_id in job.payload['run_ids']:
  run=db.get(models.AutoReglueRun,run_id)
  if run and run.plan.get('execution_mode') in {'transfer_only','cross_network'}:
   results.append({'run_id':run.id,**check_run(db,job,run)})
  job.result={'entries':results};db.commit()
 return {'entries':results}


def serialize(job):return {'id':job.id,'status':job.status,'error':job.error,**(job.result or {'entries':[]})}
def visible(db,job,allowed):
 if allowed is None:return True
 for run_id in job.payload['run_ids']:
  run=db.get(models.AutoReglueRun,run_id)
  if run and not {run.site_id,run.plan.get('source_site_id',run.site_id)}.issubset(allowed):return False
 return True
def prepare(db,request_id,filters,actor,allowed):
 with network.network_lock(db,'report-check:'+cross.brand_key(filters.brand)+':'+filters.geo):
  previous=db.get(models.BackgroundJob,str(request_id))
  if previous:
   if previous.kind!=KIND or cross.brand_key(previous.payload['brand'])!=cross.brand_key(filters.brand) or previous.payload['geo']!=filters.geo or not visible(db,previous,allowed):raise ValueError('Идентификатор проверки уже использован.')
   return previous,False
  jobs=db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind==KIND,models.BackgroundJob.status.in_(['queued','running']))).all()
  active=next((j for j in jobs if cross.brand_key(j.payload['brand'])==cross.brand_key(filters.brand) and j.payload['geo']==filters.geo),None)
  if active:
   if not visible(db,active,allowed):raise ValueError('Проверка этой связки уже выполняется.')
   return active,False
  run_ids=list(dict.fromkeys(e['run_id'] for r in reports.list_reports(db,filters.brand,filters.geo,allowed) for e in r['entries'] if e.get('run_id')))
  job=models.BackgroundJob(id=str(request_id),kind=KIND,payload={'brand':filters.brand,'geo':filters.geo,'actor':actor,'run_ids':run_ids},result={'entries':[]})
  db.add(job);db.commit()
  return job,True
