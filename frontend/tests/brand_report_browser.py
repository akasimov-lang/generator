import json,mimetypes
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
rows=[dict(id=str(i),name=f'p{i}.test',project_name=f'P{i}',brand=b,geo=g,site_type=t,domains=6,drop=2,newreg=4,subdomains=0,amp=0,unknown=0,cache_synced_at=None) for i,(b,g,t) in enumerate([('MerkurXtip','CZ','monobrand'),('Mostbet','AZ','monobrand'),('Общие ключи','CZ','general')])]
sites=[dict(id=r['id'],name=r['name'],brand=r['brand'],base_url='https://'+r['name'],publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon=r['name'],cache_geo=r['geo'],cache_language='cs',cache_domains=[],project_status='mass_actions',is_test_project=False,has_menu=False,domains_count=6,internal_pages_count=0) for r in rows]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  u=urlparse(r.request.url);path=u.path
  if not path.startswith('/api/'):
   f=ROOT/'frontend/dist'/path.lstrip('/')
   if not f.is_file():f=ROOT/'frontend/dist/index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:];data=[]
  if path=='/auth/me':data={'id':'editor','username':'editor','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=sites
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path=='/sites/statistics':data={'projects':rows if parse_qs(u.query).get('scope',['mass_actions'])[0]=='mass_actions' else rows[:1]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/mass-actions-report')
 total=page.get_by_role('button',name='Всего проектов 3',exact=True);expect(total).to_be_visible()
 page.get_by_role('button',name='MerkurXtip',exact=True).click()
 expect(total).to_be_visible();expect(page.get_by_role('button',name='Сбросить фильтр бренда',exact=True)).to_be_visible()
 search=page.get_by_placeholder('Поиск по домену или имени проекта');search.fill('no-match')
 page.locator('.massStatisticsTable').nth(1).get_by_role('button',name='Бренд',exact=True).click()
 total.click()
 expect(page.get_by_role('button',name='Сбросить фильтр бренда',exact=True)).to_have_count(0)
 expect(page.locator('.massStatisticsTable').nth(1).locator('th').first).to_have_attribute('aria-sort','ascending')
 page.locator('.massStatisticsDetails > summary').click();expect(search).to_have_value('')
 page.get_by_role('button',name='Монобренды 2',exact=True).click();total.click()
 expect(page.get_by_role('button',name='Монобренды 2',exact=True)).to_have_attribute('aria-pressed','false')
 page.locator('.massStatisticsTable').first.locator('tbody button').first.click();total.click()
 expect(page.get_by_role('button',name='Сбросить фильтр GEO',exact=True)).to_have_count(0)
 page.get_by_role('button',name='RU проекты',exact=True).click();page.get_by_role('button',name='Всего проектов 1',exact=True).click()
 expect(total).to_be_visible();expect(page.get_by_role('button',name='Массовые действия',exact=True)).to_have_attribute('aria-pressed','true')
 images=page.locator('.brandTableIcon img');expect(images).to_have_count(2)
 assert images.evaluate_all('(imgs)=>imgs.every(i=>i.complete && i.naturalWidth>0)')
 assert not errors,errors
 print('PASS: brand icons, total count, reset brand/type/sort/category and embedded search')
 browser.close()
