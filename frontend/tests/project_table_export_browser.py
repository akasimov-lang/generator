import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
sites=[dict(id=str(i),name=f'project-{i:03}.test',brand='Brand',cache_geo='PL',base_url=f'https://project-{i:03}.test',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon=f'main-{i}.test',cache_language='pl',cache_domains=[f'project-{i:03}.test'],project_status='mass_actions' if i<60 else 'working' if i<63 else 'not_in_focus',is_test_project=False,is_active=True,has_menu=False,domains_count=2,internal_pages_count=0) for i in range(65)]
exports=[];fail_export=False
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path;data=[]
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:]
  if path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=sites
  elif path=='/sites/export-table':
   exports.append(r.request.post_data_json['site_ids'])
   if fail_export:
    r.fulfill(status=400,content_type='application/json',body=json.dumps({'detail':'Не удалось подготовить Excel'}));return
   data={'filename':'projects.xlsx','content_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','base64':'UEsDBA==','count':len(exports[-1])}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/sites')
 table=page.locator('.siteDomainsTable');expect(table.locator('tbody tr')).to_have_count(50)
 picker=page.get_by_role('button',name='Фильтр проектов по статусу',exact=True)
 expect(picker).to_contain_text('Все статусы · 65')
 picker.click();options=page.get_by_role('listbox').get_by_role('option')
 expect(options).to_have_count(11)
 expect(options.filter(has_text='Массовые действия')).to_have_text('Массовые действия · 60')
 expect(options.filter(has_text='Рабочий')).to_have_text('Рабочий · 3')
 page.get_by_placeholder('Найти статус').fill('mass_actions')
 expect(options).to_have_count(1)
 page.get_by_placeholder('Найти статус').press('Enter')
 expect(picker).to_contain_text('Массовые действия · 60')
 expect(table.locator('tbody tr')).to_have_count(50)
 # Opening a selected value shows every status; Escape keeps the selection.
 picker.click();expect(options).to_have_count(11)
 page.get_by_placeholder('Найти статус').fill('absent-status');expect(options).to_have_count(0)
 page.get_by_placeholder('Найти статус').press('Escape');expect(picker).to_contain_text('Массовые действия · 60')
 download=page.get_by_role('button',name='Скачать таблицу',exact=True)
 with page.expect_download() as saved:download.click()
 assert saved.value.suggested_filename=='projects.xlsx'
 assert len(exports[-1])==60 and set(exports[-1])==set(str(i) for i in range(60)),exports
 picker.click();options.filter(has_text='Рабочий').click()
 expect(table.locator('tbody tr')).to_have_count(3)
 with page.expect_download():download.click()
 assert set(exports[-1])=={'60','61','62'}
 # Exact-domain search must still respect the chosen status.
 search=page.get_by_placeholder('Поиск по домену или имени проекта',exact=True)
 search.fill('project-001.test');expect(table.locator('tbody tr')).to_have_count(0);expect(download).to_be_disabled()
 search.fill('');expect(table.locator('tbody tr')).to_have_count(3)
 fail_export=True;download.click();expect(page.get_by_role('alert')).to_contain_text('Не удалось подготовить Excel');expect(download).to_be_enabled()
 fail_export=False
 picker.click();options.filter(has_text='Все статусы').click();expect(table.locator('tbody tr')).to_have_count(50)
 with page.expect_download():download.click()
 assert len(exports[-1])==65
 page.screenshot(path='/tmp/pagepilot-project-export-20261022/controls.png',full_page=False)
 assert not errors,errors
 browser.close()
print('PASS: all status counts, searchable/keyboard picker, no pagination truncation, filtered XLSX download, empty/error states, exact-domain status filtering')
