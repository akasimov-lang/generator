import json, os
from playwright.sync_api import sync_playwright, expect
site=dict(id='preview',name='betonredczech.com',base_url='https://bet-on-red-cz.com',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='bet-on-red-cz.com',cache_geo='CZ',cache_language='cs',homepage_title='BetOnRed Casino CZ 2026 — Recenze, Bonusy, Hry a výběry',internal_pages_count=16,domains_count=17,cache_domains=['bet-on-red-cz.com'],main_domain_history=[],x_default_history=[],alternate_domain_history=[],cache_server_host='dolphin.slf-hostesting.com',project_status='working',is_test_project=False,has_menu=True,cache_synced_at='2026-09-16T12:17:00Z',menu_capabilities_checked_at=None,header_menu_template_rendered=True,footer_menu_template_rendered=True,header_menu_rendered=True,footer_menu_rendered=True,header_menu_nested=True,footer_menu_nested=False)
caps=dict(checked_at=None,header_menu_template_rendered=True,footer_menu_template_rendered=True,header_menu_rendered=True,footer_menu_rendered=True,header_menu_nested=True,footer_menu_nested=False,check_status='completed')

topic='Casinos Mobiles — подробный обзор популярных игр и способов оплаты на мобильных устройствах'
item=dict(id='content1',site_id='preview',topic=topic,status='published',word_count=1784,include_casino_rating=True,section_id=None,published_at='2026-09-09T00:31:00Z',published_url='https://example.com/mobile/',indexing_task_id='1989438',last_publication_status_code=201,generated_at='2026-09-09T00:30:00Z',created_at='2026-09-09T00:30:00Z')
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ['CHROME'],headless=True)
 page=b.new_page(viewport={'width':390,'height':850});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 def route(r):
  path=r.request.url.split('/api')[-1].split('?')[0];data=[]
  if path=='/auth/me':data=dict(id='admin',username='admin',is_admin=True,is_active=True)
  elif path=='/sites/lookup':data=site
  elif path=='/sites':data=[site]
  elif path.endswith('/content'):data=[item]
  elif path.endswith('/menu-capabilities'):data=caps
  elif path.endswith('/overview'):data=dict(site=site,stats={},recent_content=[])
  elif 'favorite-sites' in path:data={'site_ids':[]}
  r.fulfill(status=200,content_type='application/json',body=json.dumps(data))
 page.route('**/api/**',route)
 base=os.environ.get('VITE_TEST_URL','http://127.0.0.1:5174')
 page.goto(base)
 page.evaluate('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 page.goto(base+'/project-content/betonredczech.com/')
 page.get_by_role('navigation',name='Разделы публикации').get_by_role('button').filter(has_text='Контент').click()
 table=page.locator('.projectContentTable');expect(table).to_be_visible()
 for width in [320,390,540,640,1440]:
  page.set_viewport_size(dict(width=width,height=900))
  title=table.locator('.contentTopicWithRating > span:first-child');expect(title).to_have_text(topic)
  if width<=640:
   assert title.evaluate('(e)=>e.scrollHeight <= e.clientHeight + 1'), 'Title clipped'
   for loc in [table.locator('td'), table.locator('button'),table.locator('a')]:
    for e in loc.all():
     if e.is_visible():
      box=e.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1,(width,box,e.inner_text())
   actions=table.locator('td.column-actions');assert actions.evaluate('(e)=>getComputedStyle(e).flexDirection')=='column'
   assert table.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
  else:
   assert table.locator('td').first.evaluate('(e)=>getComputedStyle(e).display')=='table-cell'
 assert not errors,errors
 b.close()
print('PASS full topic, all fields/actions in viewport at 320/390/540/640; desktop table unchanged')
