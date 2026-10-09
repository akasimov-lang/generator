"""Read-only public HTML verification; no Webdev credentials are sent."""
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from html.parser import HTMLParser
import httpx
from sqlalchemy import select
from app.db import SessionLocal
from app import models
BATCH='7b9d5b4b-5a1c-4904-b3dc-c36a8b0cae47'
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='link' and d.get('rel') in ('canonical','alternate'):self.links.append(d)
 def handle_startendtag(self,t,a):self.handle_starttag(t,a)
def verify(p):
 parser=Links();parser.feed(p['alternate_markup']);expected=sorted((l.get('hreflang',''),l.get('href','')) for l in parser.links)
 results=[]
 urls=list(dict.fromkeys(['https://'+p['new_main']+'/',p['canonical_main_and_fake'],'https://'+p['alternate_domain']+'/','https://'+p['alternate_domain']+p['fake_path']]))
 with httpx.Client(timeout=httpx.Timeout(20,connect=8),follow_redirects=True) as c:
  for url in urls:
   try:
    r=c.get(url);parser=Links();parser.feed(r.text)
    canonical=[l.get('href') for l in parser.links if l.get('rel')=='canonical'];alternates=sorted((l.get('hreflang',''),l.get('href','')) for l in parser.links if l.get('rel')=='alternate' and l.get('hreflang'))
    results.append({'url':url,'status_code':r.status_code,'final_url':str(r.url),'canonical':canonical,'alternates':alternates,'verified':r.status_code==200 and canonical==[p['canonical_main_and_fake']] and alternates==expected})
   except Exception as e:results.append({'url':url,'verified':False,'error':type(e).__name__+': '+str(e)[:250]})
 return {'site_id':p['site_id'],'project':p['project'],'main_pages_verified':all(x['verified'] for x in results[:2]),'all_urls_verified':all(x['verified'] for x in results),'pages':results}
with SessionLocal() as db:
 plans=[o.request_payload['plan'] for o in db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.request_payload['batch_id'].as_string()==BATCH,models.NetworkOperation.status=='confirmed')).all() if not o.request_payload.get('rolled_back_by')]
with ThreadPoolExecutor(max_workers=6) as pool:
 for future in as_completed([pool.submit(verify,p) for p in plans]):print(json.dumps(future.result(),ensure_ascii=False),flush=True)
