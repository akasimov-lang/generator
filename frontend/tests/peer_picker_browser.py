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
site.update(brand='Lemon Casino',cache_geo='pl-PL',project_status='mass_actions')
sites=[site,*[dict(site,id=str(i),name=name,project_status=status,brand=brand,cache_geo=geo) for i,(name,status,brand,geo) in enumerate([
 ('peer-working.pl','working','Lemon Casino','PL'),('peer-inactive.pl','inactive','Lemon Casino','ru-PL'),
 ('other-geo.cz','mass_actions','Lemon Casino','CZ'),('other-brand.pl','mass_actions','Other','PL'),
 ('similar-brand.pl','mass_actions','Lemon Casino Plus','PL')],1)]]
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
  elif path in ['/sites','/sites/cache/projects']:data=sites
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
 for i,project in enumerate(sites):project['project_team']='4:19' if i==0 else 'Another team'
 sites[1]['project_status']='hands_only'
 sites.append(dict(site,id='other-status',name='geo-ru-but-pl.pl',project_status='geo_ru',project_team='Rankomen'))
 sites.append(dict(site,id='cz-other',name='cz-other.test',brand='Other',cache_geo='CZ',project_status='working',project_team='Other team'))
 sites.append(dict(site,id='de-third',name='de-third.test',brand='Third',cache_geo='DE',project_status='inactive',project_team='Other team'))
 page.goto('http://localhost/sites?geo=PL&brand=Lemon+Casino&from=%2Fproject-generation%2Fexample.cz%2F')
 picker=page.get_by_role('region',name='Бренды и GEO')
 # The selector exposes every GEO on opening, including its selected value.
 geo=page.get_by_role('button',name='GEO выборки проектов',exact=True)
 expect(geo).to_contain_text('🇵🇱 Польша (PL)')
 expect(page.get_by_text('Проекты в выборке · 4',exact=True)).to_be_visible()
 rows=page.locator('.siteProjectDomainLink')
 expect(rows).to_have_count(4)
 assert set(rows.all_text_contents())=={'example.cz','peer-working.pl','peer-inactive.pl','geo-ru-but-pl.pl'}
 lemon=page.get_by_role('button',name='Lemon Casino, проектов: 4',exact=True)
 expect(lemon).to_have_attribute('aria-pressed','true')
 badge=lemon.locator('.peerBrandCount')
 expect(badge).to_have_text('4')
 assert badge.evaluate('(e)=>getComputedStyle(e).backgroundColor==="rgba(0, 0, 0, 0)"')
 a=lemon.bounding_box();b=badge.bounding_box()
 assert abs((a['x']+a['width'])-(b['x']+b['width'])-5)<2
 assert abs((a['y']+a['height'])-(b['y']+b['height'])-3)<2
 geo.click()
 expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(3)
 query=page.get_by_placeholder('Введите страну или код',exact=True)
 query.fill('nothing matches')
 expect(page.get_by_text('Ничего не найдено',exact=True)).to_be_visible()
 query.press('Escape')
 expect(geo).to_contain_text('Польша')
 geo.click();expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(3)
 query.fill('CZ');expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(1);query.press('Enter')
 expect(geo).to_contain_text('🇨🇿 Чехия (CZ)')
 expect(page.get_by_role('button',name='Lemon Casino, проектов: 1',exact=True)).to_have_attribute('aria-pressed','true')
 page.get_by_role('button',name='Other, проектов: 1',exact=True).click()
 expect(rows).to_have_count(1);expect(rows).to_have_text('cz-other.test')
 assert 'geo=CZ' in page.url and 'brand=Other' in page.url
 page.reload();expect(rows).to_have_text('cz-other.test')
 geo.click();query.fill('Германия');query.press('Enter')
 expect(geo).to_contain_text('🇩🇪 Германия (DE)')
 expect(page.get_by_role('button',name='Third, проектов: 1',exact=True)).to_have_attribute('aria-pressed','true')
 expect(rows).to_have_text('de-third.test')
 expect(page.get_by_role('link',name='Назад к проекту',exact=True)).to_have_attribute('href','/project-generation/example.cz/')
 page.set_viewport_size({'width':390,'height':900})
 picker.scroll_into_view_if_needed()
 assert picker.evaluate('(e)=>e.getBoundingClientRect().right<=innerWidth+1')
 assert not errors,errors
 page.screenshot(path='/tmp/pagepilot-peer-picker-mobile.png')
 browser.close()
print('PASS: searchable flag/name/code GEO list, full list and Escape; compact brand tiles and transparent corner counts; all statuses and teams included; brand/GEO switching and reload; source preserved; mobile layout')
