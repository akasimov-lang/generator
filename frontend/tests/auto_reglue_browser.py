import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
site=dict(id='preview',name='betonredczech.com',base_url='https://bet-on-red-cz.com',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='bet-on-red-cz.com',cache_geo='CZ',cache_language='cs',homepage_title='BetOnRed Casino CZ 2026 — Recenze, Bonusy, Hry a výběry',internal_pages_count=16,domains_count=17,cache_domains=['bet-on-red-cz.com'],main_domain_history=[],x_default_history=[],alternate_domain_history=[],cache_server_host='dolphin.slf-hostesting.com',project_status='working',is_test_project=False,has_menu=True,cache_synced_at='2026-09-16T12:17:00Z',menu_capabilities_checked_at=None,header_menu_template_rendered=True,footer_menu_template_rendered=True,header_menu_rendered=True,footer_menu_rendered=True,header_menu_nested=True,footer_menu_nested=False)
caps=dict(checked_at=None,header_menu_template_rendered=True,footer_menu_template_rendered=True,header_menu_rendered=True,footer_menu_rendered=True,header_menu_nested=True,footer_menu_nested=False,check_status='completed')
network=dict(canon=site['cache_canon'],reserve='bet-onred-czechia.com',domains=['bet-on-red-cz.com','bet-on-red-czechia.com','bet-onred-cz.com','bet-onred-czechia.com'],main_history=['bet-on-red-cz.com','bet-onred-cz.com'],alternate_history=['bet-on-red-cz.com'],x_default_history=[],revision='mock',alternateMarkup='',enableAlternates=True,has_head=True,operations=[])
site['project_status']='mass_actions'
cfg=dict(enabled=False,drop_domain='',parent_kind='drop',newreg_domain='',language='',profile_id='',variant='current',fake_main_path='')
global_cfg=dict(enabled=False,auxiliary_hreflangs=[],max_projects=20)
plan=dict(site_id='preview',project=site['name'],old_main='old.test',new_main='new.test',drop_domain='drop.test',alternateMarkup='<link rel="alternate" hreflang="x-default" href="https://drop.test/" />',required_page_urls=[],preview_token='a'*64)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROME'),headless=True)
 page=b.new_page(viewport={'width':1440,'height':1000})
 errors=[];calls=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 def route(r):
  path=r.request.url.split('/api')[-1].split('?')[0];method=r.request.method
  calls.append((method,path))
  task={'site_id':'preview','project':site['name'],'enabled':True,'scope':'personal','interval_days':cfg.get('interval_days',0),'status':'scheduled','url':'/auto-reglue?project_id=preview#auto-task-preview'} if cfg.get('schedule_enabled') and cfg.get('enabled') else None
  data=[]
  if path=='/auth/me':data={'id':'admin','username':'admin','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/dashboard':data={}
  elif '/favorite-sites' in path:data={'site_ids':['preview']}
  elif '/menu-capabilities' in path:data=caps
  elif path.endswith('/network'):data=network
  elif path.endswith('/overview'):data={'site':site,'stats':{},'recent_content':[]}
  elif path=='/auto-reglue':data={'tasks':[task] if task else [],'settings':global_cfg,'projects':[{'id':'preview','name':site['name'],'geo':'AZ','config':cfg}],'runs':[]}
  elif path=='/auto-reglue/settings':
   global_cfg.update(r.request.post_data_json);data=global_cfg
  elif path=='/auto-reglue/projects/preview':
   if method=='PUT':cfg.update(r.request.post_data_json);data=cfg
   else:data={'task':task,'config':cfg,'settings':global_cfg,'eligible':True,'geo':'AZ','templates':[],'runs':[]}
  elif path.endswith('/preview'):data=plan
  elif path=='/auto-reglue/start':data={'results':[{'site_id':'preview','run':{'status':'queued'}}]}
  r.fulfill(status=200,content_type='application/json',body=json.dumps(data))
 page.route('**/api/**',route)
 base=os.environ.get('VITE_TEST_URL','http://127.0.0.1:5174')
 page.goto(base);page.evaluate('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 page.goto(base+'/auto-reglue')
 expect(page.get_by_role('heading',name='Автопереклей — общие настройки')).to_be_visible()
 common=page.get_by_label('Применять общую схему доменов ко всем участникам массового автопереклея',exact=True)
 expect(common).not_to_be_checked()
 common.check()
 none=page.get_by_label('Без фейковых страниц — только URL домена или поддомена',exact=True)
 fresh=page.get_by_label('Создавать новый фейковый внутряк при каждом автопереклее',exact=True)
 current=page.get_by_label('Использовать текущий фейковый внутряк при всех автопереклеях',exact=True)
 expect(none).to_be_checked()
 fresh.check();expect(current).not_to_be_checked();expect(none).not_to_be_checked()
 current.check();expect(fresh).not_to_be_checked()

 page.get_by_label('Создавать новый поддомен новорега при каждом запуске',exact=True).check()
 expect(page.get_by_label('Использовать существующий поддомен дропа',exact=True)).not_to_be_checked()
 page.get_by_label('Общий формат имён поддоменов',exact=True).select_option('hyphen')
 page.get_by_label('Добавлять casino к известным брендам',exact=True).check()
 page.get_by_role('button',name='Сохранить общие настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить общие настройки',exact=True)).to_be_disabled()
 assert global_cfg['domain_settings']['use_current_fake_main'] and not global_cfg['domain_settings']['create_fake_main']
 assert global_cfg['apply_domain_settings']
 assert global_cfg['domain_settings']['create_subdomains'] and global_cfg['domain_settings']['parent_kind']=='newreg'
 assert global_cfg['domain_settings']['subdomain_name_style']=='hyphen'
 common.uncheck()
 page.get_by_role('button',name='Сохранить общие настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить общие настройки',exact=True)).to_be_disabled()

 guide=page.get_by_role('link',name='Инструкция по автопереклеям',exact=True)
 expect(guide).to_be_visible()
 assert guide.evaluate('(e)=>getComputedStyle(e).color') == 'rgb(255, 255, 255)'
 page.wait_for_load_state('networkidle')
 before_guide=list(calls)
 guide.click()
 expect(page).to_have_url(base+'/auto-reglue/guide')
 expect(page.get_by_role('heading',name='Инструкция по автопереклеям',exact=True)).to_be_visible()
 expect(page.get_by_role('navigation',name='Содержание инструкции')).to_be_visible()
 expect(page.get_by_role('heading',name='Однократный автопереклей — по умолчанию')).to_be_visible()
 expect(page.get_by_role('link',name='Инструкция по автопереклеям',exact=True)).to_have_count(0)
 assert calls==before_guide, calls[len(before_guide):]
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 page.get_by_role('button',name='Вернуться к автопереклею',exact=True).click()
 expect(page.get_by_role('heading',name='Автопереклей — общие настройки')).to_be_visible()
 page.set_viewport_size({'width':1440,'height':1000})
 page.get_by_label('Разрешить запуск автопереклеев').check()
 page.get_by_label('Языки для новых фейковых альтернейтов').fill('en, tr')
 page.get_by_label('Включить расписание автопереклеев').check()
 expect(page.get_by_label('Периодичность автопереклея')).to_have_value('0')
 page.get_by_label('Периодичность автопереклея').select_option('4')
 page.get_by_label('Добавлять новый фейковый альтернейт при каждом переклее').check()
 expect(page.get_by_label('Сохранять схему: обновлять адреса и дроп в x-default')).not_to_be_checked()
 page.get_by_role('button',name='Сохранить общие настройки').click()
 expect(page.get_by_role('button',name='Сохранить общие настройки')).to_be_disabled()
 assert global_cfg['interval_days']==4 and global_cfg['schedule_enabled']
 assert global_cfg['scheme_mode']=='add_auxiliary'
 page.goto(base+'/project-redirects/betonredczech.com/')
 expect(page.get_by_role('button',name='Настроить автопереклей')).to_be_visible()
 expect(page.get_by_role('link',name='Инструкция по автопереклеям',exact=True)).to_have_count(0)
 assert not [c for c in calls if c[1]=='/auto-reglue/projects/preview']
 page.get_by_role('button',name='Настроить автопереклей').click()
 page.get_by_label('Дроп для x-default',exact=True).fill('drop.test')
 page.get_by_label('Язык проекта (если не задан в кэше)',exact=True).fill('az')
 page.get_by_role('button',name='Сохранить настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить настройки',exact=True)).to_be_disabled()
 page.get_by_role('button',name='Подготовить переклей',exact=True).click()
 expect(page.get_by_role('button',name='Запустить автопереклей проекта',exact=True)).to_be_visible()
 assert not [c for c in calls if c[1]=='/auto-reglue/start']
 page.get_by_role('button',name='Запустить автопереклей проекта',exact=True).click()
 page.wait_for_timeout(150)
 assert len([c for c in calls if c[1]=='/auto-reglue/start'])==1
 page.goto(base+'/auto-reglue')
 page.locator('.autoReglueProjects input').check()
 page.get_by_role('button',name='Подготовить планы (1)').click()
 page.get_by_role('button',name='Запустить группу (1)').click()
 page.wait_for_timeout(150)
 assert len([c for c in calls if c[1]=='/auto-reglue/start'])==2
 page.goto(base+'/project-redirects/betonredczech.com/')
 page.get_by_role('button',name='Настроить автопереклей').click()
 page.get_by_label('Использовать новорег в x-default',exact=True).check()
 expect(page.get_by_label('Персональный автопереклей — исключить проект из массовых запусков')).not_to_be_checked()
 page.get_by_label('Включить расписание автопереклеев').check()
 page.get_by_label('Участвует в автопереклеях').check()
 page.get_by_label('Периодичность автопереклея').select_option('14')
 page.get_by_label('Сохранять схему: обновлять адреса и дроп в x-default').check()
 page.get_by_label('Использовать новорег в x-default',exact=True).check()
 page.get_by_label('Новорег для x-default',exact=True).fill('newreg.test')
 page.get_by_role('button',name='Сохранить настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить настройки',exact=True)).to_be_disabled()
 assert cfg['scope']=='personal' and cfg['interval_days']==14
 assert cfg['x_default_use_newreg'] and cfg['x_default_newreg_domain']=='newreg.test'
 page.get_by_label('Canonical = x-default; языковые альтернейты на поддомене').check()
 expect(page.get_by_label('Новорег для x-default',exact=True)).to_have_count(0)
 page.get_by_role('button',name='Сохранить настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить настройки',exact=True)).to_be_disabled()
 assert cfg['domain_layout']=='root_main'
 page.get_by_label('Только базовые альтернейты — без фейковых языков и GEO').check()
 expect(page.get_by_label('Сохранять схему: обновлять адреса и дроп в x-default')).not_to_be_checked()
 expect(page.get_by_label('Добавлять новый фейковый альтернейт при каждом переклее')).not_to_be_checked()
 expect(page.get_by_text('При переклее сохраняются ровно три ссылки. Остальные языковые альтернейты удаляются из разметки.',exact=True)).to_be_visible()
 expect(page.get_by_label('Языки для новых фейковых альтернейтов')).to_have_count(0)
 page.get_by_role('button',name='Сохранить настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить настройки',exact=True)).to_be_disabled()
 assert cfg['scheme_mode']=='base_only'
 page.get_by_label('Canonical = домен языковых альтернейтов; x-default отдельно',exact=True).check()
 expect(page.get_by_text('x-default выбирается по порядку из неиспользованных дропов сетки.',exact=False)).to_be_visible()
 expect(page.get_by_label('Новорег для x-default',exact=True)).to_have_count(0)
 page.get_by_role('button',name='Сохранить настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить настройки',exact=True)).to_be_disabled()
 assert cfg['domain_layout']=='subdomain_main'
 drop=page.get_by_label('Переклей на поддомен дропа (создание нового поддомена)',exact=True)
 newreg=page.get_by_label('Переклей на поддомен новорега (создание нового поддомена)',exact=True)
 expect(drop).not_to_be_checked(); expect(newreg).not_to_be_checked()
 drop.check(); expect(newreg).not_to_be_checked()
 expect(page.get_by_label('Формат имени поддомена',exact=True)).to_have_value('mixed')
 newreg.check(); expect(drop).not_to_be_checked()
 page.get_by_label('Формат имени поддомена',exact=True).select_option('hyphen')
 page.get_by_label('Добавлять варианты со словом casino для известных брендов:',exact=False).check()
 page.get_by_role('button',name='Сохранить настройки',exact=True).click()
 expect(page.get_by_role('button',name='Сохранить настройки',exact=True)).to_be_disabled()
 assert cfg['create_subdomains'] and cfg['parent_kind']=='newreg'
 assert cfg['subdomain_name_style']=='hyphen' and cfg['subdomain_add_casino']

 link=page.get_by_role('link',name='Открыть задачу автопереклея →',exact=True)
 expect(link).to_be_visible()
 expect(link).to_have_attribute('href','/auto-reglue?project_id=preview#auto-task-preview')
 toggle=page.get_by_role('button',name='Свернуть настройки',exact=True)
 expect(toggle).to_have_attribute('aria-expanded','true')
 assert page.locator('.autoReglueExpandedPanel').bounding_box()['y'] > toggle.bounding_box()['y']
 link.click()
 expect(page.locator('#auto-task-preview')).to_be_visible()
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 assert not errors,errors
 print('PASS: settings off by default, no work on open, project setup, explicit preview/start, group setup/start, mobile, no JS errors. All API calls mocked.')
 b.close()
