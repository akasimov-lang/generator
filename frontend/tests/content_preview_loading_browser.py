"""Metadata-only lists must remain renderable while article bodies are loading."""
import json,os,mimetypes
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
fixture=os.environ.get('PAGEPILOT_CONTENT_FIXTURE')
items=json.loads(Path(fixture).read_text()) if fixture else [dict(id='content',task_id='task',site_id=None,topic='Preview topic',slug='/preview/',status='generated',word_count=20,include_casino_rating=False,generation_progress=100,competitor_research_status='not_requested',competitor_research_progress=0,created_at='2026-10-20T07:11:00Z',updated_at='2026-10-20T07:11:00Z',generated_json={'pages':[{'title':'Preview title','description':'Description','content':{'blocks':[{'id':'p','type':'paragraph','data':{'text':'The loaded article body.'}}]}}]})]
dist=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
 page=browser.new_page();errors=[];fetches=[];fail=False
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path
  if not path.startswith('/api/'):
   f=dist/path.lstrip('/');f=f if f.is_file() else dist/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:];data=[];status=200
  if path=='/auth/me':data={'id':'user','username':'anton','is_admin':True,'is_active':True,'allowed_site_ids':None}
  elif path=='/content':data=[{k:v for k,v in i.items() if k not in {'generated_json','generation_context','competitor_brief'}} for i in items]
  elif path.startswith('/content/') and not path.endswith('/revisions'):
   fetches.append(path);data=next(i for i in items if i['id']==path.split('/')[2])
   if fail:status=400;data={'detail':'Текст временно недоступен'}
  r.fulfill(status=status,content_type='application/json',body=json.dumps(data))
 page.route('**/*',route)
 page.goto('http://localhost/content')
 page.get_by_text('Проект не назначен',exact=True).click()
 for index,item in enumerate(items):
  page.get_by_role('button',name='Просмотр',exact=True).nth(index).click()
  modal=page.locator('.contentPreviewModal')
  expect(page).to_have_url(__import__('re').compile('/content-preview/'+item['id']+'/'))
  expect(modal).to_be_visible()
  expect(modal.locator('.contentPreviewBody')).to_be_visible()
  assert page.get_by_role('dialog').count()==0
  if index==0:
   page.reload();expect(modal.locator('.contentPreviewBody')).to_be_visible()
  assert '/content/'+item['id'] in fetches
  assert not errors,errors
  page.get_by_role('button',name='Назад',exact=True).last.click()
  expect(page).to_have_url('http://localhost/content')
  page.get_by_text('Проект не назначен',exact=True).click()
 fail=True
 page.get_by_role('button',name='Просмотр',exact=True).first.click()
 expect(page.locator('.contentPreviewModal')).to_be_visible()
 expect(page.get_by_text('Текст временно недоступен',exact=True)).to_be_visible()
 page.get_by_role('button',name='Назад',exact=True).last.click()
 page.get_by_text('Проект не назначен',exact=True).click()
 expect(page.get_by_role('button',name='Просмотр',exact=True).first).to_be_visible()
 assert not errors,errors
 browser.close()
print('PASS: standalone preview routes, reload and Back; bodies load on demand; failed fetch remains readable; no page errors')
