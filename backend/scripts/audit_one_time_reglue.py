"""Final read-back audit, including user-requested rollbacks; no mutations."""
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from sqlalchemy import select
import httpx
from one_time_reglue import BATCH,Remote,snap,settings_equal,matches
from app.core.config import get_settings
from app.db import SessionLocal
from app import models
cfg=get_settings()
with httpx.Client(timeout=30) as c:
 r=c.post(cfg.project_cache_url.rstrip('/')+'/auth/login',json={'username':cfg.project_cache_username,'pass':cfg.project_cache_password});r.raise_for_status();token=r.json()['token']
with SessionLocal() as db:ids=list(db.scalars(select(models.NetworkOperation.id).where(models.NetworkOperation.request_payload['batch_id'].as_string()==BATCH)).all())
def check(oid):
 with SessionLocal() as db:
  op=db.get(models.NetworkOperation,oid);q=op.request_payload;site=db.get(models.Site,op.site_id);remote=Remote(site,token)
  try:
   actual=snap(remote.project());rid=q.get('rolled_back_by');expected=q['before'] if rid else q['after']
   ok=(settings_equal(actual['settings'],expected['settings']) and actual['head']==expected['head'])
   scheme_ok=matches(actual,q['plan']) if not rid else ok
   return {'site_id':site.id,'project':site.name,'operation_id':oid,'rolled_back':bool(rid),'snapshot_matches':ok,'scheme_matches':scheme_ok,'actual_main':actual['settings'].get('canon'),'changed_settings_keys':[k for k in set(actual['settings'])|set(expected['settings']) if k!='folder' and actual['settings'].get(k)!=expected['settings'].get(k)]}
  except Exception as e:return {'site_id':site.id,'project':site.name,'error':type(e).__name__+': '+str(e)[:500]}
  finally:remote.close()
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(check,i) for i in ids]):print(json.dumps(f.result(),ensure_ascii=False),flush=True)
