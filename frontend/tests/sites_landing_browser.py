import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
sites=[dict(id=str(i),name=name,brand=brand,cache_geo=geo,base_url=f'https://{name}',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon=name,cache_language='pl',cache_domains=[name,domain],project_status='mass_actions',is_test_project=False,is_active=True,has_menu=False,domains_count=2,internal_pages_count=0) for i,(name,brand,geo,domain) in enumerate([('lemon.pl','Lemon Casino','PL','internal-lemon.pl'),('fontan.pl','Fontan','PL','other-fontan.pl'),('czech.cz','Betonred','CZ','needle-in-network.cz')])]
sites[0]['cache_reserve']='lemon-reserve.pl'
imported=dict(sites[0],id='imported',name='titlewavetees.com',brand='Nine Casino',cache_geo='de_DE',base_url='https://titlewavetees.com',cache_canon='titlewavetees.com',cache_domains=['titlewavetees.com'],project_status='not_in_focus')
state={'posts':0,'polls':0,'imported':False,'fail':False}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path;data=[]
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:]
  if path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=sites+([imported] if state['imported'] else [])
  elif path=='/sites/cache/sync-jobs':
   assert r.request.method=='POST' and r.request.post_data_json=={'names':[]}
   state['posts']+=1;state['polls']=0;data={'id':'cache-job','status':'queued'}
  elif path=='/background-jobs/cache-job':
   state['polls']+=1
   if state['polls']==1:data={'id':'cache-job','status':'running'}
   elif state['fail']:data={'id':'cache-job','status':'failed','error':'Webdev временно недоступен'}
   else:
    state['imported']=True;data={'id':'cache-job','status':'completed','result':{'cache_count':4,'created_count':1,'updated_count':3,'matched_count':4,'projects':[]}}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/sites')
 expect(page.get_by_role('button',name='GEO выборки проектов',exact=True)).to_contain_text('🇵🇱 Польша (PL)')
 table=page.locator('.siteDomainsTable');expect(table.locator('tbody tr')).to_have_count(2)
 expect(table.get_by_role('img',name='Резерв выбран: lemon-reserve.pl',exact=True)).to_be_visible()
 expect(table.locator('.siteReserveChosen')).to_have_count(1)
 expect(table.locator('.siteReserveChosen')).to_have_attribute('title','Резерв выбран: lemon-reserve.pl')
 page.get_by_role('button',name='Lemon Casino, проектов: 1',exact=True).click();expect(table.locator('tbody tr')).to_have_count(1)
 query=page.get_by_role('searchbox',name='Поиск по всем доменам',exact=True)
 query.fill('https://needle-in-network.cz/path/?q=1');expect(table.locator('tbody tr')).to_have_count(1);expect(table.get_by_text('czech.cz',exact=True).first).to_be_visible()
 expect(table.locator('.siteReserveChosen')).to_have_count(0)
 expect(page.get_by_role('status').filter(has_text='Поиск по всем GEO и брендам')).to_be_visible()
 query.fill('not-present.test');expect(table.locator('tbody tr')).to_have_count(0)
 query.fill('');expect(table.locator('tbody tr')).to_have_count(1);expect(table.get_by_text('lemon.pl',exact=True).first).to_be_visible()
 geo=page.get_by_role('button',name='GEO выборки проектов',exact=True)
 geo.click();options=page.get_by_role('listbox').get_by_role('option');expect(options.first).to_contain_text('Все GEO')
 options.filter(has_text='Все GEO').click()
 expect(geo).to_contain_text('Все GEO');expect(table.locator('tbody tr')).to_have_count(1)
 page.get_by_role('button',name='Все бренды, проектов: 3',exact=True).click();expect(table.locator('tbody tr')).to_have_count(3)
 page.reload();expect(geo).to_contain_text('Все GEO');expect(table.locator('tbody tr')).to_have_count(3)
 query.fill('titlewavetees.com');expect(table.locator('tbody tr')).to_have_count(0)
 refresh=page.locator('.topbarActions button[title="Обновить кеш Webdev"]').first
 refresh.click();expect(refresh).to_be_disabled();expect(refresh).to_contain_text('Обмен данными')
 expect(page.locator('.notice')).to_contain_text('Обмен данными с Webdev')
 expect(table.locator('tbody tr')).to_have_count(1,timeout=15000)
 expect(table.get_by_text('titlewavetees.com',exact=True).first).to_be_visible()
 expect(refresh).to_be_enabled();expect(query).to_have_value('titlewavetees.com')
 expect(page.locator('.notice')).to_contain_text('Кеш Webdev обновлён')
 assert state['posts']==1
 # Resume a durable refresh after reload without creating another sync job.
 page.evaluate('localStorage.setItem("pagepilot-sites-cache-sync-job:test","cache-job")')
 state['polls']=0;page.reload();expect(refresh).to_be_disabled()
 expect(refresh).to_be_enabled(timeout=15000);assert state['posts']==1
 state['fail']=True;refresh.click()
 expect(page.locator('.notice')).to_contain_text('Webdev временно недоступен',timeout=15000)
 expect(refresh).to_be_enabled();assert state['posts']==2
 expect(table.get_by_text('titlewavetees.com',exact=True).first).to_be_visible()
 page.screenshot(path=str(DIST.parent/'sites-landing.png'),full_page=True)
 assert not errors,errors
 browser.close()
print('PASS: default PL, All GEO first and persistent, global search, Webdev background refresh imports missing projects, reload resumes without duplicate job, failures retain results')
