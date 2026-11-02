"""Technical menu preview, Main links and concurrent exchange status."""
import copy
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
site=dict(id='preview',name='project.test',brand='Lemon Casino',site_type='monobrand',base_url='https://old-main.test',publication_endpoint='/',payload_mode='simple_page',cache_canon='new-main.test',cache_geo='PL',cache_language='pl-PL',homepage_title='Lemon Casino',internal_pages_count=1,domains_count=2,cache_domains=['new-main.test'],default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],main_domain_history=[],alternate_domain_history=[],x_default_history=[],project_status='mass_actions',is_test_project=False,cache_synced_at='2026-10-20T08:00:00Z')
sections=[dict(id='s1',site_id='preview',external_id='1',name='Bonusy',path='/bonusy/',menu_type='header',parent_id=None,sync_status='pending',updated_at='2026-10-20T08:00:00Z')]
content=[dict(id='failed',site_id='preview',section_id='s1',section_content_mode='menu_page',topic='Policy',slug='/policy/',status='publication_failed',generated_at='2026-10-20T08:00:00Z',updated_at='2026-10-20T08:00:00Z',word_count=550,generation_error='Точный текст ошибки контрольной суммы',generated_json=None,competitor_count=0,competitor_research_status='not_requested')]
state={'preview':None,'apply':[],'refresh':None,'requests':[]}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page(viewport={'width':1280,'height':760});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  u=urlparse(r.request.url);path=u.path[4:];data=[]
  if u.hostname=='new-main.test':r.fulfill(content_type='text/html',body='<h1>Live page</h1>');return
  if not u.path.startswith('/api/'):
   asset=DIST/u.path.lstrip('/')
   if not asset.is_file():asset=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
  state['requests'].append((r.request.method,path))
  if path=='/auth/me':data=dict(id='u',username='anton',is_admin=True,is_active=True,allowed_site_ids=None)
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/ai-providers':data=[dict(id='gemini',name='Gemini',provider_type='gemini',is_active=True)]
  elif 'favorite-sites' in path:data={'site_ids':['preview']}
  elif path=='/sites/preview/sections':data=sections
  elif path=='/sites/preview/content':data=content
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path=='/sites/preview/menu-structure-preview':state['preview']=r;return
  elif path=='/sites/preview/generated-menu-structure/apply':
   state['apply'].append(r.request.post_data_json)
   if len(state['apply'])==1:r.fulfill(status=409,content_type='application/json',body=json.dumps({'detail':'Контрольная ошибка добавления: URL уже существует'}));return
   data={'success':True,'created_count':6,'results':[]}
  elif path=='/sites/cache/sync':state['refresh']=r;return
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.context.route('**/*',route)
 page.goto('http://localhost/project-menu/project.test/')
 expect(page.locator('.projectUpdatedAt [role="status"]')).to_have_text('Не синхронизировано: 1')
 expect(page.get_by_text('Точный текст ошибки контрольной суммы',exact=True)).to_be_visible()
 link=page.locator('a.menuTableUrl').filter(has_text='/bonusy/')
 expect(link).to_have_attribute('href','https://new-main.test/bonusy/')
 expect(link).to_have_attribute('target','_blank');assert link.locator('svg').count()==1
 assert link.evaluate('(e)=>getComputedStyle(e).fontSize')=='12px'
 with page.expect_popup() as popup:link.click()
 expect(popup.value).to_have_url('https://new-main.test/bonusy/');popup.value.close()
 page.get_by_role('button',name='Сгенерировать структуру для проекта',exact=True).click()
 mode=page.get_by_role('button',name='Тип структуры меню',exact=True);mode.click()
 expect(page.get_by_role('option')).to_have_count(3)
 search=page.get_by_placeholder('Найти тип структуры');search.fill('нет такого')
 expect(page.get_by_text('Ничего не найдено',exact=True)).to_be_visible();search.press('Escape')
 mode.click();expect(page.get_by_role('option')).to_have_count(3)
 search.fill('Технические');search.press('Enter')
 expect(page.locator('.projectUpdatedAt [role="status"]')).to_contain_text('Обмен данными')
 expect(page.locator('.projectUpdatedAt [role="status"] .spin')).to_be_visible()
 assert state['preview'] is not None and not state['apply']
 assert state['preview'].request.post_data_json['mode']=='technical_pages'
 assert state['preview'].request.post_data_json['levels']==1
 preview=dict(menu_type='header',mode='technical_pages',levels=1,top_level_count=8,geo='PL',language='pl-PL',items=[dict(title='Polityka '+str(n),slug='/policy-'+str(n)+'/',content_kind='technical_page',technical_page_key=key) for n,key in enumerate(['privacy','cookies','terms','disclaimer','responsible_gaming','age','copyright','contacts'])])
 state['preview'].fulfill(content_type='application/json',body=json.dumps(preview))
 expect(page.locator('.generatedMenuPreviewRow')).to_have_count(8)
 expect(page.locator('.projectUpdatedAt [role="status"]')).to_have_text('Не синхронизировано: 1')
 add=page.get_by_role('button',name='Добавить на сайт',exact=True)
 expect(add).to_be_enabled()
 assert add.bounding_box()['y']+add.bounding_box()['height']<=page.viewport_size['height']
 assert page.locator('.generatedMenuStructureBody').evaluate('(e)=>e.scrollHeight>e.clientHeight')
 page.get_by_role('button',name='Изменить пункт 1',exact=True).click()
 page.get_by_role('textbox',name='Название пункта 1',exact=True).fill('Manual privacy')
 page.get_by_role('textbox',name='URL пункта 1',exact=True).fill('/custom-privacy/')
 page.get_by_role('button',name='Готово',exact=True).click()
 page.get_by_role('button',name='Удалить пункт 8',exact=True).click()
 page.get_by_role('button',name='Удалить пункт 7',exact=True).click()
 expect(page.locator('.generatedMenuPreviewRow')).to_have_count(6)
 page.get_by_role('button',name='Изменить пункт 2',exact=True).click()
 page.get_by_role('button',name='Родитель пункта 2',exact=True).click()
 page.get_by_placeholder('Найти родительский пункт').fill('Manual privacy')
 page.get_by_placeholder('Найти родительский пункт').press('Enter')
 expect(page.locator('.generatedMenuPreviewRow.level2')).to_have_count(1)
 expect(page.locator('.generatedMenuPreview > header')).to_contain_text('верхних пунктов: 5')
 page.set_viewport_size({'width':390,'height':844})
 modal=page.locator('.generatedMenuStructureModal')
 assert modal.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1 && e.getBoundingClientRect().right<=innerWidth')
 assert add.bounding_box()['y']+add.bounding_box()['height']<=page.viewport_size['height']
 page.screenshot(path='/tmp/pagepilot-menu-editor-20261020/technical-menu-mobile.png')
 page.set_viewport_size({'width':1280,'height':760})
 page.screenshot(path='/tmp/pagepilot-menu-editor-20261020/technical-menu-desktop.png',full_page=True)
 add.click()
 expect(page.get_by_role('alert')).to_contain_text('Контрольная ошибка добавления')
 expect(page.locator('.generatedMenuPreviewRow')).to_have_count(6)
 assert state['apply'][0]['levels']==2 and state['apply'][0]['top_level_count']==5
 root=state['apply'][0]['items'][0]
 assert root['title']=='Manual privacy' and root['slug']=='/custom-privacy/'
 assert root['children'][0]['slug']=='/custom-privacy/policy-1/'
 add.click()
 expect(page.get_by_role('dialog')).to_have_count(0)
 assert len(state['apply'])==2 and state['apply'][1]==state['apply'][0]
 page.get_by_role('button',name='Сгенерировать структуру для проекта',exact=True).click()
 page.get_by_role('button',name='Уровни структуры меню',exact=True).click()
 page.get_by_placeholder('Найти число уровней').fill('3');page.get_by_placeholder('Найти число уровней').press('Enter')
 page.get_by_role('button',name='Количество пунктов структуры меню',exact=True).click()
 page.get_by_placeholder('Найти количество пунктов').fill('2');page.get_by_placeholder('Найти количество пунктов').press('Enter')
 page.get_by_role('button',name='Сгенерировать',exact=True).click()
 page.wait_for_function('document.querySelector(".generatedMenuStructureModal")!==null')
 assert state['preview'].request.post_data_json['levels']==3 and state['preview'].request.post_data_json['top_level_count']==2
 nested=copy.deepcopy(preview);nested['levels']=3;nested['top_level_count']=2;nested['items']=nested['items'][:2]
 nested['items'][0]['children']=[copy.deepcopy(preview['items'][2])]
 nested['items'][0]['children'][0]['children']=[copy.deepcopy(preview['items'][3])]
 state['preview'].fulfill(content_type='application/json',body=json.dumps(nested))
 expect(page.locator('.generatedMenuPreviewRow.level3')).to_have_count(1)
 expect(page.get_by_role('button',name='Отменить',exact=True)).to_be_enabled()
 page.get_by_role('button',name='Удалить пункт 2',exact=True).click()
 page.get_by_role('button',name='Удалить пункт 1',exact=True).click()
 expect(add).to_be_disabled();expect(page.get_by_role('status').filter(has_text='В предпросмотре нет пунктов')).to_be_visible()
 page.get_by_role('button',name='Отменить',exact=True).click()
 page.get_by_role('button',name='Обновить проект',exact=False).click()
 expect(page.locator('.projectUpdatedAt [role="status"]')).to_contain_text('Обмен данными')
 assert state['refresh'] is not None
 state['refresh'].fulfill(status=400,content_type='application/json',body=json.dumps({'detail':'Ошибка синхронизации'}))
 expect(page.locator('.projectUpdatedAt [role="status"]')).to_have_text('Не синхронизировано: 1')
 assert not errors,errors
 print('PASS: technical menu count/depth, manual titles/URLs/reparenting/deletion, sticky actions on desktop/mobile, preserved preview after apply error, empty preview blocked; Main links and exchange status')
 browser.close()
