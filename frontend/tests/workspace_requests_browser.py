import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
site=dict(id='preview',name='betonredczech.com',base_url='https://bet-on-red-cz.com',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='bet-on-red-cz.com',cache_geo='CZ',cache_language='cs',homepage_title='BetOnRed Casino CZ 2026 — Recenze, Bonusy, Hry a výběry',internal_pages_count=16,domains_count=17,cache_domains=['bet-on-red-cz.com'],main_domain_history=[],x_default_history=[],alternate_domain_history=[],cache_server_host='dolphin.slf-hostesting.com',project_status='working',is_test_project=False,has_menu=True,cache_synced_at='2026-09-16T12:17:00Z',menu_capabilities_checked_at=None,header_menu_template_rendered=True,footer_menu_template_rendered=True,header_menu_rendered=True,footer_menu_rendered=True,header_menu_nested=True,footer_menu_nested=False)
caps=dict(checked_at=None,header_menu_template_rendered=True,footer_menu_template_rendered=True,header_menu_rendered=True,footer_menu_rendered=True,header_menu_nested=True,footer_menu_nested=False,check_status='completed')
network=dict(canon=site['cache_canon'],reserve='bet-onred-czechia.com',domains=['bet-on-red-cz.com','bet-on-red-czechia.com','bet-onred-cz.com','bet-onred-czechia.com'],main_history=['bet-on-red-cz.com','bet-onred-cz.com'],alternate_history=['bet-on-red-cz.com'],x_default_history=[],revision='mock',alternateMarkup='',enableAlternates=True,has_head=True,operations=[])
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROME'),headless=True)
 page=b.new_page(viewport={'width':1920,'height':1080})
 errors=[]; calls=[]; delayed_archive=[]; delayed_sections=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 def route(r):
  path=r.request.url.split('/api')[-1].split('?')[0]
  calls.append((r.request.method,path))
  if path.endswith('/sections') and not delayed_sections:
   delayed_sections.append(r);return
  if path=='/tasks-archive' and not delayed_archive:
   delayed_archive.append(r);return
  data=[]
  if path=='/auth/me':data={'id':'admin','username':'admin','is_admin':True,'is_active':True}
  elif path=='/sites/lookup':data=site
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/dashboard':data={}
  elif '/favorite-sites' in path:data={'site_ids':['preview']}
  elif path.endswith('/notices/core-update/done'):
   assert r.request.post_data_json == {'stamp':site['core_update_notice']}
   site['core_update_notice']=None
   data=site
  elif path.endswith('/menu-capabilities/check') and site.get('menu_warning'):
   site['menu_warning']=None
   site['header_menu_nested']=True
   caps['header_menu_nested']=True
   caps['check_status']='completed'
   data=caps
  elif '/menu-capabilities' in path:data=caps
  elif path.endswith('/network'):data=network
  elif path=='/auto-reglue/projects/preview':data={'config':{'enabled':False,'scope':'mass','schedule_enabled':False,'interval_days':0,'scheme_mode':'preserve','auxiliary_hreflangs':[],'drop_domain':'','newreg_domain':'','language':'','profile_id':'','variant':'current','fake_main_path':''},'settings':{'enabled':False},'eligible':False,'geo':'CZ','templates':[],'runs':[]}
  elif path.endswith('/overview'):data={'site':site,'stats':{},'recent_content':[]}
  r.fulfill(status=200,content_type='application/json',body=json.dumps(data))
 page.route('**/api/**',route)
 base=os.environ.get('VITE_TEST_URL','http://127.0.0.1:5174')
 page.goto(base)
 page.evaluate('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 page.goto(base+'/project-network/betonredczech.com/')
 expect(page.locator('.networkTable')).to_be_visible()
 assert not delayed_archive, 'Workspace must not request the archive'
 assert not any(path in ['/sites/cache/projects','/tasks','/content','/dashboard','/users'] for _,path in calls), calls
 assert calls.count(('GET','/sites')) == 1
 expect(page.get_by_text('Меню реализовано',exact=True)).to_have_count(2)
 page.wait_for_timeout(200)
 assert not [c for c in calls if c[0]!='GET'],calls
 assert calls.count(('GET','/sites/preview/menu-capabilities'))==1,calls
 assert calls.count(('GET','/sites/preview/network'))==1,calls
 assert not [c for c in calls if c[1].endswith(('/overview','/sections'))],calls
 before=list(calls)
 for label in ['Переклей','Сетка'] * 6:
  page.locator('.workspaceTabs').get_by_role('link',name=label,exact=True).click()
  page.wait_for_timeout(100)
  expect(page.get_by_text('Меню реализовано',exact=True)).to_have_count(2)
  expect(page.get_by_role('heading',name='Автопереклей проекта',exact=True)).to_have_count(0)
  expect(page.locator('.projectNetworkPanel')).to_have_count(1)
 assert calls==before, calls[len(before):]
 page.get_by_role('link',name='Обзор',exact=True).click()
 expect(page.get_by_text('Generated',exact=True)).to_be_visible()
 assert delayed_sections, 'Overview must render while sections are still pending'
 delayed_sections[0].fulfill(status=200,content_type='application/json',body='[]')
 tabs=['Обзор','Генерация','Контент и публикация','Меню','Сетка','Переклей','Автопереклей']
 for label in tabs:
  page.locator('.workspaceTabs').get_by_role('link',name=label,exact=True).click()
  page.wait_for_timeout(150)
 page.get_by_role('link',name='Контент и публикация',exact=True).click()
 page.wait_for_timeout(150)
 before_sections=list(calls)
 nav=page.get_by_role('navigation',name='Разделы публикации')
 for label in ['Кампании','Контент','Процесс','Очередь','Ошибки','Удалённые']:
  nav.get_by_role('button').filter(has_text=label).click()
  page.wait_for_timeout(100)
 assert calls==before_sections, calls[len(before_sections):]
 warmed=list(calls)
 for label in tabs:
  page.locator('.workspaceTabs').get_by_role('link',name=label,exact=True).click()
  page.wait_for_timeout(150)
 assert calls==warmed, calls[len(warmed):]
 assert not [c for c in calls if c[0]!='GET'], calls
 assert calls.count(('GET','/sites/preview/overview')) == 1, calls
 assert calls.count(('GET','/sites/preview/sections')) == 1, calls
 assert calls.count(('GET','/sites/preview/content')) == 1, calls
 assert calls.count(('GET','/sites/preview/network')) == 1, calls
 page.get_by_role('link',name='Сетка',exact=True).click()
 page.get_by_role('button',name='Обновить данные',exact=True).click()
 page.wait_for_timeout(150)
 assert calls.count(('GET','/sites/preview/network')) == 2, calls
 print('All workspace tabs: first-load calls', [c for c in warmed if c not in before], '; repeat navigation: zero requests')

 page.get_by_role('button',name='Запустить точную desktop-проверку меню проекта betonredczech.com',exact=True).click()
 page.wait_for_timeout(300)
 assert [c for c in calls if c[0]=='POST']==[('POST','/sites/preview/menu-capabilities/check')]
 # Reload reads persisted data; no new check is queued.
 before_posts=len([c for c in calls if c[0]=='POST'])
 page.reload();expect(page.get_by_text('Меню реализовано',exact=True)).to_have_count(2)
 assert len([c for c in calls if c[0]=='POST'])==before_posts
 # An unchecked project must not automatically trigger template or live checks either.
 for key in ['header_menu_rendered','footer_menu_rendered','header_menu_template_rendered','footer_menu_template_rendered']:
  site[key]=None; caps[key]=None
 caps['check_status']='not_checked'
 page.reload();expect(page.get_by_text('Не проверено',exact=True)).to_have_count(2)
 page.wait_for_timeout(250)
 assert len([c for c in calls if c[0]=='POST'])==before_posts
 # Saved notices appear even on a cold network tab, without content loading.
 site.update(menu_warning='header_nested',core_update_notice='2026-09-16T20:00:00:item',header_menu_rendered=True,header_menu_nested=False)
 caps.update(header_menu_rendered=True,header_menu_nested=False,check_status='completed')
 page.reload()
 menu_notice=page.locator('.projectMenuImplementationWarning').filter(has_text='Вложенное меню Header')
 core_notice=page.locator('.projectCoreUpdateNotice')
 expect(menu_notice).to_be_visible()
 expect(core_notice).to_be_visible()
 for label in ['Переклей','Автопереклей','Обзор','Контент и публикация','Сетка']:
  page.locator('.workspaceTabs').get_by_role('link',name=label,exact=True).click()
  expect(menu_notice).to_be_visible()
  expect(core_notice).to_be_visible()
 core_notice.get_by_role('button',name='Готово',exact=True).click()
 expect(core_notice).to_have_count(0)
 page.reload()
 expect(core_notice).to_have_count(0)
 expect(menu_notice).to_be_visible()
 menu_notice.get_by_role('button',name='Проверить',exact=True).click()
 expect(menu_notice).to_have_count(0)
 page.reload()
 expect(menu_notice).to_have_count(0)
 expect(core_notice).to_have_count(0)
 # Long project content: the tab bar must remain at the viewport top.
 page.locator('.networkTable').evaluate('(el) => el.style.minHeight = "1800px"')
 page.evaluate('window.scrollTo(0, 900)')
 page.wait_for_timeout(100)
 tabs_bar=page.get_by_role('navigation',name='Вкладки проекта',exact=True)
 assert abs(tabs_bar.bounding_box()['y']) < 2, tabs_bar.bounding_box()
 page.set_viewport_size({'width':390,'height':844})
 tabs_bar.evaluate('(el) => window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top + 300)')
 page.wait_for_timeout(100)
 assert abs(tabs_bar.bounding_box()['y']) < 2, tabs_bar.bounding_box()
 assert tabs_bar.bounding_box()['height'] < 80
 tabs_bar.get_by_role('link',name='Автопереклей',exact=True).click()
 expect(page).to_have_url(base+'/project-auto-reglue/betonredczech.com/')
 assert not errors,errors
 print('PASS: saved legacy results; no automatic checks; one initial network read; zero extra requests across network/reglue tabs; manual check only; reload persists; unchecked stays unchecked.')
 b.close()
