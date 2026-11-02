"""Domain redirects after network: edit/add, failed save, stale edit, cache reload and mobile."""
import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
site=dict(id='redirect-test',name='pewny-prawnik24.pl',brand='Lemon Casino',base_url='https://lemon-casino9.pl',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='lemon-casino9.pl',cache_geo='PL',cache_language='pl-PL',cache_domains=['lemon-casino9.pl'],project_status='mass_actions',is_test_project=False,has_menu=True,domains_count=1,internal_pages_count=0)
network=dict(canon='lemon-casino9.pl',reserve='',domains=['lemon-casino9.pl'],revision='one',main_history=[],x_default_history=[],alternate_history=[],alternateMarkup='',enableAlternates=False,has_head=True,alternates=[],operations=[],has_domain_redirects=True,domain_redirects=[{'url':d,'value':'lemon-casino9.pl'} for d in ['lemoncasino.jp.net','lemon-casino-pl1.it.com','www.bodzon-psychoterapia.pl','www.biletico.pl']])
posts=[]
fail=False
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1100})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(request):
  path=urlparse(request.request.url).path
  if not path.startswith('/api/'):
   asset=DIST/path.lstrip('/')
   if not asset.is_file():asset=DIST/'index.html'
   request.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
  path=path[4:];data=[]
  if path.endswith('/network/operations') and request.request.method=='POST':
   body=request.request.post_data_json;posts.append(body)
   assert body['action'] in ('domain_redirect','domain_redirects_main')
   if fail or body['revision']!=network['revision']:
    request.fulfill(status=409 if not fail else 422,content_type='application/json',body=json.dumps({'detail':'Настройки изменились. Обновите данные.' if not fail else 'Webdev отклонил редирект.'}));return
   before=list(network['domain_redirects'])
   if body['action']=='domain_redirects_main':
    network['domain_redirects']=[{**row,'value':network['canon']} for row in before if row['url'].removeprefix('www.')!=network['canon'].removeprefix('www.')]
   else:
    row={'url':body['redirect_source'],'value':body['redirect_target']}
    if body['redirect_original_source']:
     network['domain_redirects']=[row if r['url']==body['redirect_original_source'] else r for r in before]
    else:network['domain_redirects'].append(row)
   network['revision']+='x'
   network['operations'].insert(0,dict(id=body['request_id'],action=body['action'],status='confirmed',message='Подтверждено',domain=None,created_at='2026-10-20T11:00:00Z',initiator='test',redirects_before=before,redirects_after=list(network['domain_redirects'])))
   data=network
  elif path.endswith('/network/indexing') or path.endswith('/network/sitemap'):data=None
  elif path.endswith('/network'):data=network
  elif path.endswith('/network/operations'):data=network['operations']
  elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
  elif path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ('/sites','/sites/cache/projects'):data=[site]
  elif path=='/sites/lookup':data=site
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  request.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route)
 page.goto('http://localhost/project-network/pewny-prawnik24.pl/')
 panel=page.get_by_role('region',name='Доменные редиректы',exact=True)
 table=panel.get_by_role('table')
 expect(table.locator('tbody tr')).to_have_count(4)
 assert page.locator('.networkTable').evaluate('(el)=>!!(el.compareDocumentPosition(document.querySelector(".networkRedirects"))&Node.DOCUMENT_POSITION_FOLLOWING)')
 expect(table.get_by_role('link',name='lemoncasino.jp.net',exact=True)).to_have_attribute('href','https://lemoncasino.jp.net/')
 expect(table.get_by_role('link',name='lemoncasino.jp.net',exact=True)).to_have_attribute('target','_blank')
 before_height=table.locator('tbody tr').first.bounding_box()['height']
 panel.get_by_role('button',name='Редактировать редирект lemoncasino.jp.net',exact=True).click()
 expect(panel.get_by_label('Редирект: откуда',exact=True)).to_have_count(0)
 expect(table.locator('tbody tr').first.get_by_label('Редирект: куда',exact=True)).to_be_focused()
 assert abs(table.locator('tbody tr').first.bounding_box()['height']-before_height)<=1
 expect(panel.locator('.networkRedirectForm')).to_have_count(0)
 panel.get_by_label('Редирект: куда',exact=True).fill('cancelled-main.pl')
 panel.get_by_role('button',name='Отменить',exact=True).click()
 expect(table.locator('tbody tr').first).to_contain_text('lemon-casino9.pl')
 assert not posts
 panel.get_by_role('button',name='Редактировать редирект lemoncasino.jp.net',exact=True).click()
 panel.get_by_label('Редирект: куда',exact=True).fill('new-main.pl')
 panel.get_by_label('Редирект: куда',exact=True).press('Enter')
 expect(panel.get_by_role('form')).to_have_count(0)
 expect(table.locator('tbody tr').first).to_contain_text('new-main.pl')
 assert posts[-1]['redirect_original_source']=='lemoncasino.jp.net'
 panel.get_by_role('button',name='Добавить редирект',exact=True).click()
 panel.get_by_label('Редирект: откуда',exact=True).fill('new-source.pl')
 panel.get_by_label('Редирект: куда',exact=True).fill('lemon-casino9.pl')
 fail=True
 panel.get_by_role('button',name='Сохранить редирект',exact=True).click()
 expect(page.locator('.projectNotificationButton')).to_have_attribute('title',__import__('re').compile('Webdev отклонил'))
 expect(panel.get_by_label('Редирект: откуда',exact=True)).to_have_value('new-source.pl')
 expect(table.locator('tbody tr')).to_have_count(4)
 fail=False
 panel.get_by_role('button',name='Сохранить редирект',exact=True).click()
 expect(table.locator('tbody tr')).to_have_count(5)
 assert posts[-1]['redirect_original_source']==''
 # Preserve the edit's original revision even if a background refresh arrives.
 panel.get_by_role('button',name='Редактировать редирект new-source.pl',exact=True).click()
 panel.get_by_label('Редирект: куда',exact=True).fill('edited-main.pl')
 edit_revision=network['revision']
 network['revision']+='remote'
 page.get_by_role('button',name='Обновить данные',exact=True).click()
 expect(page.get_by_role('button',name='Обновить данные',exact=True)).to_be_enabled()
 panel.get_by_role('button',name='Сохранить',exact=True).click()
 expect(page.locator('.projectNotificationButton')).to_have_attribute('title',__import__('re').compile('Настройки изменились'))
 assert posts[-1]['revision']==edit_revision
 panel.get_by_label('Редирект: куда',exact=True).press('Escape')
 page.reload()
 expect(table.locator('tbody tr')).to_have_count(5)
 expect(table.locator('tbody tr').last).to_contain_text('lemon-casino9.pl')
 bulk=panel.get_by_role('button',name='Редирект на Main',exact=True)
 expect(bulk).to_be_enabled()
 bulk.click()
 expect(bulk).to_be_disabled()
 assert posts[-1]['action']=='domain_redirects_main'
 assert all(row['value']==network['canon'] for row in network['domain_redirects'])
 assert len(network['domain_redirects'])==5
 expect(page.get_by_text('Все доменные редиректы на текущий Main',exact=False).first).to_be_visible()
 page.reload()
 expect(bulk).to_be_disabled()
 panel.scroll_into_view_if_needed();page.screenshot(path='/tmp/pagepilot-domain-redirects-20261020/desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 panel.get_by_role('button',name='Добавить редирект',exact=True).click()
 expect(panel.get_by_label('Редирект: откуда',exact=True)).to_be_visible()
 page.screenshot(path='/tmp/pagepilot-domain-redirects-20261020/mobile.png',full_page=True)
 assert panel.evaluate('(el)=>el.getBoundingClientRect().right<=innerWidth+1 && el.scrollWidth<=el.clientWidth+1')
 page.screenshot(path='/tmp/pagepilot-domain-redirects-20261020/mobile.png',full_page=True)
 assert not errors,errors
 browser.close()
print('PASS: four cached redirects, placement, edit/add, failed save retention, stale edit protection, reload, links and mobile')
