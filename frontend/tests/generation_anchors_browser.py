"""Generation anchor defaults, comma/newline editing, blur saving, error preservation."""
import json,mimetypes,os,re
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
POLISH=['polskie kasyno online','najlepsze kasyna online','kasyna internetowe','kasyno na prawdziwe pieniadze','wypłacalne kasyna internetowe','wypłacalne kasyna','najbardziej wypłacalne kasyno online','kasyno online blik','blik kasyno','kasyno z blikiem']
site=dict(id='e245f30e-6714-466d-baf1-f7242321c713',name='general.pl',base_url='https://general.pl',brand='Общие ключи',site_type='general',project_status='mass_actions',is_active=True,external_project_id='native',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='general.pl',cache_domains=['general.pl'],cache_geo='PL',cache_language='pl',homepage_title='Home',internal_pages_count=2,domains_count=1,has_menu=False,main_domain_history=[],alternate_domain_history=[],x_default_history=[])
saved=None;writes=[];fail=False
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  global saved
  path=urlparse(r.request.url).path
  if not path.startswith('/api/'):
   asset=DIST/path.lstrip('/')
   if not asset.is_file():asset=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
  path=path[4:];data=[];code=200
  if path=='/auth/me':data={'id':'anton','username':'anton','is_admin':True,'is_active':True}
  elif path in ('/sites','/sites/cache/projects'):data=[site]
  elif path=='/sites/lookup':data=site
  elif path.endswith('/pages/generation-anchors'):
   if r.request.method=='PUT':
    writes.append(r.request.post_data_json)
    if fail:code=400;data={'detail':'Не удалось сохранить анкоры'}
    else:saved=list(dict.fromkeys(v.strip() for v in re.split(r'[,\n]+',writes[-1]['anchors']) if v.strip()))
   if code==200:data={'anchors':saved if saved is not None else POLISH if site['site_type']=='general' else [site['brand']],'source':'custom' if saved else 'default'}
  elif path.endswith('/pages/interlinking'):data={'complete':False,'internal_count':0,'linked_from_home':0,'linked_to_home':0,'message':'Нет внутренних страниц.','showcase':{'count':0,'brands':[]}}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path.endswith('/notifications'):data={'items':[],'total':0,'active_count':0}
  r.fulfill(status=code,content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/project-generation/general.pl/')
 field=page.get_by_role('textbox',name='Анкоры на главную',exact=True)
 expect(field).to_have_value('\n'.join(POLISH))
 field.fill('first anchor, second anchor\nfirst anchor')
 page.get_by_role('button',name='Новая задача на генерацию',exact=False).focus()
 expect(field).to_have_value('first anchor\nsecond anchor')
 assert len(writes)==1 and saved==['first anchor','second anchor']
 fail=True;field.fill('not saved anchor');field.press('Tab')
 expect(page.get_by_role('alert').filter(has_text='Не удалось сохранить анкоры')).to_be_visible()
 expect(field).to_have_value('not saved anchor')
 fail=False;page.get_by_role('button',name='Сохранить анкоры',exact=True).click()
 expect(field).to_have_value('not saved anchor');expect(page.get_by_role('button',name='Сохранить анкоры',exact=True)).to_be_disabled()
 site.update(brand='BetOnRed',site_type='monobrand',cache_geo='CZ',cache_language='cs');saved=None
 page.reload();expect(field).to_have_value('BetOnRed')
 page.screenshot(path='/tmp/pagepilot-generation-semantics-20261022/anchors.png',full_page=False)
 assert not errors,errors
 browser.close()
print('PASS: Polish general defaults, monobrand brand default, comma/newline input, save on blur, deduplication, failed edits preserved, explicit retry')
