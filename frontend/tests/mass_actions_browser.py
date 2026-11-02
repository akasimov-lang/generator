import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
settings={'enabled':True,'execution_mode':'cross_network','schedule_enabled':False,'interval_days':0,'max_projects':100,'scheme_mode':'preserve','auxiliary_hreflangs':[],'selection_filter':None}
requests=[];previews=[]
move_requests=[]
runs=[]
rows=[dict(id=str(i),name=f'p{i}.test',project_name=f'P{i}',brand=b,geo=g,site_type=t,domains=6,drop=2,newreg=4,subdomains=0,amp=0,unknown=0,cache_synced_at=None) for i,(b,g,t) in enumerate([
 ('MerkurXtip','CZ','monobrand'),('MerkurXtip','CZ','monobrand'),('Общие ключи','CZ','general'),('Other','CZ','monobrand'),
 ('MerkurXtip','PL','monobrand'),('Общие ключи','PL','general'),('Mostbet','AZ','monobrand'),('MerkurXtip','DE','monobrand'),
 ('Общие ключи','AZ','general'),('Общие ключи','DE','general'),('Outside','FR','monobrand')])]
sites=[dict(id=r['id'],name=r['name'],brand=r['brand'],site_type=r['site_type'],base_url='https://'+r['name'],publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],external_project_id='project-'+r['id'],cache_canon=r['name'],cache_geo=r['geo'],cache_language='cs',cache_domains=[],project_status='mass_actions',is_test_project=False,has_menu=False,domains_count=6,internal_pages_count=0) for r in rows]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  u=urlparse(r.request.url);path=u.path
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:];data=[]
  if path=='/auth/me':data={'id':'editor','username':'editor','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=sites
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path=='/auto-reglue':data={'settings':settings,'projects':[{'id':r['id'],'name':r['name'],'geo':r['geo'],'config':{'scope':'mass'}} for r in rows],'runs':runs,'tasks':[],'language_pool':[]}
  elif path=='/ai-providers':data=[{'id':'gemini','name':'Gemini','provider_type':'gemini','is_active':True}]
  elif path=='/auto-reglue/settings' and r.request.method=='PUT':
   settings.update(r.request.post_data_json);data=settings
  elif path=='/auto-reglue/move-plus2':
   request=r.request.post_data_json;move_requests.append(request)
   data={'id':request['request_id'],'site_id':'0','status':'completed','phase':'completed','message':'Перенесено',
         'plan':{'manual_action':'move_plus2','execution_mode':'transfer_only','geo':'CZ','brand':'MerkurXtip','source_project':'p1.test','project':'p0.test','domains':[{'domain':'newreg1.test','domain_type':'newreg'},{'domain':'newreg2.test','domain_type':'newreg'}]}}
   runs[:]=[data]
  elif path=='/auto-reglue/content-drafts':
   request=r.request.post_data_json;requests.append(request);data={'results':[{'site_id':sid,'project':next(p['name'] for p in rows if p['id']==sid),'status':'ready','draft_id':'draft','url':'/project-content/p0.test/'} for sid in request['site_ids']]}
  elif path=='/auto-reglue/preview-batch':
   request=r.request.post_data_json;previews.append(request);data={'batch_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','plans':[{'site_id':'0','project':'p0.test','source_project':'p1.test','old_main':'old.test','new_main':'new.test','preview_token':'a'*64,'batch_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','required_page_urls':[],'main_target_kind':'newreg','fallback_reason':'Выбранный резерв в БАН; выбран разрешённый новорег из другой сетки того же бренда и GEO.'}],'skipped':[]}
  elif path=='/auto-reglue/reports':
   q=parse_qs(u.query)
   data={'reports':[{'id':'report','actor':'editor','created_at':'2026-10-19T12:00:00Z','filter':{'brand':'MerkurXtip','geo':'CZ','include_general':False,'site_type':None},'skipped':[], 'entries':[{'run_id':'run','status':'completed','source_project':'p1.test','target_project':'p0.test','domains':['new.test'],'old_main':'old.test','new_main':'new.test','old_fake_main_path':'/old/','new_fake_main_path':'/new/','message':'Подтверждено'}]}] if q.get('brand')==['MerkurXtip'] and q.get('geo')==['CZ'] else []}
  elif path=='/auto-reglue/reports/check':data=None
  elif path=='/auto-reglue/transfer-queue':data={'limit':5,'entries':[]}
  elif path=='/sites/statistics':data={'projects':rows}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/auto-reglue')
 expect(page.get_by_role('heading',name='Статистика · Массовые действия',exact=True)).to_have_count(0)
 expect(page.get_by_role('heading',name='Массовые действия',exact=True)).to_have_count(1)
 expect(page.get_by_role('heading').filter(has_text='Список проектов')).to_be_visible()
 expect(page.locator('.massStatisticsTable')).to_have_count(0)
 expect(page.get_by_text('Проекты в выборке',exact=False)).to_have_count(0)
 picker=page.get_by_role('region',name='Бренды и GEO массовых действий')
 toolbar=page.get_by_label('Массовые действия',exact=True)
 controls=page.locator('.massStatisticsControls')
 expect(picker.get_by_role('button',name='MerkurXtip, проектов: 4',exact=True)).to_be_visible()
 tiles=picker.locator('.peerBrandTile')
 assert tiles.nth(1).locator('.peerBrandCount').inner_text()=='4'
 picker.get_by_role('button',name='Меньше проектов',exact=True).click()
 assert 'Mostbet' in tiles.nth(1).inner_text()
 picker.get_by_role('button',name='Больше проектов',exact=True).click()
 assert picker.get_by_role('group',name='GEO массовых действий').get_by_role('button').count()==5
 assert picker.evaluate('(e)=>e.getBoundingClientRect().top') < toolbar.evaluate('(e)=>e.getBoundingClientRect().top')
 expect(page.locator('.massStatisticsCards')).to_have_count(0)
 def choose_geo(text):
  picker.get_by_role('group',name='GEO массовых действий').get_by_role('button').filter(has_text=text).click()
 def choose_brand(text):
  picker.get_by_role('button').filter(has=page.locator('.peerBrandName',has_text=text)).click()
 expect(picker.get_by_role('button',name='Outside, проектов: 1',exact=True)).to_have_count(0)
 expect(picker.locator('.massGeoCount')).to_have_text(['10','2','4','2','2'])
 for country,flag,code,brand,sid,general in [('Азербайджан','🇦🇿','AZ','Mostbet','6','8'),('Германия','🇩🇪','DE','MerkurXtip','7','9')]:
  choose_geo(country)
  expect(picker.get_by_role('group',name='GEO массовых действий').get_by_role('button',pressed=True)).to_contain_text(flag)
  choose_brand(brand)
  expect(toolbar).to_contain_text('Выбрано: 1')
  expect(page.get_by_role('checkbox',name=f'Выбрать проект p{sid}.test',exact=True)).to_be_checked()
  page.reload()
  expect(picker.get_by_role('group',name='GEO массовых действий').get_by_role('button',pressed=True)).to_contain_text(country)
  expect(picker.get_by_role('button',name=f'{brand}, проектов: 1',exact=True)).to_have_attribute('aria-pressed','true')
  toolbar.get_by_role('button',name='Обрезать 99% контента',exact=True).click()
  page.get_by_role('button',name='Создать черновики (1)',exact=True).click()
  assert requests[-1]['site_ids']==[sid] and requests[-1]['filter']['geo']==code
  page.get_by_label('Включить общие ключи этого GEO',exact=True).check()
  expect(toolbar).to_contain_text('Выбрано: 2')
  page.get_by_role('button',name='Создать черновики (2)',exact=True).click()
  assert set(requests[-1]['site_ids'])=={sid,general} and requests[-1]['filter']['geo']==code
  page.get_by_label('Включить общие ключи этого GEO',exact=True).uncheck()
 choose_geo('Все GEO')
 choose_brand('MerkurXtip')
 expect(toolbar).to_contain_text('Выбрано: 0')
 expect(page.get_by_role('button',name='Move +2',exact=True)).to_be_disabled()
 toolbar.get_by_role('button',name='Обрезать 99% контента',exact=True).click()
 expect(page.get_by_role('button',name='Создать черновики (0)',exact=True)).to_be_disabled()
 choose_geo('Чехия')
 expect(picker.get_by_role('button',name='MerkurXtip, проектов: 2',exact=True)).to_be_visible()
 expect(toolbar).to_contain_text('Выбрано: 2')
 expect(page.get_by_role('heading').filter(has_text='MerkurXtip — CZ')).to_be_visible()
 for sid in ['0','1']:expect(page.get_by_role('checkbox',name=f'Выбрать проект p{sid}.test',exact=True)).to_be_checked()
 for label,action in [('Переписать мета и заголовки','meta_headings'),('Переписать абзацы','paragraphs'),('Обрезать 50% контента','trim_50'),('Обрезать 99% контента','trim_99')]:
  toolbar.get_by_role('button',name=label,exact=True).click()
  page.get_by_role('button',name='Создать черновики (2)',exact=True).click()
  expect(page.get_by_text('Черновик готов',exact=True)).to_have_count(2)
  assert requests[-1]['action']==action and set(requests[-1]['site_ids'])=={'0','1'}
  assert requests[-1]['filter']=={'brand':'MerkurXtip','geo':'CZ','include_general':False,'site_type':None}
 page.get_by_role('checkbox',name='Выбрать проект p1.test',exact=True).uncheck()
 expect(toolbar).to_contain_text('Выбрано: 1')
 page.get_by_role('button',name='Создать черновики (1)',exact=True).click()
 assert requests[-1]['site_ids']==['0']
 page.get_by_label('Включить общие ключи этого GEO',exact=True).check()
 expect(toolbar).to_contain_text('Выбрано: 3')
 page.get_by_role('button',name='Создать черновики (3)',exact=True).click()
 assert set(requests[-1]['site_ids'])=={'0','1','2'} and requests[-1]['filter']['include_general']
 choose_geo('Польша')
 expect(toolbar).to_contain_text('Выбрано: 2')
 page.get_by_role('button',name='Создать черновики (2)',exact=True).click()
 assert set(requests[-1]['site_ids'])=={'4','5'} and requests[-1]['filter']['geo']=='PL'
 page.get_by_label('Включить общие ключи этого GEO',exact=True).uncheck()
 choose_geo('Чехия')
 toolbar.get_by_role('button',name='Перекрёстный автопереклей',exact=True).click()
 base=page.get_by_role('checkbox',name='Базовый Alternate по языку и GEO — с новым фейковым внутряком',exact=True)
 base.check()
 main_policy=page.get_by_role('combobox',name='Тип доменов для переклея',exact=True)
 main_policy.click()
 expect(page.get_by_role('listbox',name='Тип доменов для переклея')).to_be_visible()
 expect(page.get_by_role('listbox',name='Тип доменов для переклея').get_by_role('option')).to_have_count(4)
 main_policy.fill('смешанный')
 expect(page.get_by_role('listbox',name='Тип доменов для переклея').get_by_role('option')).to_have_count(1)
 main_policy.press('Enter')
 sub_new=page.get_by_label('10% переклеев — на поддомен новорега',exact=True)
 sub_drop=page.get_by_label('10% переклеев — на поддомен дропа',exact=True)
 sub_new.check();sub_drop.check()
 expect(page.get_by_text('План для 2 проектов:',exact=False)).to_contain_text('новореги — 1, дропы — 1, поддомены новорегов — 0, поддомены дропов — 0')
 main_policy.click()
 expect(page.get_by_role('listbox',name='Тип доменов для переклея').get_by_role('option')).to_have_count(4)
 main_policy.fill('нет такого режима')
 expect(page.get_by_text('Ничего не найдено. Попробуйте название или код.',exact=True)).to_be_visible()
 main_policy.press('Escape')
 expect(main_policy).to_have_value(__import__('re').compile('Смешанный'))
 main_policy.click();main_policy.fill('Только дропы');main_policy.press('Enter')
 expect(sub_new).not_to_be_checked();expect(sub_new).to_be_disabled()
 expect(sub_drop).to_be_checked()
 main_policy.click();main_policy.fill('Смешанный');main_policy.press('Enter');sub_new.check()
 expect(page.get_by_role('button',name='Подготовить планы (2)',exact=True)).to_be_disabled()
 page.get_by_role('button',name='Сохранить общие настройки',exact=True).click()
 expect(base).to_be_checked()
 assert settings['scheme_mode']=='locale_base'
 assert settings['main_target_mode']=='mixed' and settings['newreg_subdomain_share'] and settings['drop_subdomain_share']
 page.reload()
 page.get_by_text('Настройки, планы и история запусков',exact=True).click()
 expect(page.get_by_role('combobox',name='Тип доменов для переклея',exact=True)).to_have_value(__import__('re').compile('Смешанный'))
 expect(page.get_by_label('10% переклеев — на поддомен новорега',exact=True)).to_be_checked()
 expect(page.get_by_label('10% переклеев — на поддомен дропа',exact=True)).to_be_checked()
 assert settings['selection_filter']['brand']=='MerkurXtip' and settings['selection_filter']['geo']=='CZ'
 page.get_by_role('button',name='Подготовить планы (2)',exact=True).click()
 expect(page.get_by_role('button',name='Запустить группу (1)',exact=True)).to_be_visible()
 expect(page.get_by_text('Фактически подготовлено:',exact=False)).to_contain_text('Новореги — 1')
 expect(page.get_by_role('note')).to_contain_text('Выбранный резерв в БАН')
 assert set(previews[-1]['site_ids'])=={'0','1'} and previews[-1]['filter']['geo']=='CZ'
 choose_geo('Польша')
 expect(page.get_by_role('button',name='Запустить группу (1)',exact=True)).to_have_count(0)
 choose_geo('Чехия')
 report=page.locator('.massReglueReports')
 expect(report.get_by_role('heading',name='Отчёты · MerkurXtip · CZ',exact=True)).to_be_visible()
 for text in ['p0.test','p1.test','/old/','/new/']:
  expect(report.get_by_text(text,exact=text.endswith('.test'))).to_be_visible()
 page.get_by_role('button',name='Move +2',exact=True).click()
 expect(page.get_by_role('status',name='Ход переноса доменов')).to_contain_text('newreg1.test')
 assert set(move_requests[-1]['site_ids'])=={'0','1'} and move_requests[-1]['filter']['geo']=='CZ'
 assert move_requests[-1]['filter']['brand']=='MerkurXtip' and move_requests[-1]['count']==2
 assert page.get_by_role('button',name='Move +1',exact=True).locator('xpath=ancestor::span[contains(@class,"siteDomainsTitle")]').count()==1
 with page.expect_request('**/auto-reglue/move-plus2') as move_one:
  page.get_by_role('button',name='Move +1',exact=True).click()
 assert move_one.value.post_data_json['count']==1
 runs[0]['status']='waiting';runs[0]['phase']='transfer_create'
 runs[0]['domain_progress']=[dict(domain='newreg1.test',domain_type='newreg',stage='adding',source_project='p1.test',target_project='p0.test')]
 expect(page.get_by_role('status',name='Ход переноса доменов')).to_contain_text('Добавление',timeout=10000)
 page.reload()
 expect(page.get_by_role('status',name='Ход переноса доменов')).to_contain_text('Добавление',timeout=10000)
 runs[0]['status']='completed';runs[0]['phase']='completed';runs[0]['domain_progress'][0]['stage']='delivered'
 expect(page.get_by_role('status',name='Ход переноса доменов')).to_contain_text('Подтверждено',timeout=10000)
 page.screenshot(path='/tmp/pagepilot-scoped-actions/desktop.png')
 page.set_viewport_size({'width':390,'height':1000})
 picker.scroll_into_view_if_needed()
 assert picker.evaluate('(e)=>e.getBoundingClientRect().right<=innerWidth+1')
 page.screenshot(path='/tmp/pagepilot-scoped-actions/mobile.png')
 assert not errors,errors
 browser.close()
print('PASS: typed Main policy searchable selection, math rounding, incompatible checkbox reset and saved rules; PL/CZ/AZ/DE GEO chips and counts; AZ/DE reload persistence and isolated actions; unsupported GEO excluded; required searchable brand+GEO; automatic filtered selection and checkbox subset; generic opt-in; all content requests scoped; previews invalidated; persistent brand/GEO report with source and fake paths; mobile')
