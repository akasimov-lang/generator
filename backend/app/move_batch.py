"""Up to five donors, bounded prefetch and domain-specific replacement."""
from uuid import UUID,uuid5
from sqlalchemy import select
from app import models,auto_reglue as auto,project_network as network,cross_reglue as cross
from app import domain_redistribution as move,mass_action_reports as reports,domain_transfer_queue as queue
from app.mass_action_scope import brand_key,MassActionFilter
from app.domain_transfer_policy import geo_key

def group_key(id):return 'move-prefetch:'+str(id)
def failure_key(brand,geo):return 'move-failures:'+auto.digest([brand_key(brand),geo_key(geo)])[:40]
def blocked_domains(db,brand,geo):
 row=db.get(models.AutoReglueConfig,failure_key(brand,geo))
 return set((row.value if row else {}).get('domains',{}))
def group_runs(db,run):
 row=db.get(models.AutoReglueConfig,group_key(run.plan.get('batch_id',run.id)))
 return [r for id in (row.value.get('run_ids',[]) if row else [run.id]) if (r:=db.get(models.AutoReglueRun,id))]
def prepare(db,request_id,filters,site_ids,actor,allowed=None,count=2):
 from app.move_plus2 import prepare as prepare_one
 filters=MassActionFilter.model_validate(filters)
 with network.network_lock(db,'move-prefetch:'+brand_key(filters.brand)+':'+filters.geo):
  previous=db.get(models.AutoReglueRun,str(request_id))
  if previous and not previous.plan.get('prefetch'):
   prepare_one(db,request_id,filters,site_ids,actor,allowed,count)
   return group_runs(db,previous),False
  row=db.get(models.AutoReglueConfig,group_key(request_id))
  if row and row.value.get('ready'):
   if row.value['site_ids']!=sorted(set(site_ids)) or row.value['filter']!=filters.model_dump() or row.value['count']!=count:raise ValueError('Идентификатор Move уже использован с другой выборкой.')
   if allowed is not None and not set(site_ids).issubset(allowed):raise ValueError('Проекты недоступны.')
   return [db.get(models.AutoReglueRun,id) for id in row.value['run_ids']],False
  if not row:
   row=models.AutoReglueConfig(key=group_key(request_id),value={'run_ids':[],'site_ids':sorted(set(site_ids)),
    'filter':filters.model_dump(),'count':count,'actor':actor,'ready':False})
   db.add(row);db.commit()
  runs=[db.get(models.AutoReglueRun,id) for id in row.value['run_ids']]
  for index in range(len(runs),len(set(site_ids))):
   rid=request_id if index==0 else uuid5(UUID(str(request_id)),'donor:'+str(index))
   ctx={'id':str(request_id),'runs':runs,'unique_donors':False,'unique_recipients':True,'drop_used':any(d['domain_type']=='drop' for r in runs for d in r.plan['domains'])}
   try:run,_=prepare_one(db,rid,filters,site_ids,actor,allowed,count,prefetch=ctx)
   except (ValueError,network.NetworkConflict) as error:
    if not runs:raise
    row.value={**row.value,'planning_note':str(error)};db.commit();break
   runs.append(run);row.value={**row.value,'run_ids':[r.id for r in runs]};db.commit()
  attach_extractions(db,row,runs)
  row.value={**row.value,'ready':True};db.commit()
  return runs,True

def state_matches(db,run,state,site_id,before):
 if cross.source_guard(state)!=cross.source_guard(before):return False
 expected=set(before['domains'])
 for peer in group_runs(db,run):
  if peer.id==run.id:continue
  if peer.plan['source_site_id']==site_id:
   for d in peer.plan['domains']:
    for action in move.deletion_actions(peer):
     op=db.get(models.NetworkOperation,move.receipt(peer,action))
     if op and op.status=='confirmed':expected.discard(d['domain'])
  if peer.site_id==site_id:
   op=db.get(models.NetworkOperation,move.receipt(peer,'create'))
   if op and op.status=='confirmed':expected.update(d['domain'] for d in peer.plan['domains'])
 return set(state['domains'])==expected

def ready_to_add(db,run):
 peers=group_runs(db,run)
 if not peers:return True
 entries=queue.listing(db,run.plan['brand'],run.plan['geo'])['entries']
 available=queue.LIMIT-len(entries)
 for peer in sorted(peers,key=lambda p:p.plan.get('prefetch_index',0)):
  if peer.id==run.id or peer.plan.get('source_released') or peer.status in {'failed','partial','cancelled','completed'}:continue
  reserved={e['domain'] for e in entries if e['run_id']==peer.id}
  needed=sum(d['domain'] not in reserved for d in peer.plan['domains'])
  if needed<=available:return False
 for peer in peers:
  if peer.id==run.id:continue
  if peer.status=='completed':continue
  if peer.plan.get('prefetch_index',0)<run.plan.get('prefetch_index',0):
   op=db.get(models.NetworkOperation,move.receipt(peer,'create'))
   if not op:
    if peer.status not in {'failed','partial','cancelled'}:return False
   elif op.request_payload.get('job_id'):
    with network.Remote(db,db.get(models.Site,peer.site_id)) as remote:job=remote.job_state(op.request_payload['job_id'])
    if not job or job.get('state') not in {'completed','failed'}:return False
   elif op.status in {'pending','unknown'}:return False
 return True

def domain_errors(db,run,target_domains=None):
 if target_domains is None:target_domains=network.read_network(db,db.get(models.Site,run.site_id))['domains']
 missing={d['domain'] for d in run.plan['domains']}-set(target_domains)
 if not missing:return []
 errors=[]
 for action in [*move.deletion_actions(run),'create']:
  op=db.get(models.NetworkOperation,move.receipt(run,action))
  if not op or not op.request_payload.get('job_id'):continue
  site=db.get(models.Site,op.site_id)
  with network.Remote(db,site) as remote:job=remote.job_state(op.request_payload['job_id'])
  if not job or job.get('state') not in {'completed','failed'}:continue
  result=job.get('result') or {}
  for row in (job.get('domains') or result.get('domains') or []):
   if row.get('status')!='error' or row.get('domain') not in missing:continue
   logs=row.get('logs') or []
   code=str(row.get('failedStage') or '').upper()
   if not code:code='SUBDOMAIN_CREATE_FAILED' if any('создания поддомена' in str(s).lower() for s in logs) else 'DNS' if any('dns' in str(s).lower() and 'ошиб' in str(s).lower() for s in logs) else 'WEBDEV_DOMAIN_FAILED'
   message=str(row.get('errorMessage') or next((s for s in reversed(logs) if 'ошиб' in str(s).lower()),None) or 'Webdev не завершил операцию с доменом.')
   errors.append({'domain':row['domain'],'code':code,'message':message,'system_response':row,'job_id':op.request_payload['job_id'],'stage':action,'at':queue.now()})
 return errors

def _continue_after_error(db,run,send):
 if run.plan.get('manual_action')!='move_plus2' or run.plan.get('replacement_handled'):return []
 errors=domain_errors(db,run)
 if not errors:return [] # Unknown transport results are checked, never replaced blindly.
 source=db.get(models.Site,run.plan['source_site_id']);target=db.get(models.Site,run.site_id)
 source_state=network.read_network(db,source);target_state=network.read_network(db,target)
 key=failure_key(run.plan['brand'],run.plan['geo']);failures=db.get(models.AutoReglueConfig,key)
 if not failures:failures=models.AutoReglueConfig(key=key,value={'domains':{}});db.add(failures)
 failures.value={'domains':{**failures.value.get('domains',{}),**{e['domain']:e for e in errors}}}
 all_arrived=all(d['domain'] not in source_state['domains'] and d['domain'] in target_state['domains'] for d in run.plan['domains'])
 run.plan={**run.plan,'domain_errors':errors,'replacement_handled':False,'replacement_pending':True,'execution_error_before_replacement':run.plan.get('execution_error_before_replacement') or run.message}
 if all_arrived:
  queue.confirmed(db,run,[d['domain'] for d in run.plan['domains']])
  run.status='completed';run.phase='completed'
  run.plan={**run.plan,'completion_basis':'membership_with_domain_errors','source_after':move.snapshot(source_state),'target_after':move.snapshot(target_state),
   'applied_result':{'new_main':target_state['canon'],'fake_main_path':target_state.get('fake_main_current') or None,'confirmed_at':queue.now()},'completed_at':queue.now()}
 else:run.status='failed'
 run.message=f'Пропущено доменов с ошибкой Webdev: {len(errors)}. Остальные переносы продолжаются.'
 reports.refresh_run(db,run);db.commit()
 peers=group_runs(db,run)
 if sum(len(p.plan.get('domain_errors',[])) for p in peers)>=5:
  run.plan={**run.plan,'replacement_error':'Достигнут лимит 5 ошибочных доменов за запуск. Нужна проверка Webdev.','replacement_handled':True,'replacement_pending':False};db.commit();return []
 row=db.get(models.AutoReglueConfig,group_key(run.plan.get('batch_id',run.id)))
 intent=db.get(models.AutoReglueConfig,'move-plus2:'+run.id)
 if not intent:return []
 from app.move_plus2 import prepare as prepare_one
 ctx={'id':run.plan.get('batch_id',run.id),'runs':peers,'index':len(peers),'unique_donors':False,
  'drop_used':any(d['domain_type']=='drop' for p in peers for d in p.plan['domains'])}
 try:
  replacement,_=prepare_one(db,uuid5(UUID(run.id),'replacement'),run.plan['mass_filter'],intent.value['site_ids'],run.initiator,None,min(2,len(errors)),prefetch=ctx)
  if row:row.value={**row.value,'run_ids':[*row.value['run_ids'],replacement.id]}
  else:
   row=models.AutoReglueConfig(key=group_key(ctx['id']),value={'run_ids':[run.id,replacement.id],'ready':True});db.add(row)
  run.plan={**run.plan,'replacement_run_id':replacement.id,'replacement_handled':True,'replacement_pending':False,'replacement_error':None};reports.refresh_run(db,run);db.commit()
  send(replacement.id)
  return [replacement]
 except (ValueError,network.NetworkConflict) as error:
  pending=any(p.status in {'queued','running','waiting'} for p in peers if p.id!=run.id)
  run.plan={**run.plan,'replacement_error':str(error),'replacement_handled':not pending,'replacement_pending':pending};reports.refresh_run(db,run);db.commit();return []


def continue_after_error(db,run,send):
 with network.network_lock(db,'move-replacement:'+run.id):
  db.refresh(run)
  return _continue_after_error(db,run,send)


def attach_extractions(db,manifest,runs):
 groups={}
 for run in runs:groups.setdefault(run.plan['source_site_id'],[]).append(run)
 batches={}
 for source,peers in groups.items():
  chunks=[];chunk=[];size=0
  for peer in peers:
   count=len(peer.plan['domains'])
   if size+count>queue.LIMIT:chunks.append(chunk);chunk=[];size=0
   chunk.append(peer);size+=count
  if chunk:chunks.append(chunk)
  for index,chunk in enumerate(chunks):
   if len(chunk)<2:continue
   rid=str(uuid5(UUID(runs[0].plan['batch_id']),'extract:'+source+':'+str(index)))
   batches[rid]={'source_site_id':source,'run_ids':[p.id for p in chunk],
    'domains':[d['domain'] for p in chunk for d in p.plan['domains']]}
   for peer in chunk:peer.plan={**peer.plan,'extraction_batch':rid}
 manifest.value={**manifest.value,'extractions':batches}


def extraction(db,run):
 rid=run.plan.get('extraction_batch')
 if not rid:return [run],[d['domain'] for d in run.plan['domains']]
 row=db.get(models.AutoReglueConfig,group_key(run.plan['batch_id']))
 value=(row.value.get('extractions',{}) if row and row.value.get('ready') else {}).get(rid)
 if not value or run.id not in value['run_ids'] or value['source_site_id']!=run.plan['source_site_id']:
  raise ValueError('Нет сохранённого разрешения группового извлечения.')
 peers=[db.get(models.AutoReglueRun,id) for id in value['run_ids']]
 from app.move_plus2 import validate_intent
 from app.mass_action_scope import require_run_scope
 for peer in peers:
  if not peer or peer.plan.get('extraction_batch')!=rid or peer.plan['source_site_id']!=value['source_site_id'] or peer.plan.get('batch_id')!=run.plan['batch_id']:
   raise ValueError('Состав группового извлечения изменился.')
  validate_intent(db,peer);require_run_scope(db,peer)
 names=[d['domain'] for peer in peers for d in peer.plan['domains']]
 if names!=value['domains'] or len(names)>queue.LIMIT or len(set(names))!=len(names):raise ValueError('Домены группового извлечения изменились.')
 return peers,names


def clear_destination_errors(db,run,domains):
 confirmed=set(domains)
 old=run.plan.get('domain_errors',[])
 resolved=[e for e in old if e['domain'] in confirmed]
 plan={**run.plan,'domain_errors':[e for e in old if e['domain'] not in confirmed]}
 if all(d['domain'] in confirmed for d in plan.get('domains',[])):
  plan.update(replacement_error=None,replacement_pending=False,replacement_handled=True)
 run.plan=plan
 row=db.get(models.AutoReglueConfig,failure_key(plan['brand'],plan['geo']))
 if row:
  failures=dict(row.value.get('domains',{}))
  for error in resolved:
   existing=failures.get(error['domain'])
   if existing and existing.get('job_id')==error.get('job_id'):failures.pop(error['domain'])
  row.value={**row.value,'domains':failures}
