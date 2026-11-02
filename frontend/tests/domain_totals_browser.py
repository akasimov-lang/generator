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
  elif 'favorite-sites' in path:data={'site_ids':[]}
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
 site.update(domains_count=20,network_domain_counts={'drop':12,'newreg':3,'subdomains':5,'amp':0,'unknown':0})
 sites[1].update(domains_count=14,network_domain_counts={'drop':2,'newreg':11,'subdomains':1,'amp':0,'unknown':0})
 sites[2].update(domains_count=0,network_domain_counts={'drop':0,'newreg':0,'subdomains':0,'amp':0,'unknown':0})
 sites.append(dict(site,id='missing',name='unclassified.pl',network_domain_counts={}))
 sites.pop() # The dedicated unknown-count case is checked separately below.
 sites.extend(dict(site,id='extra'+str(i),name='extra-'+str(i)+'.pl',domains_count=3,network_domain_counts={'drop':1,'newreg':2,'subdomains':0,'amp':0,'unknown':0}) for i in range(27))
 page.goto('http://localhost/sites?geo=PL&brand=Lemon+Casino')
 table=page.locator('.siteDomainsTable')
 footer=table.locator('tfoot')
 expect(page.get_by_text('Проекты в выборке · 30',exact=True)).to_be_visible()
 def totals(domains,drops,newreg):
  expect(footer.get_by_text('Итого',exact=True)).to_have_count(0)
  for column,value in [('domainsCount',domains),('dropsCount',drops),('newregCount',newreg)]:
   expect(footer.locator('.column-'+column)).to_have_text(value)
 totals('115','41','68')
 page.get_by_label('Количество строк на странице',exact=True).select_option('25')
 expect(table.locator('tbody tr')).to_have_count(25)
 totals('115','41','68')
 page.get_by_role('button',name='Вперёд',exact=False).click()
 expect(table.locator('tbody tr')).to_have_count(5)
 totals('115','41','68')
 search=page.get_by_placeholder('Поиск по домену или имени проекта',exact=True)
 search.fill('peer-working.pl')
 expect(table.locator('tbody tr')).to_have_count(1)
 totals('14','2','11')
 search.fill('')
 totals('115','41','68')
 page.set_viewport_size({'width':390,'height':900})
 footer.scroll_into_view_if_needed()
 totals('115','41','68')
 assert footer.evaluate('(e)=>e.getBoundingClientRect().right <= innerWidth+1')
 page.set_viewport_size({'width':1440,'height':1000})
 sites.append(dict(site,id='missing',name='unknown-counts.pl',network_domain_counts={}))
 page.reload()
 totals('135','—','—')
 assert not errors,errors
 browser.close()
print('PASS: Domains, Drops and NewReg totals for complete filtered selection; unchanged across pages; search updates totals; mobile footer; unknown counts stay unknown')
