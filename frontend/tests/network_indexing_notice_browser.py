"""Autosave on leaving fields, durable errors, hover summary and the project log route."""
import copy,json,mimetypes,os,re
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
sid='5276dbf6-1e66-4206-8585-2d61e7a5dd18'
site=dict(id=sid,name='lemon-casinoss.pl',brand='Lemon Casino',base_url='https://lemon-casinoss.pl',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='lemon-casinoss.pl',cache_geo='PL',cache_language='pl',cache_domains=['lemon-casinoss.pl','reserve.test'],project_status='mass_actions',is_test_project=False,is_active=True,has_menu=True,domains_count=2,internal_pages_count=0)
network=dict(canon='lemon-casinoss.pl',reserve='reserve.test',domains=site['cache_domains'],revision='one',main_history=[],x_default_history=[],alternate_history=[],alternateMarkup='<link rel="alternate" href="https://{{settings.canon}}/play/" hreflang="pl-PL" />',enableAlternates=True,enableCanonical=True,has_head=True,canonicalDefaultMarkup='<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}" />',canonicalFakeMainMarkup='<link rel="canonical" href="https://{{settings.canon}}/play/" />',fake_main_enabled=True,fake_main_current='/play/',fake_main_paths=['/play/','/lemons/'],alternates=[],operations=[])
posts=[]; notices={}; reads=[];notice_posts=[];fail=False;journal_down=False
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page(viewport={'width':1800,'height':1100});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  global fail
  url=urlparse(r.request.url);path=url.path;q=parse_qs(url.query)
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:];data=[]
  if path.endswith('/notifications'):
   if r.request.method=='POST':
    notice_posts.append(r.request.post_data_json)
    if journal_down:
     r.fulfill(status=503,content_type='application/json',body='{"detail":"Journal temporarily unavailable"}');return
    n=r.request.post_data_json
    existing=notices.get(n['key'])
    if n['active'] or not existing:
     notices[n['key']]={**n,'id':n['key'],'client_key':n['key'],'source':'interface','created_at':'2026-10-21T15:00:00Z','occurrences':1}
    else:existing['active']=False
    notices[n['key']]['status']='active' if n['active'] else 'resolved'
    data={'id':n['key'],'active':n['active']}
   else:
    reads.append(path);items=list(notices.values())
    active=sum(n['active'] for n in items)
    if q.get('active_only')==['true']:items=[n for n in items if n['active']]
    data={'active_count':active,'items':items,'total':len(items)}
  elif path.endswith('/network/operations') and r.request.method=='POST':
   payload=r.request.post_data_json;posts.append(payload)
   if fail:
    r.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'Webdev: test gateway error; canonical was not saved'}));return
   assert payload['action'] in ['alternates','reglue']
   if payload['action']=='alternates':
    network.update(alternateMarkup=payload['alternate_markup'],enableAlternates=payload['enable_alternates'])
    for a,b in [('canonical_default_markup','canonicalDefaultMarkup'),('canonical_fake_main_markup','canonicalFakeMainMarkup')]:
     if a in payload:network[b]=payload[a]
   else:network['canon']=payload['domain']
   network['revision']+='x'
   network['operations'].insert(0,dict(id=payload['request_id'],action=payload['action'],status='confirmed',domain=payload['domain'],initiator='anton',created_at='2026-10-21T15:00:00Z',message='Подтверждено'))
   data=network
  elif path.endswith('/network/indexing'):data={'id':'index-test','status':'index_unknown','response_status':201,'message':'Сервис не подтвердил номер задачи (HTTP 201).','count':13,'created_at':'2026-09-23T14:37:59Z'}
  elif path.endswith('/network/sitemap'):data=None
  elif path.endswith('/network'):data=network
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path=='/auth/me':data={'id':'test','username':'anton','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route)
 page.goto('http://localhost/project-network/lemon-casinoss.pl/')
 expect(page.locator('.networkIndexing').first).not_to_contain_text('Ответ не подтверждён — проверьте сервис индексации')
 badge=page.locator('.projectNotificationButton')
 expect(badge).to_have_attribute('title',re.compile('HTTP_201'))
 assert notices['network-indexing']['severity']=='info'
 assert '23.09.2026' in notices['network-indexing']['context']
 assert not posts
 badge.click()
 expect(page.locator('.projectLogEntry').filter(has_text='HTTP_201')).to_have_count(1)
 assert not errors,errors
 browser.close()
print('PASS: exact HTTP 201 and historical date in informational project notice; no red inline error or resubmission')
