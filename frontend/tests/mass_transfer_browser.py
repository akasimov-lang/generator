import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
DIST=Path(os.environ.get('PAGEPILOT_DIST', ROOT/'frontend/dist'))
settings={'enabled':True,'execution_mode':'cross_network','schedule_enabled':False,'interval_days':0,'max_projects':20,'scheme_mode':'preserve','auxiliary_hreflangs':[]}
requests=[]
runs=[]
plan={'site_id':'0','project':'p0.test','source_site_id':'donor','source_project':'donor.test','execution_mode':'transfer_only','domains':[{'domain':'free-drop.test','domain_type':'drop'},{'domain':'free-new.test','domain_type':'newreg'}],'preview_token':'token','source_before':{'domains':['a','b','c','d']},'target_before':{'domains':['p0.test']}}
rows=[dict(id=str(i),name=f'p{i}.test',project_name=f'P{i}',brand=b,geo=g,site_type=t,domains=6,drop=2,newreg=4,subdomains=0,amp=0,unknown=0,cache_synced_at=None) for i,(b,g,t) in enumerate([('MerkurXtip','CZ','monobrand'),('Mostbet','AZ','monobrand'),('Общие ключи','CZ','general')])]
sites=[dict(id=r['id'],name=r['name'],brand=r['brand'],base_url='https://'+r['name'],publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],external_project_id='project-'+r['id'],cache_canon=r['name'],cache_geo=r['geo'],cache_language='cs',cache_domains=[],project_status='mass_actions',is_test_project=False,has_menu=False,domains_count=6,internal_pages_count=0) for r in rows]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
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
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path=='/auto-reglue':data={'settings':settings,'projects':[{'id':r['id'],'name':r['name'],'geo':r['geo'],'config':{'scope':'mass'}} for r in rows],'runs':runs,'tasks':[],'language_pool':[]}
  elif path=='/auto-reglue/settings':settings.update(r.request.post_data_json);data=settings
  elif path=='/auto-reglue/projects/0/preview':data=plan
  elif path=='/auto-reglue/start':
   body=r.request.post_data_json;requests.append(body)
   runs.append({'id':'run','site_id':'0','status':'completed','phase':'completed','plan':dict(plan,source_after={'domains':['a','b']},target_after={'domains':['p0.test','free-drop.test','free-new.test']})});data={'results':[{'site_id':'0','run':runs[0]}]}
  elif path=='/auto-reglue/runs/run/rollback':
   requests.append({'rollback':True});runs[0]['plan']['rollback_run_id']='rollback';data={'id':'rollback','status':'queued'}
  elif path=='/ai-providers':data=[{'id':'gemini','name':'Gemini','provider_type':'gemini','is_active':True}]
  elif path=='/auto-reglue/content-drafts':
   request=r.request.post_data_json;requests.append(request);data={'results':[{'site_id':sid,'project':next(p['name'] for p in rows if p['id']==sid),'status':'ready','draft_id':'draft','url':'/project-content/p0.test/'} for sid in request['site_ids']]}
  elif path=='/sites/statistics':data={'projects':rows if parse_qs(u.query).get('scope',['mass_actions'])[0]=='mass_actions' else rows[:1]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/auto-reglue')
 expect(page.get_by_role('heading',name='Массовые действия',exact=True)).to_be_visible()
 expect(page.get_by_role('link',name='Массовые действия',exact=True)).to_be_visible()
 expect(page.get_by_role('button',name='Всего проектов 3',exact=True)).to_be_visible()
 toolbar=page.get_by_label('Массовые действия',exact=True)
 for label in ['Перекрёстный автопереклей','Обменять домены между сетками','Переписать мета и заголовки','Переписать абзацы','Обрезать 50% контента','Обрезать 99% контента']:
  expect(toolbar.get_by_role('button',name=label,exact=True)).to_be_visible()
 page.get_by_role('button',name='MerkurXtip',exact=True).click()
 choose=page.get_by_role('checkbox',name='Выбрать проект p0.test',exact=True)
 expect(choose).to_be_enabled();choose.check()
 expect(toolbar).to_contain_text('Выбрано: 1')
 toolbar.get_by_role('button',name='Обменять домены между сетками',exact=True).click()
 expect(page.get_by_text('Выберите одну принимающую сетку.',exact=False)).to_be_visible()
 page.get_by_role('button',name='Сохранить общие настройки',exact=True).click()
 prepare=page.get_by_role('button',name='Подготовить планы (1)',exact=True)
 expect(prepare).to_be_enabled();prepare.click()
 expect(page.get_by_text('free-drop.test',exact=True)).to_be_visible()
 expect(page.get_by_text('free-new.test',exact=True)).to_be_visible()
 assert not requests
 page.get_by_role('button',name='Запустить группу (1)',exact=True).click()
 rollback=page.get_by_role('button',name='Откатить перенос',exact=True)
 expect(rollback).to_be_visible();rollback.click()
 assert len(requests)==2 and len(requests[0]['items'])==1 and requests[1]['rollback']
 expect(page.get_by_role('button',name='Откат запущен',exact=True)).to_be_disabled()
 assert not errors,errors
 browser.close()
print('PASS: transfer-only mode; explicit saved configuration; two-domain preview before start; history and rollback action')
