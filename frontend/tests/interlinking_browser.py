"""Interlinking indicator: complete reciprocal coverage, gray fallback, explicit refresh, no idle polling."""
import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
site=dict(id='e245f30e-6714-466d-baf1-f7242321c713',name='betonredczech.com',base_url='https://cz.bet-on-red-cz.com',brand='BetOnRed',site_type='monobrand',project_status='mass_actions',is_active=True,external_project_id='native',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='cz.bet-on-red-cz.com',cache_domains=['cz.bet-on-red-cz.com'],cache_geo='CZ',cache_language='cs',homepage_title='Home',internal_pages_count=2,domains_count=1,has_menu=False,main_domain_history=[],alternate_domain_history=[],x_default_history=[])
status={'complete':True,'internal_count':2,'linked_from_home':2,'linked_to_home':2,'message':'Перелинковка выполнена.'}
reads=[];failed=False
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
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
  elif path.endswith('/pages'):data={'pages':[],'total':0,'source':'webdev'}
  elif path.endswith('/network'):data={'canon':site['cache_canon'],'reserve':'','domains':site['cache_domains'],'revision':'revision','main_history':[],'x_default_history':[],'alternate_history':[],'alternateMarkup':'','enableAlternates':False,'has_head':False,'alternates':[],'operations':[]}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path.endswith('/notifications'):data={'items':[],'total':0,'active_count':0}
  r.fulfill(status=code,content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/project-network/betonredczech.com/')
 badge=page.locator('.projectInterlinking')
 expect(badge).to_have_class('projectInterlinking isComplete')
 expect(badge).to_have_attribute('aria-label','Перелинковка выполнена')
 expect(badge).to_have_attribute('title',__import__('re').compile('Главная → внутренние: 2/2.*',__import__('re').S))
 page.wait_for_timeout(1500);baseline=len(reads)
 page.wait_for_timeout(3000);assert len(reads)==baseline,reads
 status.update(complete=False,linked_to_home=1,message='Не все страницы связаны с главной в обе стороны.')
 badge.click();expect(badge).to_be_enabled();expect(badge).not_to_have_class(__import__('re').compile('isComplete'))
 expect(badge).to_have_attribute('title',__import__('re').compile('Внутренние → главная: 1/2'))
 status.update(internal_count=0,linked_from_home=0,linked_to_home=0,message='На сайте пока нет внутренних страниц.')
 badge.click();expect(badge).to_be_enabled();expect(badge).to_have_attribute('title',__import__('re').compile('Нет|нет'))
 failed=True;badge.click();expect(badge).to_be_enabled();expect(badge).not_to_have_class(__import__('re').compile('isComplete'))
 expect(badge).to_have_attribute('title',__import__('re').compile('Webdev check failed'))
 failed=False;status.update(complete=True,internal_count=2,linked_from_home=2,linked_to_home=2,message='Перелинковка выполнена.')
 page.evaluate('(id)=>window.dispatchEvent(new CustomEvent("pagepilot-project-changed",{detail:{siteId:id}}))',site['id'])
 expect(badge).to_have_class('projectInterlinking isComplete')
 before=len(reads);page.evaluate('window.dispatchEvent(new CustomEvent("pagepilot-project-changed",{detail:{siteId:"other"}}))')
 page.wait_for_timeout(1000);assert len(reads)==before
 page.screenshot(path='/tmp/pagepilot-interlinking-20261022/indicator.png',full_page=False)
 # General sites additionally show a showcase count and compact brand tiles.
 site.update(site_type='general',brand='Общие ключи')
 brands=['Ritzo','NV Casino','Roby Casino','Wild Tokyo','Instant Casino','Hugo Casino','Yep!Casino','Sankra Casino','Jokery Casino','BetAlice Casino','Slotoro Casino']
 status['showcase']={'count':11,'brands':brands,'message':''}
 page.goto('http://localhost/project-network/betonredczech.com/')
 showcase=page.get_by_role('button',name='Витрина — открыть контент и публикацию',exact=True)
 expect(showcase.locator('.projectShowcaseCount')).to_have_text('11')
 showcase.click()
 expect(page.get_by_role('region',name='Бренды витрины')).to_be_visible()
 expect(page.locator('.projectShowcaseTile')).to_have_count(11)
 actual=page.locator('.projectShowcaseTile > span:last-child').all_text_contents();assert actual==brands,actual
 page.set_viewport_size({'width':700,'height':1000})
 assert page.locator('.projectShowcaseTiles').evaluate('(e)=>e.scrollHeight > e.firstElementChild.offsetHeight'), 'Tiles must wrap into compact rows'
 page.screenshot(path='/tmp/pagepilot-interlinking-20261022/showcase.png',full_page=False)
 site.update(site_type='monobrand',brand='BetOnRed')
 page.goto('http://localhost/project-network/betonredczech.com/')
 expect(page.locator('.projectShowcaseIndicator')).to_have_count(0)
 expect(page.get_by_role('region',name='Бренды витрины')).to_have_count(0)
 assert not errors,errors
 browser.close()
print('PASS: green only for reciprocal content links, gray incomplete/no pages/error, tooltip counts, manual/event refresh, no idle polling or unrelated-project refresh')
