"""Publication list accepts native Webdev dates, including legacy numeric timestamps."""
import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
site=dict(id='e245f30e-6714-466d-baf1-f7242321c713',name='betonredczech.com',base_url='https://cz.bet-on-red-cz.com',brand='BetOnRed',site_type='monobrand',project_status='mass_actions',is_active=True,external_project_id='native',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='cz.bet-on-red-cz.com',cache_domains=['cz.bet-on-red-cz.com'],cache_geo='CZ',cache_language='cs',homepage_title='Home',internal_pages_count=2,domains_count=1,has_menu=False,main_domain_history=[],alternate_domain_history=[],x_default_history=[])
status={'complete':True,'internal_count':2,'linked_from_home':2,'linked_to_home':2,'message':'Перелинковка выполнена.'}
reads=[];failed=False
site.update(name='top-polskie-kasyno.pl',brand='Общие ключи',site_type='general',cache_canon='ionickiss.pl',cache_geo='PL')
dates=[1750167277596,1749807104156,1750167277,'1750167277596','2026-09-09 14:31:23','2023-07-12T13:45:33+00:00',None,'','invalid',{'unexpected':True}]
rows=[dict(key=str(i),title='Page '+str(i),slug='/' if i==0 else '/page-'+str(i)+'/',is_home=i==0,created_at=value,updated_at=value) for i,value in enumerate(dates)]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100},timezone_id='UTC');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  u=urlparse(r.request.url);path=u.path
  if not path.startswith('/api/'):
   asset=DIST/path.lstrip('/')
   if not asset.is_file():asset=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
  path=path[4:];data=[];code=200
  if path=='/auth/me':data={'id':'anton','username':'anton','is_admin':True,'is_active':True}
  elif path in ('/sites','/sites/cache/projects'):data=[site]
  elif path=='/sites/lookup':data=site
  elif path.endswith('/pages/interlinking'):
   reads.append(path)
   if failed:code=400;data={'detail':'Webdev check failed'}
   else:data=status.copy()
  elif path.endswith('/pages'):data={'pages':rows,'total':len(rows),'source':'webdev'}
  elif path.endswith('/network'):data={'canon':site['cache_canon'],'reserve':'','domains':site['cache_domains'],'revision':'revision','main_history':[],'x_default_history':[],'alternate_history':[],'alternateMarkup':'','enableAlternates':False,'has_head':False,'alternates':[],'operations':[]}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path.endswith('/notifications'):data={'items':[],'total':0,'active_count':0}
  r.fulfill(status=code,content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/project-content/top-polskie-kasyno.pl/')
 expect(page.locator('.pp-page-row')).to_have_count(len(rows))
 expected=['17.06.2025, 13:34','13.06.2025, 09:31','17.06.2025, 13:34','17.06.2025, 13:34','09.09.2026, 14:31','12.07.2023, 13:45','—','—','—','—']
 for index,wanted in enumerate(expected):
  dates_ui=page.locator('.pp-page-row').filter(has=page.locator('strong',has_text=__import__('re').compile('^Page '+str(index)+'$'))).locator('time')
  expect(dates_ui).to_have_text([wanted,wanted])
 page.get_by_role('button',name='Обновить список',exact=True).click()
 expect(page.locator('.pp-page-row')).to_have_count(len(rows))
 page.reload()
 expect(page.locator('.pp-page-row')).to_have_count(len(rows))
 assert not errors,errors
 browser.close()
print('PASS: direct publication route, milliseconds/seconds/numeric strings/ISO/native/null/invalid dates, list refresh and browser reload without render errors')
