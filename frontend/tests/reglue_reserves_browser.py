import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ.get('PAGEPILOT_DIST','frontend/dist'))
OUT=Path('/tmp/pagepilot-reserve-pool-20261023');OUT.mkdir(exist_ok=True)
rows=[];posts=[];edits=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1820,'height':1050});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path;data=[]
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:]
  if path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path=='/sites/statistics':data={'projects':[]}
  elif path=='/auto-reglue':data={'settings':{'enabled':False,'execution_mode':'cross_network','scheme_mode':'preserve','domain_settings':{},'auxiliary_hreflangs':[]},'projects':[],'tasks':[],'runs':[]}
  elif path=='/auto-reglue/reserves':
   if r.request.method=='POST':
    req=r.request.post_data_json;posts.append(req)
    for i,name in enumerate(['one.test','two.test']):rows.append(dict(id=str(i),domain=name,domain_type=req['domain_type'],brand=req['brand'] or None,status='available',created_at='2026-10-23T09:12:00Z',assigned_at=None,project=None,project_restricted=False,fibery_name=None,error=None,run_status=None))
    data={'added':['one.test','two.test'],'duplicates':[],'errors':[]}
   else:data={'items':rows,'total':len(rows),'available':sum(x['status']=='available' for x in rows),'brands':['Pin-Up','BetOnRed','Lemon Casino']}
  elif path.startswith('/auto-reglue/reserves/'):
   req=r.request.post_data_json;edits.append(req);row=next(x for x in rows if x['id']==path.rsplit('/',1)[1]);row['brand']=req['brand'] or None;data={'id':row['id'],'brand':row['brand']}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route)
 page.goto('http://localhost/auto-reglue')
 shortcut=page.locator('.reservePoolShortcut');expect(shortcut).to_be_visible();expect(shortcut.locator('.reserveCount')).to_have_text('0')
 shortcut.get_by_role('button').click();dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
 brand=dialog.get_by_role('combobox',name='Бренд (необязательно)');brand.click();expect(dialog.get_by_role('option')).to_have_count(4)
 brand.fill('Pin');expect(dialog.get_by_role('option')).to_have_count(1);brand.press('Enter');expect(brand).to_have_value('Pin-Up')
 brand.click();expect(dialog.get_by_role('option')).to_have_count(4);brand.fill('absent');expect(dialog.get_by_text('Ничего не найдено',exact=False)).to_be_visible();brand.press('Escape');expect(brand).to_have_value('Pin-Up');expect(dialog).to_be_visible()
 dialog.get_by_label('Домены',exact=True).fill('one.test, two.test');dialog.get_by_role('button',name='Отправить',exact=True).click()
 expect(dialog.get_by_role('status')).to_contain_text('Добавлено: 2');expect(shortcut.locator('.reserveCount')).to_have_text('2')
 assert posts==[{'domains':'one.test, two.test','brand':'Pin-Up','domain_type':'drop'}]
 dialog.get_by_role('button',name='Закрыть окно').click();expect(dialog).not_to_be_visible();page.screenshot(path=str(OUT/'button-desktop.png'))
 shortcut.get_by_role('link',name='показать').click();expect(page.get_by_role('heading',name='База резервов под переклей',exact=True)).to_be_visible()
 expect(page.locator('.reserveInventory tbody tr')).to_have_count(2)
 row=page.locator('.reserveInventory tbody tr').filter(has_text='one.test');editor=row.get_by_role('combobox');editor.click();editor.fill('Lemon');editor.press('Enter');row.get_by_role('button',name='Сохранить',exact=True).click();expect(row.get_by_role('combobox')).to_have_value('Lemon Casino');assert edits==[{'brand':'Lemon Casino'}]
 rows[1].update(status='assigned',project='network.test',fibery_name='#1716_Lemon_PL',assigned_at='2026-10-23T10:00:00Z',error='WEBDEV_TIMEOUT: ответ не подтверждён',run_status='waiting')
 page.locator('.reserveInventory').get_by_role('button',name='Обновить',exact=True).click();expect(page.get_by_role('link',name='network.test')).to_have_attribute('href','/project-network/network.test/')
 expect(page.get_by_text('WEBDEV_TIMEOUT: ответ не подтверждён')).to_be_visible();expect(page.get_by_text('#1716_Lemon_PL')).to_be_visible()
 page.screenshot(path=str(OUT/'inventory-desktop.png'))
 page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='drops',exact=True).click();expect(dialog).to_be_visible();page.screenshot(path=str(OUT/'import-mobile.png'))
 assert dialog.bounding_box()['width']<=390
 dialog.get_by_role('button',name='Закрыть окно').click();expect(dialog).not_to_be_visible()
 assert not errors,errors
 browser.close()
print('PASS: shared pool button/count, modal, searchable brand/type, Escape, import, per-domain brand edit, table dates/network/Fibery/error, mobile')
