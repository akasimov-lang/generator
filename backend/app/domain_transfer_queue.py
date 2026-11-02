"""Durable transfer outbox: at most five reserved/extracted roots per brand + GEO."""
from datetime import datetime,timezone
from hashlib import sha256
from sqlalchemy import select
from app import models
from app.domain_transfer_policy import domain_key,geo_key
from app.mass_action_scope import brand_key

LIMIT=5
PREFIX='transfer-outbox:'
ACTIVE={'reserved','extracted','adding','failed'}
def now():return datetime.now(timezone.utc).isoformat()
def key(run,domain):return PREFIX+sha256((run.id+':'+domain_key(domain)).encode()).hexdigest()
def scope(run):return brand_key(run.plan.get('brand')),geo_key(run.plan.get('geo'))
def rows(db,brand,geo):
 return db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.like(PREFIX+'%'),
  models.AutoReglueConfig.value['brand_key'].as_string()==brand_key(brand),
  models.AutoReglueConfig.value['geo'].as_string()==geo_key(geo))).all()
def reserve(db,run,domains,operation_id,*,removed=False):
 from app.project_network import network_lock,NetworkConflict
 brand,geo=scope(run)
 with network_lock(db,'transfer-outbox:'+brand+':'+geo):
  current=rows(db,brand,geo)
  existing={r.key:r for r in current}
  needed=[d for d in domains if key(run,d) not in existing]
  reopened=[d for d in domains if key(run,d) in existing and existing[key(run,d)].value['status'] not in ACTIVE]
  if sum(r.value['status'] in ACTIVE for r in current)+len(needed)+len(reopened)>LIMIT:
   raise NetworkConflict('TRANSFER_QUEUE_FULL: очередь '+str(run.plan.get('brand'))+' '+geo+' заполнена (лимит 5). Ждём добавления извлечённых доменов.')
  for domain in needed:
   value={'run_id':run.id,'domain':domain,'brand':run.plan.get('brand'),'brand_key':brand,'geo':geo,
    'source_site_id':run.plan['source_site_id'],'source_project':run.plan.get('source_project'),
    'target_site_id':run.site_id,'target_project':run.plan.get('project'),'status':'extracted' if removed else 'reserved',
    'reserved_at':now(),'removed_at':now() if removed else None,'deletion_id':operation_id,
    'history':[{'status':'extracted' if removed else 'reserved','at':now()}]}
   db.add(models.AutoReglueConfig(key=key(run,domain),value=value))
  for domain in reopened:
   transition(existing[key(run,domain)],'extracted' if removed else 'reserved',removed_at=now() if removed else None,delivered_at=None)
  db.commit() # Reserve capacity before a remote deletion can be sent.

def transition(row,status,**fields):
 value={**row.value,**fields}
 if value['status']!=status:value['history']=[*value.get('history',[]),{'status':status,'at':now()}]
 row.value={**value,'status':status}

def adding(db,run,domains,operation_id):
 reserve(db,run,domains,None,removed=True)
 for domain in domains:
  row=db.get(models.AutoReglueConfig,key(run,domain))
  if row and row.value['status']!='delivered':transition(row,'adding',addition_id=operation_id,error_code=None,error=None)
 db.commit()

def observe(db,site,state):
 for row in db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.like(PREFIX+'%'))):
  v=row.value
  if v['status'] not in ACTIVE:continue
  present=any(domain_key(d)==domain_key(v['domain']) for d in state['domains'])
  if site.id==v['source_site_id'] and not present and not v.get('removed_at'):
   transition(row,'extracted',removed_at=now())
  elif site.id==v['source_site_id'] and present and not v.get('removed_at'):
   op=db.get(models.NetworkOperation,v.get('deletion_id')) if v.get('deletion_id') else None
   if op and op.status=='failed':transition(row,'released',error_code='DELETE_FAILED',error=op.message)
  elif site.id==v['target_site_id'] and present and v.get('removed_at'):
   transition(row,'delivered',delivered_at=now(),error_code=None,error=None)

def confirmed(db,run,domains):
 for domain in domains:
  row=db.get(models.AutoReglueConfig,key(run,domain))
  if not row:
   row=models.AutoReglueConfig(key=key(run,domain),value={'run_id':run.id,'domain':domain,
    'brand':run.plan.get('brand'),'brand_key':scope(run)[0],'geo':scope(run)[1],
    'source_site_id':run.plan['source_site_id'],'source_project':run.plan.get('source_project'),
    'target_site_id':run.site_id,'target_project':run.plan.get('project'),
    'status':'delivered','reserved_at':run.created_at.isoformat(),'verified_at':now(),
    'delivered_at':now(),'history':[{'status':'delivered','at':now(),'basis':'verified_membership'}]})
   db.add(row)
  elif row.value['status']!='delivered':transition(row,'delivered',delivered_at=now(),error_code=None,error=None)

def failure(db,run,domains,code,message):
 for domain in domains:
  row=db.get(models.AutoReglueConfig,key(run,domain))
  if row and row.value['status'] in ACTIVE:transition(row,'failed',error_code=code,error=message)

def listing(db,brand,geo,allowed=None):
 values=[r.value for r in rows(db,brand,geo) if r.value['status'] in ACTIVE]
 if allowed is not None:values=[v for v in values if {v['source_site_id'],v['target_site_id']}.issubset(allowed)]
 return {'limit':LIMIT,'entries':sorted(values,key=lambda v:(v['reserved_at'],v['domain']))}


def progress(db,run):
 if run.plan.get('use_selected_reserve'):return []
 result=[]
 errors={e['domain']:e for e in run.plan.get('domain_errors',[])}
 for item in run.plan.get('domains',[]) or [{'domain':run.plan.get('new_main'),'domain_type':run.plan.get('domain_type')}]:
  d=item['domain']
  if not d:continue
  row=db.get(models.AutoReglueConfig,key(run,d))
  stage=(row.value['status'] if row else 'delivered' if run.status=='completed' else 'failed' if run.status in {'failed','partial'} else 'adding' if run.phase=='transfer_create' else 'reserved' if run.phase=='transfer_delete' else 'planned')
  if stage=='delivered' and run.status in {'queued','running','waiting'}:stage='confirming'
  result.append({'domain':d,'domain_type':item.get('domain_type'),'stage':'failed' if d in errors else stage,
   'source_project':run.plan.get('source_project'),'target_project':run.plan.get('project'),'error':errors.get(d)})
 return result


def reserve_extraction(db,runs,operation_id):
 from app.project_network import network_lock,NetworkConflict
 brand,geo=scope(runs[0])
 with network_lock(db,'transfer-outbox:'+brand+':'+geo):
  current=rows(db,brand,geo);active={r.key for r in current if r.value['status'] in ACTIVE}
  requested={key(run,d['domain']) for run in runs for d in run.plan['domains']}
  if len(active|requested)>LIMIT:raise NetworkConflict('TRANSFER_QUEUE_FULL: ждём свободное место в очереди (лимит 5).')
  for run in runs:reserve(db,run,[d['domain'] for d in run.plan['domains']],operation_id)
