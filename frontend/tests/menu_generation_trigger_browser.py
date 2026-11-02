"""Selecting menu settings never generates; the explicit button sends one request."""
import json,mimetypes
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
site=dict(id='menu-test',name='project.test',brand='Lemon Casino',site_type='monobrand',base_url='https://main.test',publication_endpoint='/',payload_mode='simple_page',cache_canon='main.test',cache_geo='PL',cache_language='pl-PL',homepage_title='Lemon Casino',internal_pages_count=1,domains_count=2,cache_domains=['main.test'],default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],main_domain_history=[],alternate_domain_history=[],x_default_history=[],project_status='mass_actions',is_test_project=False)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});posts=[];errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path
  if not path.startswith('/api/'):
   asset=ROOT/'frontend/dist'/path.lstrip('/')
   if not asset.is_file():asset=ROOT/'frontend/dist/index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0]or'text/plain',body=asset.read_bytes());return
  path=path[4:];data=[]
  if r.request.method=='POST':
   posts.append((path,r.request.post_data_json))
   assert path=='/sites/menu-test/menu-structure-preview',path
   data=dict(menu_type='header',mode='technical_pages',levels=2,top_level_count=3,geo='PL',language='pl-PL',items=[dict(title='Polityka '+str(i),slug='/policy-'+str(i)+'/',content_kind='technical_page')for i in range(3)])
  elif path=='/auth/me':data=dict(id='test',username='test',is_admin=True,is_active=True)
  elif path in ('/sites','/sites/cache/projects'):data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path.endswith('/network/indexing')or path.endswith('/network/sitemap'):data=None
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route)
 page.goto('http://localhost/project-menu/project.test/')
 page.get_by_role('button',name='Сгенерировать структуру для проекта',exact=True).click()
 page.get_by_role('button',name='Тип структуры меню',exact=True).click()
 page.get_by_placeholder('Найти тип структуры').fill('Технические')
 page.get_by_placeholder('Найти тип структуры').press('Enter')
 expect(page.get_by_text('Нажмите «Сгенерировать», чтобы увидеть будущую структуру.',exact=True)).to_be_visible()
 expect(page.get_by_role('button',name='Добавить на сайт',exact=True)).to_be_disabled()
 assert not posts
 page.get_by_role('button',name='Уровни структуры меню',exact=True).click()
 page.get_by_role('option',name='2 уровня',exact=True).click()
 page.get_by_role('button',name='Количество пунктов структуры меню',exact=True).click()
 page.get_by_role('option',name='3',exact=True).click()
 assert not posts
 page.get_by_role('button',name='Сгенерировать',exact=True).click()
 expect(page.locator('.generatedMenuPreviewRow')).to_have_count(3)
 assert len(posts)==1 and posts[0][1]['mode']=='technical_pages' and posts[0][1]['levels']==2 and posts[0][1]['top_level_count']==3
 page.get_by_role('button',name='Тип структуры меню',exact=True).click()
 page.get_by_role('option',name='По тематике проекта',exact=True).click()
 expect(page.locator('.generatedMenuPreviewRow')).to_have_count(0)
 assert len(posts)==1 and not errors,errors
 browser.close()
print('PASS: menu type/levels/count do not generate; explicit Generate submits exactly once')
