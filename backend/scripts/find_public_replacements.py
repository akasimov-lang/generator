"""Read-only lookup of domains serving the newly applied project scheme."""
import json,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlsplit
from sqlalchemy import select
import httpx
from app.db import SessionLocal
from app import models
from app.network_state import project_network_state,domain_name
from app.domain_classification import classify_domains
from html.parser import HTMLParser
BATCH='7b9d5b4b-5a1c-4904-b3dc-c36a8b0cae47'
class H(HTMLParser):
 def __init__(self):super().__init__();self.canonical=[];self.alternate=[]
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='link' and d.get('rel')=='canonical':self.canonical.append(d.get('href'))
  if t=='link' and d.get('rel')=='alternate' and d.get('hreflang'):self.alternate.append((d.get('hreflang'),d.get('href')))
def serves(c,domain,p):
 h=H();h.feed(p['alternate_markup']);expected=sorted(h.alternate)
 for path in ['/',p['fake_path']]:
  try:
   r=c.get('https://'+domain+path);parser=H();parser.feed(r.text)
   if not(r.status_code==200 and urlsplit(str(r.url)).hostname.removeprefix('www.')==domain.removeprefix('www.') and parser.canonical==[p['canonical_main_and_fake']] and sorted(parser.alternate)==expected):return False
  except Exception:return False
 return True
checks=[json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines()]
issues={x['site_id']:x for x in checks if not x['all_urls_verified']}
def find(siteid):
 with SessionLocal() as db:
  op=db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.site_id==siteid,models.NetworkOperation.request_payload['batch_id'].as_string()==BATCH))
  site=db.get(models.Site,siteid);q=op.request_payload;p=q['plan'];state=project_network_state(q['after']);types=site.domain_types or {};roles=classify_domains(state['domains'],types)
  domains=[d for d in state['domains'] if d not in state['amp_domains'] and types.get(d)!='amp'];roots=[d for d in domains if not roles[d]['is_subdomain']]
  used={domain_name(d).removeprefix('www.') for d in [state['canon'],state['prev'],*(site.main_domain_history or [])] if d}
  drops=[d for d in roots if types.get(d)=='drop'];unused=[d for d in drops if d.removeprefix('www.') not in used];newregs=[d for d in domains if types.get(d)=='newreg' and d.removeprefix('www.') not in used]
  ordered=list(dict.fromkeys(unused+[d for d in [q['before']['settings']['canon'],state['reserve'],*drops] if d in drops]+newregs))
  with httpx.Client(timeout=httpx.Timeout(12,connect=5),follow_redirects=True) as c:
   newmain=p['new_main'];tried=[]
   if not issues[siteid]['main_pages_verified']:
    newmain=None
    for d in ordered:
     if d==p['new_main']:continue
     ok=serves(c,d,p);tried.append({'domain':d,'serves_project':ok})
     if ok:newmain=d;break
   alternate=p['alternate_domain']
   if newmain and not serves(c,alternate,p):
    alternate=None
    for d in roots:
     if types.get(d)!='newreg':continue
     ok=serves(c,d,p);tried.append({'alternate_candidate':d,'serves_project':ok})
     if ok:alternate=d;break
    alternate=alternate or newmain
  result={'site_id':siteid,'project':site.name,'operation_id':op.id,'old_target':p['new_main'],'new_main':newmain,'new_main_type':types.get(newmain),'old_alternate':p['alternate_domain'],'alternate_domain':alternate,'checks':tried}
  print(json.dumps(result,ensure_ascii=False),flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(find,sid) for sid in issues]):f.result()
