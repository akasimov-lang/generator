import json,mimetypes,copy
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
job={'domain_summary':{'reserve_drops':0,'newregs':1,'drops':0,'other':0},'launch_enabled':True,'id':'b28ebc84-5efa-4737-9d0d-f0f58a200811','mode':'preview','status':'completed','created_at':'2026-10-23T07:00:00Z','ready':1,'counts':{'skipped':1},'progress':{'percent':100,'done':1,'total':2},'events':[],'items':[
 {'site_id':'one','project':'betonred-czechia.com','geo':'CZ','status':'ready','old_main':'old.test','new_main':'new.test','source_project':'donor.test','scheme':'Новорег из другой сетки; внутряк /cz/; с альтернейтами','alternate':'<link rel="alternate" href="https://new.test/cz/" hreflang="cs-CZ" />','progress':100,'canonical':'<link rel="canonical" href="https://{{settings.canon}}/cz/" />','new_fake_path':'/cz/'},
 {'site_id':'two','project':'skipped.test','geo':'PL','status':'skipped','reason':'Уже переклеен на этой неделе (МСК).','progress':100}]}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];posts=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path
  if not path.startswith('/api/'):
   f=ROOT/'frontend/dist'/path.lstrip('/')
   if not f.is_file():f=ROOT/'frontend/dist/index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  data=[]
  if path=='/api/auth/me':data={'id':'anton','username':'anton','is_admin':True,'is_active':True}
  elif path=='/api/auto-reglue/pilot/tasks':
   data={'items':[{'id':job['id'],'status':job['status'],'total':2,'counts':job['counts'],'launched_at':'2026-10-23T07:00:00Z','finished_at':None}] if job['mode']=='execution' else [],'total':1 if job['mode']=='execution' else 0,'has_more':False}
  elif path.startswith('/api/auto-reglue/pilot'):
   if r.request.method=='POST':
    posts.append(path)
    if path=='/api/auto-reglue/pilot':
     job.update(id=r.request.post_data_json['request_id'],mode='preview',status='queued',planning_phase='Подготовка Title/H1',title_h1_progress={'done':1,'total':2})
     r.fulfill(content_type='application/json',body=json.dumps(job));return
    if path.endswith('/rows/one/refresh'):
     job['items'][0].update(alternate='<link rel="alternate" href="https://new.test/cz/" hreflang="cs" />',title_h1_preview={'title_before':'Casino Brand bonus online','title_after':'Casino Brand online bonus','h1_before':'Casino Brand games online','h1_after':'Casino Brand online games'})
     r.fulfill(content_type='application/json',body=json.dumps(job));return
    assert path.endswith('/'+job['id']+'/start'),path
    job.update(mode='execution',status='queued',progress={'percent':55,'done':1,'total':2},ready=0)
    job['items'][0].update(status='waiting',progress=10,run_id='run',phase='delete_domain',confirmation={'started_at':'2026-10-23T07:00:00Z','next_check_at':'2099-01-01T00:00:00Z','attempt':1,'limit':10,'interval_seconds':15})
   data=job
  elif path=='/api/auto-reglue/runs/run/check':
   assert r.request.method=='POST'
   posts.append(path);job['items'][0]['verification']={'status':'confirmed','checked_at':'2026-10-23T15:00:00Z','server':'cobra','message':'Все настройки подтверждены','checks':[{'code':'MAIN','label':'Main','ok':True}]};data=job['items'][0]
  elif path=='/api/auto-reglue/runs/run/cancel':
   assert r.request.method=='POST'
   posts.append(path);job['items'][0].update(status='cancelled',reason='Остановлен пользователем');data=job['items'][0]
  elif path=='/api/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/auto-reglue/pilot')
 expect(page.get_by_role('button',name='Запустить · 1',exact=True)).to_have_count(2)
 expect(page.locator('.pilotUpdated')).to_have_count(0)
 expect(page.locator('.pilotTable tbody tr')).to_have_count(2)
 expect(page.get_by_label('GEO CZ')).to_contain_text('🇨🇿')
 expect(page.locator('.pilotTable')).to_contain_text('hreflang="cs-CZ"')
 assert not posts
 page.locator('.pilotTable details summary').first.click()
 expect(page.locator('.pilotTable details .pilotAlternateChanged')).to_have_text('/cz/')
 # A stalled preview remains restartable; this never invokes /start.
 job.update(status='queued',planning_phase='Подготовка Title/H1',title_h1_progress={'done':1,'total':2})
 page.reload()
 expect(page.get_by_text('Title/H1: 1 из 2.',exact=False)).to_be_visible()
 expect(page.get_by_role('button',name='Запустить · 1',exact=True).first).to_be_disabled()
 page.get_by_role('button',name='Перезапустить планирование',exact=True).click()
 expect(page).to_have_url('http://localhost/auto-reglue/pilot?id='+job['id'])
 assert posts==['/api/auto-reglue/pilot']
 job['status']='completed';page.reload()
 expect(page.get_by_label('Домены в плане')).to_contain_text('На новореги: 1')
 expect(page.get_by_role('progressbar',name='Прогресс betonred-czechia.com',exact=True)).to_have_attribute('value','0')
 expect(page.locator('.pilotRowProgress progress')).to_have_count(2)
 expect(page.get_by_role('button',name='Обновить план betonred-czechia.com')).to_be_enabled()
 page.get_by_role('button',name='Обновить план betonred-czechia.com').click()
 expect(page.locator('.pilotTitleH1').first).to_contain_text('Casino Brand online bonus')
 expect(page.locator('.pilotTitleH1 .pilotRewrittenWord').first).to_contain_text('bonus')
 expect(page.locator('.pilotTable tbody tr').nth(1)).to_contain_text('Уже переклеен на этой неделе')
 for width in [1440,1024]:
  page.set_viewport_size({'width':width,'height':1000})
  assert page.locator('.pilotTable').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
 page.set_viewport_size({'width':1440,'height':1000})
 page.get_by_role('button',name='Запустить · 1',exact=True).last.click()
 expect(page).to_have_url('http://localhost/auto-reglue/pilot/logs?id='+job['id'])
 expect(page.get_by_role('progressbar',name='Выполнение переклея',exact=True)).to_have_attribute('value','55')
 expect(page.get_by_role('progressbar',name='Прогресс betonred-czechia.com',exact=True)).to_have_attribute('value','10')
 expect(page.locator('.transferConfirmation')).to_contain_text('Следующая проверка через')
 page.reload();expect(page.locator('.pilotTable')).to_contain_text('Ждём подтверждения')
 assert len(posts)==3
 job.update(status='completed',progress={'percent':100,'done':2,'total':2},counts={'completed':1,'skipped':1})
 job['items'][0].update(status='completed',progress=100,phase='completed',performed_at='2026-10-23T08:12:00Z')
 job['items'][0]['updated_fields']={'title':True,'h1':True,'alternates':True}
 expect(page.locator('.pilotProgress')).to_contain_text('Успешно: 1',timeout=10000)
 expect(page.locator('.transferConfirmation')).to_have_count(0)
 expect(page.locator('.pilotTable')).to_contain_text('23.10.2026, 11:12:00')
 expect(page.get_by_label('Title обновлён',exact=True)).to_be_visible()
 expect(page.get_by_label('H1 обновлён',exact=True)).to_be_visible()
 expect(page.get_by_label('Альтернейт обновлён',exact=True)).to_be_visible()
 job['items'][0].update(alternate='',alternates_enabled=False)
 page.reload()
 expect(page.locator('.pilotTable')).to_contain_text('Выключены')
 expect(page.get_by_label('Альтернейт обновлён',exact=True)).to_be_visible()
 job['items'][0]['updated_fields']={'title':False,'h1':False,'alternates':True}
 page.reload()
 expect(page.get_by_label('Title обновлён',exact=True)).to_have_count(0)
 expect(page.get_by_label('H1 обновлён',exact=True)).to_have_count(0)
 before=len(posts);page.goto('http://localhost/auto-reglue/pilot')
 expect(page.get_by_role('heading',name='Auto Pilot — массовые переклеи')).to_be_visible()
 expect(page.locator('.pilotTasks tbody tr')).to_have_count(1)
 assert len(posts)==before
 page.get_by_role('link',name='Открыть таблицу').click()
 expect(page.locator('.pilotTable')).to_contain_text('23.10.2026, 11:12:00')
 page.goto('http://localhost/auto-reglue/pilot')
 page.get_by_role('link',name='Запланировать и запустить').click()
 expect(page.get_by_role('button',name='Перезапустить планирование')).to_be_visible()
 assert posts[-1]=='/api/auto-reglue/pilot' and sum(x.endswith('/start') for x in posts)==1
 job.update(mode='execution',status='queued');job['items'][0].update(status='waiting',run_id='run')
 page.goto('http://localhost/auto-reglue/pilot/logs?id='+job['id'])
 before=len(posts)
 expect(page.get_by_role('heading',name='Журнал операций',exact=True)).to_have_count(0)
 page.get_by_role('link',name='Ошибки и примечания · 1',exact=True).click()
 expect(page.get_by_role('heading',name='Auto Pilot — ошибки и примечания')).to_be_visible()
 expect(page.locator('.pilotIssues tbody tr')).to_have_count(1)
 expect(page.locator('.pilotIssues')).not_to_contain_text('skipped.test')
 assert len(posts)==before
 page.get_by_role('tab',name='Журнал операций',exact=True).click()
 expect(page.get_by_role('heading',name='Журнал операций',exact=True)).to_be_visible()
 expect(page.locator('.pilotIssues')).to_have_count(0)
 page.get_by_role('tab',name='Ошибки и примечания',exact=True).click()
 for width in [1440,1024]:
  page.set_viewport_size({'width':width,'height':1000})
  assert page.locator('.pilotIssues').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
 page.get_by_role('button',name='Обновить результат betonred-czechia.com',exact=True).click()
 expect(page.locator('.pilotIssues')).to_contain_text('Проверка Webdev')
 assert posts[-1]=='/api/auto-reglue/runs/run/check' and sum(x.endswith('/start') for x in posts)==1
 page.get_by_role('button',name='Отменить переклей betonred-czechia.com',exact=True).click()
 expect(page.get_by_role('status')).to_contain_text('Ошибок, ожиданий и примечаний нет.')
 expect(page.get_by_role('button',name='Отменить переклей betonred-czechia.com',exact=True)).to_have_count(0)
 assert posts[-1]=='/api/auto-reglue/runs/run/cancel' and sum(x.endswith('/start') for x in posts)==1
 assert not errors,errors
 page.screenshot(path='/tmp/pagepilot-auto-pilot-20261023/browser.png')
 browser.close()
print('PASS: saved plan, exact start once, compact table, GEO, alternates, logs, persisted progress, polling')
