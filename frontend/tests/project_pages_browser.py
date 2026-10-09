"""Editor, default tab, source preservation, AI review, history, Fibery and brand inventory."""
import copy
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

site=dict(id='preview',name='example.cz',brand='Brand',fibery_name='#640_fontan casino_PL',external_project_id='project',base_url='https://example.cz',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='example.cz',cache_geo='CZ',cache_language='cs',homepage_title='Home',internal_pages_count=1,domains_count=2,cache_domains=['example.cz'],main_domain_history=[],x_default_history=['old.test'],alternate_domain_history=[],cache_server_host='test.example',project_status='working',is_test_project=False,has_menu=False,cache_synced_at='2026-10-09T10:00:00Z')
home={'key':'home','title':'Home','description':'Original description','slug':'/','is_home':True,'created_at':'2026-01-15 10:30:00','updated_at':'2026-10-09 09:11:00','revision':'a'*64,'content':{'version':'2.28','blocks':[
 {'id':'heading','type':'header','data':{'text':'Brand overview','level':1}},
 {'id':'text','type':'paragraph','data':{'text':'Brand text with <a href="/terms/">terms</a> and <strong>100</strong> points.'}},
 {'id':'image','type':'image','data':{'file':{'url':'/uploads/brand.webp'},'caption':'Brand image','withBorder':False}},
 {'id':'table','type':'table','data':{'withHeadings':True,'content':[['Condition','Value'],['Bonus','100']]}}
]}}
internal={**copy.deepcopy(home),'key':'bonus','title':'Bonus page','slug':'/bonus/','is_home':False}
state={'pages':[home,internal],'saved':[],'drafts':[],'history':[],'conflict':False,'before':copy.deepcopy(home)}
base=os.environ.get('VITE_TEST_URL','http://127.0.0.1:5178')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];calls=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=r.request.url.split('/api')[-1].split('?')[0];method=r.request.method;calls.append((method,path));data=[];status=200
  if path=='/auth/me':data={'id':'user','username':'anton','is_admin':True,'is_active':True,'allowed_site_ids':None}
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/ai-providers':data=[{'id':'gemini','name':'Gemini','provider_type':'gemini','is_active':True}]
  elif 'favorite-sites' in path:data={'site_ids':['preview']}
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path.endswith('/overview'):data={'site':site,'stats':{},'recent_content':[]}
  elif path=='/sites/preview/pages':data={'pages':state['pages'],'total':2}
  elif path.endswith('/history/version'):data=state['before'] if 'before=true' in r.request.url else home
  elif path.endswith('/history'):data=state['history']
  elif path.endswith('/ai/job'):data=state['drafts'][0]
  elif path.endswith('/ai'):
   if method=='GET':data=state['drafts']
   else:
    body=r.request.post_data_json;result=copy.deepcopy(body['content']);result['blocks'][0]['data']['text']='Rewritten Brand heading'
    data={'id':'job','action':body['action'],'status':'ready','input_content':body['content'],'result_content':result,'created_at':'2026-10-09T10:10:00Z'};state['drafts']=[data]
  elif path.endswith('/interlink'):
   body=r.request.post_data_json;content=copy.deepcopy(body['content']);content['blocks'][1]['data']['text']='<a href="/">Brand</a> text'
   data={'content':content,'changed':True,'message':'Ссылка добавлена в черновик.'}
  elif path in ['/sites/preview/pages/home','/sites/preview/pages/bonus']:
   data=home if path.endswith('home') else internal
   if method=='PUT':
    if state['conflict']:status=409;data={'detail':'Страница изменилась в Webdev. Скопируйте изменения и загрузите заново.'}
    else:
     body=r.request.post_data_json;state['saved'].append(body);data.update({key:body[key] for key in ['title','description','content']});data['revision']='b'*64
     state['history']=[{'id':'version','requested_by':'anton','created_at':'2026-10-09T10:05:00Z','title':data['title']}]
     data={'id':body['request_id'],'status':'confirmed','page':data}
  elif '/edits/' in path:status=404;data={'detail':'Операция не найдена.'}
  elif path=='/auto-reglue':data={'settings':{'enabled':False,'auxiliary_hreflangs':[],'max_projects':20},'projects':[],'runs':[],'tasks':[]}
  elif path=='/auto-reglue/brands':data={'brands':[{'key':'brand','brand':'Brand','project_count':2,'domain_count':8,'projects':[{'id':'preview','name':'example.cz','geo':'CZ','domain_count':2},{'id':'second','name':'other.test','domain_count':6}]}],'transfers_enabled':False}
  r.fulfill(status=status,content_type='application/json',body=json.dumps(data))
 page.route('**/api/**',route)
 page.goto(base+'/project-content/example.cz/')
 expect(page.get_by_role('heading',name='Все страницы')).to_be_visible()
 expect(page.locator('.pp-page-row').first).to_contain_text('Главная')
 expect(page.locator('.pp-page-row').first).to_contain_text('15.01.2026, 10:30')
 expect(page.locator('.pp-page-row').first).to_contain_text('09.10.2026, 09:11')
 expect(page.locator('.publicationWorkflowNav button').first).to_contain_text('2')
 page.screenshot(path='/tmp/pagepilot-pages-dates.png')
 page.locator('.pp-page-row').first.click()
 expect(page.get_by_role('dialog')).to_be_visible()
 expect(page.get_by_label('Title страницы')).to_have_value('Home')
 paragraph=page.locator('.pp-content-block').nth(1).get_by_role('textbox',name='Текст',exact=True)
 expect(paragraph.locator('a')).to_have_attribute('href','/terms/')
 paragraph.fill('Changed Brand text with 100 points.')
 page.get_by_label('Title страницы').fill('Updated home')
 page.get_by_role('button',name='Сохранить на сайте',exact=True).click()
 expect(page.get_by_text('Изменения сохранены в Webdev и подтверждены.')).to_be_visible()
 assert len(state['saved'])==1
 assert state['saved'][0]['content']['blocks'][2]==state['before']['content']['blocks'][2]
 page.get_by_role('button',name='Переписать заголовки',exact=True).click()
 page.get_by_text('Черновики переработки (1)',exact=False).click()
 page.get_by_role('button',name='Просмотреть',exact=True).click()
 expect(page.get_by_text('Rewritten Brand heading',exact=True)).to_be_visible()
 assert len(state['saved'])==1
 page.get_by_role('button',name='Вставить результат в редактор',exact=True).click()
 expect(page.locator('.pp-content-block').first.get_by_role('textbox',name='Текст',exact=True)).to_have_text('Rewritten Brand heading')
 page.get_by_role('button',name='История версий (1)',exact=True).click()
 page.get_by_role('button',name='До изменения',exact=True).click()
 expect(page.locator('.pp-version-preview')).to_contain_text('Original description')
 page.once('dialog',lambda d:d.accept())
 page.get_by_role('button',name='Загрузить версию в редактор',exact=True).click()
 expect(page.get_by_label('Title страницы')).to_have_value('Home')
 # A revision conflict must keep the draft editable and must not suggest a retry of an unknown write.
 state['conflict']=True
 page.get_by_role('button',name='Сохранить на сайте',exact=True).click()
 expect(page.get_by_role('alert').filter(has_text='Страница изменилась')).to_be_visible()
 expect(page.get_by_role('button',name='Проверить сохранение',exact=True)).to_have_count(0)
 expect(page.get_by_label('Title страницы')).to_be_enabled()
 state['conflict']=False
 Path('/tmp/pagepilot-editor-checks').mkdir(exist_ok=True)
 page.screenshot(path='/tmp/pagepilot-editor-checks/desktop.png')
 page.set_viewport_size({'width':390,'height':844})
 assert page.locator('.pp-page-editor').evaluate('(e)=>e.scrollWidth<=innerWidth')
 page.screenshot(path='/tmp/pagepilot-editor-checks/mobile.png')
 page.once('dialog',lambda d:d.dismiss())
 page.get_by_role('button',name='Назад',exact=True).click()
 expect(page.get_by_role('dialog')).to_be_visible()
 page.once('dialog',lambda d:d.accept())
 page.get_by_role('button',name='Назад',exact=True).click()
 page.get_by_role('button',name='Bonus page',exact=False).click()
 page.get_by_role('button',name='Сгенерировать перелинковку',exact=True).click()
 expect(page.locator('.pp-content-block').nth(1).get_by_role('textbox',name='Текст',exact=True).locator('a')).to_have_attribute('href','/')
 assert len(state['saved'])==1
 page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Закрыть редактор',exact=True).click()
 page.set_viewport_size({'width':1440,'height':1000})
 page.goto(base+'/sites')
 expect(page.get_by_text('Имя проекта',exact=True)).to_be_visible()
 expect(page.get_by_text('Name WebDev',exact=True)).to_be_visible()
 expect(page.get_by_text('Страницы',exact=True)).to_be_visible()
 expect(page.get_by_text('x-default',exact=True)).to_have_count(0)
 page.get_by_placeholder('Поиск по домену или имени проекта').fill('fontan casino')
 expect(page.get_by_text('#640_fontan casino_PL',exact=True)).to_be_visible()
 page.goto(base+'/auto-reglue')
 expect(page.get_by_role('heading',name='Бренды и сетки проектов')).to_be_visible()
 field=page.get_by_role('combobox',name='Бренд для межпроектного переклея')
 field.click();field.fill('brand');field.press('Enter')
 expect(page.get_by_text('Бренд выбран для подготовки отдельного теста. Изменений в сетках нет.')).to_be_visible()
 assert not any(method!='GET' and path.startswith('/auto-reglue/') for method,path in calls)
 assert not errors,errors
 browser.close()
print('PASS: all pages, editor, preservation, AI review, history, linking, mobile, Fibery, read-only brands')
