"""Correct a previously saved scheme using verified domains from the same network."""
import copy,json,sys
from pathlib import Path
from uuid import UUID,uuid5
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from one_time_reglue import Remote,HEAD,now,save,step,snap,desired,finish
from app.core.config import get_settings
from app.db import SessionLocal
from app import models
from app.project_network import network_lock
from app.network_state import project_network_state,domain_name
from app.network_indexing import submit_network_indexing
cfg=get_settings()
with httpx.Client(timeout=30) as c:
 r=c.post(cfg.project_cache_url.rstrip('/')+'/auth/login',json={'username':cfg.project_cache_username,'pass':cfg.project_cache_password});r.raise_for_status();token=r.json()['token']
def correct(item):
 if not item.get('new_main'):return {'site_id':item['site_id'],'status':'no_valid_target'}
 with SessionLocal() as db:
  op=db.get(models.NetworkOperation,item['operation_id']);site=db.get(models.Site,item['site_id']);remote=Remote(site,token);rev=None
  try:
   with network_lock(db,site.id):
    assert op.status=='confirmed'
    project=remote.project();assert snap(project)==op.request_payload['after'],'Settings changed after last confirmed operation'
    state=project_network_state(project)
    for d in [item['new_main'],item['alternate_domain']]:assert d in state['domains'] and d not in state['amp_domains'] and (site.domain_types or {}).get(d)!='amp'
    p=copy.deepcopy(op.request_payload['plan']);prior=copy.deepcopy(op.request_payload)
    p.update(new_main=item['new_main'],new_main_type=item['new_main_type'],alternate_domain=item['alternate_domain'])
    if item['alternate_domain']!=item['old_alternate']:
     p['newreg']=item['alternate_domain'] if (site.domain_types or {}).get(item['alternate_domain'])=='newreg' else ''
     p['no_newreg']='Нет' if p['newreg'] else 'Да — нет доступного новорега, ссылки на Main'
    p['x_default']='https://'+p['new_main']+'/'
    p['canonical_main_and_fake']='https://'+p['new_main']+p['fake_path']
    links=[(p['language']+'-'+p['geo'],'https://'+p['alternate_domain']+p['fake_path']),(p['language'],'https://'+p['alternate_domain']+'/'),('x-default',p['x_default'])]
    p['alternate_markup']='\n'.join('<link rel="alternate" hreflang="'+lang+'" href="'+url+'" />' for lang,url in links)
    p['public_correction']=item
    rid=str(uuid5(UUID(op.id),'public-correction-v1'))
    assert not db.get(models.NetworkOperation,rid),'Correction receipt already exists; do not repeat'
    rp=copy.deepcopy(p);rp['old_main']=state['canon']
    rev=models.NetworkOperation(id=rid,site_id=site.id,action='reglue',status='running',initiator='anton',request_payload={'correction_of':op.id,'source_domain':state['canon'],'reserve':p['new_main'],'plan':rp,'before':snap(project),'steps':{},'rollback_command':'one_time_reglue.py rollback --operation '+rid,'started_at':now()},message='Коррекция цели/языкового домена после публичной проверки.')
    db.add(rev);db.commit()
    if state['canon']!=p['new_main']:
     reserve={'reserve':p['new_main']}
     if 'reserveOption' in project['settings']:reserve['reserveOption']=p['new_main']
     step(db,rev,remote,'reserve','POST','/projects/update-value',{'folder':site.name,**reserve},lambda q:all(q['settings'].get(k)==v for k,v in reserve.items()))
     step(db,rev,remote,'reglue','POST','/projects/update-reglue',{'folder':site.name,'reserve':p['new_main'],'trigger':'webdev:settings','initiator':cfg.project_cache_username},lambda q:domain_name(q['settings'].get('canon'))==p['new_main'])
    head=desired(p)
    step(db,rev,remote,'head','PATCH','/projects/update-head',{'folder':site.name,**head},lambda q:all(q['head'].get(k)==v for k,v in head.items()))
    finish(db,site,remote,rev)
    chain=prior.get('version_chain',[])+[{'plan':prior['plan'],'after':prior['after'],'steps':prior['steps'],'indexing_operation_id':prior.get('indexing_operation_id'),'correction_operation_id':rid}]
    op.message='Итог массового запуска: '+p['old_main']+' → '+p['new_main']+'; '+p['fake_path']+'. Цель/языковой домен уточнены после публичной проверки. Исходная версия ДО и промежуточная версия сохранены. Откат: '+op.id
    save(db,op,plan=p,reserve=p['new_main'],after=rev.request_payload['after'],version_chain=chain,indexing_operation_id=rev.request_payload['indexing_operation_id'],public_corrected_at=now())
   submit_network_indexing(db,rev.request_payload['indexing_operation_id'])
   return {'site_id':site.id,'project':site.name,'status':'corrected','new_main':p['new_main'],'alternate_domain':p['alternate_domain'],'correction_id':rev.id}
  except Exception as e:
   db.rollback()
   if rev:
    rev=db.get(models.NetworkOperation,rev.id)
    if rev.status=='running':rev.status='partial';rev.message=type(e).__name__+': '+str(e)[:600];db.commit()
   return {'site_id':item['site_id'],'status':'error','error':type(e).__name__+': '+str(e)[:600]}
  finally:remote.close()
items=[json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines()]
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(correct,p) for p in items]):print(json.dumps(f.result(),ensure_ascii=False),flush=True)
