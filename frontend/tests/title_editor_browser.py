"""Editor, default tab, source preservation, AI review, history, Fibery and brand inventory."""
import copy
import json
import os
import mimetypes
from urllib.parse import urlparse
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
DIST = Path(os.environ.get('PAGEPILOT_DIST', Path(__file__).resolve().parents[1] / 'dist'))
# The home page deliberately comes after an internal page.
state['pages'] = [internal, home]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];calls=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  parsed = urlparse(r.request.url)
  if not parsed.path.startswith('/api/'):
   asset = DIST / parsed.path.lstrip('/')
   if not asset.is_file(): asset = DIST / 'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream', body=asset.read_bytes());return
  path=parsed.path[4:];method=r.request.method;calls.append((method,path));data=[];status=200
  if path=='/auth/me':data={'id':'user','username':'anton','is_admin':True,'is_active':True,'allowed_site_ids':None}
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/ai-providers':data=[{'id':'gemini','name':'Gemini','provider_type':'gemini','is_active':True}]
  elif 'favorite-sites' in path:data={'site_ids':['preview']}
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path.endswith('/auto-lb'):data={'context':{'brand':'Brand','geo':'CZ','language':'cs','main':'example.cz','main_url':'https://example.cz'},'context_error':None,'provider_ready':True,'anchor_count':100,'topic_count':300,'topic_text':'','prompts':{},'generations':[]}
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
 page.route('**/*',route)
 for path, source in [('/project-generation/example.cz/', 'Генерация'), ('/project-auto-lb/example.cz/', 'АвтоЛБ')]:
  page.goto('http://localhost'+path)
  trigger=page.get_by_role('button',name='Открыть редактор главной страницы',exact=True)
  expect(trigger).to_be_visible()
  page.evaluate("document.body.style.minHeight='2400px';window.scrollTo(0,70)")
  trigger.scroll_into_view_if_needed()
  origin=page.evaluate('({left:scrollX,top:scrollY})')
  trigger.click()
  expect(page.get_by_role('dialog')).to_be_visible()
  expect(page.get_by_label('Title страницы',exact=True)).to_have_value('Home')
  crumbs=page.get_by_role('navigation',name='Хлебные крошки редактора')
  expect(crumbs).to_contain_text('example.cz')
  expect(crumbs).to_contain_text(source)
  expect(crumbs.locator('[aria-current=page]')).to_have_text('Главная страница')
  assert page.url.endswith(path)
  page.get_by_role('button',name='Назад',exact=True).click()
  expect(page.get_by_role('dialog')).to_have_count(0)
  assert page.url.endswith(path)
  assert page.evaluate('({left:scrollX,top:scrollY})')==origin
  trigger.focus();trigger.press('Enter')
  expect(page.get_by_label('Title страницы',exact=True)).to_have_value('Home')
  page.get_by_label('Title страницы',exact=True).fill('Unsaved home')
  page.once('dialog',lambda dialog:dialog.dismiss())
  page.get_by_role('button',name='Назад',exact=True).click()
  expect(page.get_by_role('dialog')).to_be_visible()
  page.once('dialog',lambda dialog:dialog.accept())
  crumbs.get_by_role('button',name=source,exact=True).click()
  expect(page.get_by_role('dialog')).to_have_count(0)
  assert page.url.endswith(path)
 # Missing home must stay in the source section and show a clear error.
 state['pages']=[internal]
 trigger.click()
 expect(page.get_by_text('Главная страница проекта не найдена в Webdev.',exact=True)).to_be_visible()
 expect(page.get_by_role('dialog')).to_have_count(0)
 assert page.url.endswith('/project-auto-lb/example.cz/')
 assert not any(method!='GET' for method,path in calls),calls
 assert not errors,errors
 browser.close()
print('PASS: home identified by is_home; dynamic breadcrumbs; Back restores origin and scroll; keyboard; dirty confirmation; missing home')
