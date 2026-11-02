import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
settings={'enabled':True,'execution_mode':'cross_network','schedule_enabled':False,'interval_days':0,'max_projects':100,'scheme_mode':'preserve','auxiliary_hreflangs':[],'selection_filter':None}
requests=[];previews=[]
move_requests=[]
runs=[]
rows=[dict(id=str(i),name=f'p{i}.test',project_name=f'P{i}',brand=b,geo=g,site_type=t,domains=6,drop=2,newreg=4,subdomains=0,amp=0,unknown=0,cache_synced_at=None) for i,(b,g,t) in enumerate([
 ('MerkurXtip','CZ','monobrand'),('MerkurXtip','CZ','monobrand'),('Общие ключи','CZ','general'),('Other','CZ','monobrand'),
 ('MerkurXtip','PL','monobrand'),('Общие ключи','PL','general'),('Mostbet','AZ','monobrand'),('MerkurXtip','DE','monobrand'),
 ('Общие ключи','AZ','general'),('Общие ключи','DE','general'),('Outside','FR','monobrand')])]
sites=[dict(id=r['id'],name=r['name'],brand=r['brand'],site_type=r['site_type'],base_url='https://'+r['name'],publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],external_project_id='project-'+r['id'],cache_canon=r['name'],cache_geo=r['geo'],cache_language='cs',cache_domains=[],project_status='mass_actions',is_test_project=False,has_menu=False,domains_count=6,internal_pages_count=0) for r in rows]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  u=urlparse(r.request.url);path=u.path
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:];data=[]
  if path=='/auth/me':data={'id':'editor','username':'editor','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=sites
  elif path=='/auto-reglue/list-launch':data=None
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path=='/auto-reglue':data={'settings':settings,'projects':[{'id':r['id'],'name':r['name'],'geo':r['geo'],'config':{'scope':'mass'}} for r in rows],'runs':runs,'tasks':[],'language_pool':[]}
  elif path=='/ai-providers':data=[{'id':'gemini','name':'Gemini','provider_type':'gemini','is_active':True}]
  elif path=='/auto-reglue/settings' and r.request.method=='PUT':
   settings.update(r.request.post_data_json);data=settings
  elif path=='/auto-reglue/move-plus2':
   request=r.request.post_data_json;move_requests.append(request)
   data={'id':request['request_id'],'site_id':'0','status':'completed','phase':'completed','message':'Перенесено',
         'plan':{'manual_action':'move_plus2','execution_mode':'transfer_only','geo':'CZ','brand':'MerkurXtip','source_project':'p1.test','project':'p0.test','domains':[{'domain':'newreg1.test','domain_type':'newreg'},{'domain':'newreg2.test','domain_type':'newreg'}]}}
   runs[:]=[data]
  elif path=='/auto-reglue/content-drafts':
   request=r.request.post_data_json;requests.append(request);data={'results':[{'site_id':sid,'project':next(p['name'] for p in rows if p['id']==sid),'status':'ready','draft_id':'draft','url':'/project-content/p0.test/'} for sid in request['site_ids']]}
  elif path=='/auto-reglue/preview-batch':
   request=r.request.post_data_json;previews.append(request);data={'batch_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','plans':[{'site_id':'0','project':'p0.test','source_project':'p1.test','old_main':'old.test','new_main':'new.test','preview_token':'a'*64,'batch_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','required_page_urls':[],'main_target_kind':'newreg','fallback_reason':'Выбранный резерв в БАН; выбран разрешённый новорег из другой сетки того же бренда и GEO.'}],'skipped':[]}
  elif path=='/auto-reglue/reports':
   q=parse_qs(u.query)
   data={'reports':[{'id':'report','actor':'editor','created_at':'2026-10-19T12:00:00Z','filter':{'brand':'MerkurXtip','geo':'CZ','include_general':False,'site_type':None},'skipped':[], 'entries':[{'run_id':'run','status':'completed','source_project':'p1.test','target_project':'p0.test','domains':['new.test'],'old_main':'old.test','new_main':'new.test','old_fake_main_path':'/old/','new_fake_main_path':'/new/','message':'Подтверждено'}]}] if q.get('brand')==['MerkurXtip'] and q.get('geo')==['CZ'] else []}
  elif path=='/auto-reglue/reports/check':data=None
  elif path=='/auto-reglue/transfer-queue':data={'limit':5,'entries':[]}
  elif path=='/sites/statistics':data={'projects':rows}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/auto-reglue')
 picker=page.get_by_role('region',name='Бренды и GEO массовых действий')
 expect(picker.locator('.peerBrandTile').first).to_contain_text('11')
 expect(page.get_by_role('checkbox',name='Выбрать проект p0.test',exact=True)).to_be_visible()
 # Add a new project; the statistics poll must also refresh the full site snapshot.
 added={**rows[0],'id':'new','name':'added.test','project_name':'Added'}
 rows.append(added);sites.append({**sites[0],'id':'new','name':'added.test'})
 expect(picker.locator('.peerBrandTile').first).to_contain_text('12',timeout=12000)
 expect(page.get_by_role('checkbox',name='Выбрать проект added.test',exact=True)).to_be_visible()
 # Deletion and mass-status removal both update the same page without reloading.
 rows[:]=[r for r in rows if r['id'] not in ('new','0')]
 sites[:]=[s for s in sites if s['id']!='new'];sites[0]['project_status']='working'
 expect(picker.locator('.peerBrandTile').first).to_contain_text('10',timeout=12000)
 expect(page.get_by_role('checkbox',name='Выбрать проект added.test',exact=True)).to_have_count(0)
 expect(page.get_by_role('checkbox',name='Выбрать проект p0.test',exact=True)).to_have_count(0)
 assert not errors,errors
 browser.close()
print('PASS: additions, deletion and status changes update counts and projects without reload')
