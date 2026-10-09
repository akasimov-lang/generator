"""Read-only candidate selection after failed availability checks."""
import copy,json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from uuid import UUID,uuid5
import httpx
from one_time_reglue import BATCH,Remote,validate
from app.core.config import get_settings
from app.db import SessionLocal
from app import models
from app.network_state import project_network_state,domain_name
from app.domain_classification import classify_domains
plan=json.loads(Path('/tmp/reglue-plan.json').read_text())
cfg=get_settings()
with httpx.Client(timeout=30) as c:
 r=c.post(cfg.project_cache_url.rstrip('/')+'/auth/login',json={'username':cfg.project_cache_username,'pass':cfg.project_cache_password});r.raise_for_status();token=r.json()['token']
def choose(p):
 with SessionLocal() as db:
  op=db.get(models.NetworkOperation,str(uuid5(UUID(BATCH),p['site_id'])))
  if op:return p
  site=db.get(models.Site,p['site_id']);remote=Remote(site,token)
  try:
   project=remote.project();validate(project,p,site);state=project_network_state(project)
   types=site.domain_types or {};roles=classify_domains(state['domains'],types);amp=set(state['amp_domains'])
   roots=[d for d in state['domains'] if not roles[d]['is_subdomain'] and d not in amp and types.get(d)!='amp']
   used={domain_name(d).removeprefix('www.') for d in [state['canon'],state['prev'],*(site.main_domain_history or [])] if d}
   drops=[d for d in roots if types.get(d)=='drop'];unused=[d for d in drops if d.removeprefix('www.') not in used]
   newregs=[d for d in state['domains'] if types.get(d)=='newreg' and d not in amp and d.removeprefix('www.') not in used]
   reserve=state['reserve']
   candidates=list(dict.fromkeys([d for d in [reserve,*unused] if d in unused]+[d for d in [state['canon'],reserve,*drops] if d in drops]+[d for d in [reserve,*newregs] if d in newregs]))
   checks=[];target=None
   for d in candidates:
    try:result=remote.request('POST','/projects/check-domain',{'domain':d})
    except Exception as e:result={'reachable':False,'reason':type(e).__name__}
    checks.append({'domain':d,**result})
    if result.get('reachable') is True:target=d;break
   p=copy.deepcopy(p);p['replacement_checks']=checks
   if not target:p['replacement_error']='No available candidate';print(p['project']+' NO CANDIDATE',file=sys.stderr,flush=True);return p
   p['original_planned_main']=p['new_main'];p['new_main']=target;p['new_main_type']=types[target]
   p['fallback_newreg']='Да' if types[target]=='newreg' else 'Нет';p['reused_drop']='Да' if target in drops and target.removeprefix('www.') in used else 'Нет'
   p['main_change']='Main сохраняется: новая схема' if target==state['canon'] else 'Смена Main'
   p['alternate_domain']=p['newreg'] or target;p['x_default']='https://'+target+'/'
   p['canonical_main_and_fake']='https://'+target+p['fake_path']
   links=[(p['language']+'-'+p['geo'],'https://'+p['alternate_domain']+p['fake_path']),(p['language'],'https://'+p['alternate_domain']+'/'),('x-default',p['x_default'])]
   p['alternate_markup']='\n'.join('<link rel="alternate" hreflang="'+lang+'" href="'+url+'" />' for lang,url in links)
   p['notes']+='\nЦель заменена после проверки доступности по указанию пользователя: '+p['original_planned_main']+' → '+target
   print(p['project']+' => '+target,file=sys.stderr,flush=True);return p
  finally:remote.close()
with ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(choose,p):p for p in plan['projects'] if not p['excluded']}
 replacements={}
 for f in as_completed(futures):
  p=futures[f]
  try:replacements[p['site_id']]=f.result()
  except Exception as e:p=copy.deepcopy(p);p['replacement_error']=type(e).__name__+': '+str(e);replacements[p['site_id']]=p
plan['projects']=[replacements.get(p['site_id'],p) for p in plan['projects']]
Path('/tmp/reglue-plan-replacements.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
print(json.dumps([{k:p.get(k) for k in ['source_ids','project','original_planned_main','new_main','replacement_error','replacement_checks']} for p in plan['projects'] if 'replacement_checks' in p or 'replacement_error' in p],ensure_ascii=False))
