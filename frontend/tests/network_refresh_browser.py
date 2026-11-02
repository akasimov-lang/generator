"""Refresh only the current project filter, update real counts/Main, preserve selection, report partial failures."""
import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
sites=[dict(id=str(i),name=f'project-{i}.pl',external_project_id=f'webdev-{i}',brand=b,cache_geo=g,site_type='monobrand',base_url=f'https://old-{i}.pl',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon=f'old-{i}.pl',cache_language='pl-PL',cache_domains=[f'old-{i}.pl'],project_status='mass_actions',is_test_project=False,is_active=True,has_menu=False,domains_count=1,internal_pages_count=0,network_domain_counts={'drop':0,'newreg':1,'subdomains':0,'amp':0,'unknown':0}) for i,(b,g) in enumerate([('Fontan','PL')]*4+[('Fontan','CZ'),('Lemon Casino','PL')])]
sites[0]['cache_reserve']='selected-reserve.pl'
reads=[];fail=set()
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 page.add_init_script('localStorage.setItem("sites-table-preferences:test",JSON.stringify({columnOrder:["rowNumber","select","name","brand","title","canon","reserve","language","status","domainsCount","dropsCount","newregCount","subdomainsCount","fiberyName"],siteSort:{key:"reserve",direction:"asc"}}))')
 def route(r):
  u=urlparse(r.request.url);path=u.path;q=parse_qs(u.query)
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:];data=[]
  if path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ('/sites','/sites/cache/projects'):data=sites
  elif path=='/sites/lookup':data=next(s for s in sites if s['id']==q['site_id'][0])
  elif path.endswith('/network'):
   sid=path.split('/')[2];reads.append(sid)
   assert q=={'refresh':['true']}
   if sid in fail:
    r.fulfill(status=502,content_type='application/json',body=json.dumps({'detail':'Webdev временно недоступен'}));return
   s=sites[int(sid)];s.update(cache_canon=f'new-{sid}.pl',cache_reserve=f'reserve-{sid}.pl',cache_domains=[f'new-{sid}.pl',f'extra-{sid}.pl'],domains_count=2,network_domain_counts={'drop':1,'newreg':1,'subdomains':0,'amp':0,'unknown':0})
   data={'canon':s['cache_canon'],'domains':s['cache_domains']}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/favorites')
 page.wait_for_function('JSON.parse(localStorage.getItem("sites-table-preferences:test") || "{}").siteSort === null')
 page.goto('http://localhost/sites?geo=PL&brand=Fontan&from=%2Fproject-network%2Fproject-0.pl%2F')
 button=page.get_by_role('button',name='Обновить сетки проектов',exact=True)
 expect(button).to_be_visible()
 expect(page.get_by_role('columnheader',name='Резерв',exact=True)).to_have_count(0)
 expect(page.get_by_role('heading').filter(has_text='Fontan — PL')).to_be_visible()
 page.get_by_role('checkbox',name='Выбрать проект project-0.pl',exact=True).check()
 button.click()
 expect(button).to_be_enabled()
 expect(page.get_by_role('status').filter(has_text='Обновлено: 4 / 4')).to_be_visible()
 assert set(reads)=={'0','1','2','3'} and len(reads)==4,reads
 for i in range(4):
  expect(page.locator('td').get_by_text(f'new-{i}.pl',exact=True)).to_be_visible()
 expect(page.locator('td.column-reserve')).to_have_count(0)
 expect(page.get_by_role('checkbox',name='Выбрать проект project-0.pl',exact=True)).to_be_checked()
 assert page.url.endswith('from=%2Fproject-network%2Fproject-0.pl%2F')
 expect(page.locator('tfoot')).to_contain_text('8')
 expect(page.locator('tfoot')).to_contain_text('4')
 # An error must not prevent refreshing the other networks.
 reads.clear();fail.add('1')
 button.click()
 expect(page.get_by_role('status').filter(has_text='Обновлено частично: 3 / 4')).to_be_visible(timeout=20000)
 assert set(reads)=={'0','1','2','3'}
 details=page.locator('.siteNetworkRefreshErrors')
 expect(details.locator('p')).not_to_be_visible()
 details.locator('summary').click()
 expect(details).to_contain_text('project-1.pl')
 expect(details).to_contain_text('Webdev временно недоступен')
 page.screenshot(path='/tmp/pagepilot-reserve-status-20261020/network-refresh.png',full_page=True)
 assert not errors,errors
 browser.close()
print('PASS: no reserve column, saved reserve sorting safely removed; scoped network refresh, fresh Main/counts/totals, preserved selection and scope, partial failure does not stop other projects')
