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
state={'link_report':None,'link_requests':[],'pages':[home,internal],'saved':[],'drafts':[],'history':[],'conflict':False,'before':copy.deepcopy(home)}
DIST = Path(os.environ.get('PAGEPILOT_DIST', Path(__file__).resolve().parents[1] / 'dist'))
# The home page deliberately comes after an internal page.
state['pages'] = [internal, home]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000})
 actions=[];errors=[];calls=[];page.on('pageerror',lambda e:errors.append(str(e)))
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
  elif path=='/sites/preview/autolink-pages':
   if method=='POST':
    body=r.request.post_data_json;state['link_requests'].append(body)
    state['link_report']={'id':body['request_id'],'status':'completed','entries':[
     {'key':'bonus','title':'Bonus page','slug':'/bonus/','is_home':False,'status':'confirmed','paragraph':'<a href="/">Brand</a> is linked.','block_index':1,'block_id':'text','message':'Ссылка сохранена.'},
     {'key':'missing','title':'Manual page','slug':'/manual/','is_home':False,'status':'failed','paragraph':'A useful paragraph about payments.','block_index':1,'block_id':'text','message':'Бренд не найден. Добавьте ссылку вручную.'}]}
   data=state['link_report']
  elif path=='/sites/preview/pages/missing':
   data=state['pages'][2]
   if method=='PUT':
    body=r.request.post_data_json;state['saved'].append(body);data.update({key:body[key] for key in ['title','description','content']});data['revision']='b'*64
    state['link_report']['entries'][1].update(status='confirmed',paragraph=body['content']['blocks'][1]['data']['text'],message='Изменения сохранены.')
    data={'id':body['request_id'],'status':'confirmed','page':data}
  elif path=='/sites/preview/pages':data={'pages':state['pages'],'total':2}
  elif path.endswith('/history/version'):data=state['before'] if 'before=true' in r.request.url else home
  elif path.endswith('/history'):data=state['history']
  elif path.endswith('/ai/job'):data=state['drafts'][0]
  elif path.endswith('/ai'):
   if method=='GET':data=state['drafts']
   else:
    body=r.request.post_data_json;result=copy.deepcopy(body['content']);count=int(body['action'].split('_')[1]);actions.append(body);result['blocks'].extend([{'id':f'added-{i}', 'type':'paragraph','data':{'text':f'Additional useful information number {i} about using Brand.'}} for i in range(count)])
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
 missing=copy.deepcopy(internal);missing.update(key='missing',title='Manual page',slug='/manual/')
 missing['content']['blocks'][1]['data']['text']='A useful paragraph about payments.'
 state['pages'].append(missing)
 page.goto('http://localhost/project-content/example.cz/')
 page.goto('http://localhost/page-preview/preview/bonus/?from=%2Fproject-content%2Fexample.cz%2F')
 expect(page.get_by_role('button',name='Редактировать страницу',exact=True)).to_be_visible()
 expect(page.locator('.contentPreviewBody')).to_be_visible()
 page.get_by_role('button',name='Назад',exact=True).click()
 expect(page).to_have_url('http://localhost/project-content/example.cz/')
 start=page.get_by_role('button',name='Автоперелинковка',exact=True)
 expect(start).to_be_visible();start.click()
 expect(page.get_by_text('Удача — 1 · Неудача — 1',exact=True)).to_be_visible()
 assert len(state['link_requests'])==1
 report=page.get_by_role('region',name='Отчёт по автоперелинковке',exact=True)
 expect(report).to_be_visible()
 expect(report.get_by_text('A useful paragraph about payments.',exact=True)).to_be_visible()
 expect(report.locator('a[href="/"]')).to_have_count(1)
 report.get_by_role('button',name='Редактировать',exact=True).last.click()
 expect(page).to_have_url(__import__('re').compile('/page-editor/preview/missing/'))
 editor=page.get_by_role('region',name='Редактор страницы: Manual page',exact=True)
 expect(editor).to_be_visible();assert page.get_by_role('dialog').count()==0
 expect(editor.get_by_role('navigation',name='Хлебные крошки редактора')).to_contain_text('Контент и публикация')
 page.reload();expect(editor).to_be_visible()
 paragraph=page.locator('#page-editor-block-1')
 expect(paragraph).to_contain_text('A useful paragraph about payments.')
 paragraph.get_by_role('button',name='HTML текста',exact=True).click()
 paragraph.locator('textarea').fill('A useful <a href="/">homepage</a> link.')
 expect(editor).to_contain_text('Есть несохранённые изменения')
 page.once('dialog',lambda d:d.dismiss());editor.get_by_role('button',name='Назад',exact=True).click()
 expect(page).to_have_url(__import__('re').compile('/page-editor/preview/missing/'))
 expect(paragraph.locator('textarea')).to_have_value('A useful <a href="/">homepage</a> link.')
 editor.get_by_role('button',name='Сохранить на сайте',exact=True).click()
 expect(editor.get_by_role('button',name='Сохранить на сайте',exact=True)).to_be_disabled()
 assert len(state['saved'])==1
 editor.get_by_role('button',name='Назад',exact=True).click()
 expect(page).to_have_url('http://localhost/project-content/example.cz/')
 expect(page.get_by_text('Удача — 2 · Неудача — 0',exact=True)).to_be_visible()
 expect(page.get_by_role('region',name='Отчёт по автоперелинковке',exact=True)).to_contain_text('A useful homepage link.')
 assert not errors,errors
 page.screenshot(path='/tmp/pagepilot-autolink-report.png');browser.close()
print('PASS: autolink beside refresh; success/failure summary; paragraphs after pages; manual edit route, reload, unsaved Back button protection, save and refreshed report')
