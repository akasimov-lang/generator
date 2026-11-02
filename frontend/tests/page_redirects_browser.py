import copy,json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
site=dict(id='redirect-test',name='lemon-casinoss.pl',brand='Lemon Casino',base_url='https://lemon-casinoss.pl',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='lemon-casinoss.pl',cache_geo='PL',cache_language='pl',cache_domains=['lemon-casinoss.pl','other.pl'],project_status='mass_actions',is_test_project=False,has_menu=True,domains_count=2,internal_pages_count=0)
network=dict(canon=site['name'],reserve='',domains=site['cache_domains'],revision='one',main_history=[],x_default_history=[],alternate_history=[],alternateMarkup='',enableAlternates=False,has_head=True,alternates=[],operations=[],has_domain_redirects=True,domain_redirects=[],has_page_redirects=True,page_redirects=[{'domain':site['name'],'redirects':[{'url':'/play/','value':'https://lemon-casinoss.pl/'}]}])
posts=[];state={'fail':False}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1500,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path
  if not path.startswith('/api/'):
   asset=DIST/path.lstrip('/')
   if not asset.is_file():asset=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
  path=path[4:];data=[]
  if path.endswith('/network/operations') and r.request.method=='POST':
   b=r.request.post_data_json;posts.append(b);assert b['action']=='page_redirect'
   if state['fail'] or b['revision']!=network['revision']:
    r.fulfill(status=422 if state['fail'] else 409,content_type='application/json',body=json.dumps({'detail':'Редирект отклонён' if state['fail'] else 'Данные изменились'}));return
   before=copy.deepcopy(network['page_redirects'])
   if b['page_redirect_original_source']:
    for group in network['page_redirects']:
     if group['domain']==b['page_redirect_original_domain']:group['redirects']=[row for row in group['redirects'] if row['url']!=b['page_redirect_original_source']]
   if not b['page_redirect_delete']:
    group=next((g for g in network['page_redirects'] if g['domain']==b['page_redirect_domain']),None)
    if not group:group={'domain':b['page_redirect_domain'],'redirects':[]};network['page_redirects'].append(group)
    group['redirects'].append({'url':b['page_redirect_source'],'value':b['page_redirect_target']})
   network['revision']+='x';network['operations'].insert(0,dict(id=b['request_id'],action='page_redirect',status='confirmed',message='Подтверждено',domain=None,created_at='2026-10-21T10:00:00Z',initiator='test',page_redirects_before=before,page_redirects_after=copy.deepcopy(network['page_redirects'])))
   data=network
  elif path.endswith('/network'):data=network
  elif path.endswith('/network/operations'):data=network['operations']
  elif path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/project-network/lemon-casinoss.pl/')
 panel=page.get_by_role('region',name='Постраничные редиректы',exact=True);table=panel.get_by_role('table')
 expect(table.locator('tbody tr')).to_have_count(1)
 assert panel.evaluate('(el)=>!!(document.querySelector(".networkRedirects").compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING)')
 panel.get_by_role('button',name='Изменить постраничный редирект lemon-casinoss.pl/play/',exact=True).click()
 panel.get_by_label('Постраничный редирект: куда',exact=True).fill('https://lemon-casinoss.pl/new/')
 panel.get_by_role('button',name='Сохранить постраничный редирект',exact=True).click();expect(panel.get_by_role('form')).to_have_count(0)
 expect(table.locator('tbody tr')).to_contain_text('/new/')
 panel.get_by_role('button',name='Добавить постраничный редирект',exact=True).click()
 domain=panel.get_by_role('combobox',name='Домен редиректа',exact=True);domain.click();expect(panel.get_by_role('option')).to_have_count(2)
 domain.fill('other');domain.press('Enter');expect(domain).to_have_value('other.pl')
 panel.get_by_label('Постраничный редирект: откуда',exact=True).fill('/old/')
 panel.get_by_label('Постраничный редирект: куда',exact=True).fill('https://lemon-casinoss.pl/')
 state['fail']=True;panel.get_by_role('button',name='Сохранить постраничный редирект',exact=True).click()
 expect(page.get_by_role('alert')).to_contain_text('Редирект отклонён');expect(panel.get_by_role('form')).to_have_count(1)
 state['fail']=False;panel.get_by_role('button',name='Сохранить постраничный редирект',exact=True).click();expect(table.locator('tbody tr')).to_have_count(2)
 before=len(posts);panel.get_by_role('button',name='Удалить постраничный редирект other.pl/old/',exact=True).click();assert len(posts)==before
 panel.get_by_role('button',name='Удалить редирект',exact=True).click();expect(table.locator('tbody tr')).to_have_count(1)
 page.reload();expect(table.locator('tbody tr')).to_have_count(1)
 page.set_viewport_size({'width':390,'height':844});panel.get_by_role('button',name='Добавить постраничный редирект',exact=True).click()
 page.wait_for_timeout(250)
 assert panel.evaluate('(el)=>el.getBoundingClientRect().right<=innerWidth+1&&el.scrollWidth<=el.clientWidth+1')
 page.screenshot(path=str(DIST.parent/'page-redirects-mobile.png'),full_page=True)
 assert not errors,errors;browser.close()
print('PASS: native page redirect list follows domain redirects, searchable domain picker, edit/add/delete, failure preserves form, reload/mobile and history')
