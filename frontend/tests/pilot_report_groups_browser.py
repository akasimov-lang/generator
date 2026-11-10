"""Server-only check: deployed UI with real permission-scoped report data."""
import json
import re
import sys
from urllib.parse import parse_qs, urlparse
from fastapi.encoders import jsonable_encoder
from playwright.sync_api import expect, sync_playwright
assert sys.platform != 'darwin', 'Run on the server only.'
from app import pilot_task_cache
from app.db import SessionLocal
USER={'username':'anton','allowed_site_ids':None}
with SessionLocal() as db:
    snapshot=pilot_task_cache.tasks(db,USER,limit=100)
counts=snapshot['group_counts']
assert counts['all']==sum(v for k,v in counts.items() if k!='all')
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[];writes=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
    def assets(route):
        p=urlparse(route.request.url)
        route.fulfill(response=route.fetch(url='http://frontend'+p.path+('?' + p.query if p.query else '')))
    def api(route):
        p=urlparse(route.request.url);path=p.path[4:];q=parse_qs(p.query);data=[]
        if route.request.method!='GET':writes.append(path)
        if path=='/auth/me':data={'id':'anton','username':'anton','is_admin':True,'is_active':True}
        elif 'favorite-sites' in path:data={'site_ids':[]}
        elif path=='/auto-reglue/pilot/tasks':
            with SessionLocal() as db:data=pilot_task_cache.tasks(db,USER,offset=int(q.get('offset',['0'])[0]),q=q.get('q',[''])[0],group=q.get('group',['all'])[0])
        route.fulfill(content_type='application/json',body=json.dumps(jsonable_encoder(data)))
    page.route('**/*',assets);page.route('**/api/**',api)
    page.goto('https://ai-seo-content-panel.site/auto-reglue/pilot/report')
    tabs=page.get_by_role('group',name='Группы отчётов')
    expect(tabs.get_by_role('button')).to_have_count(6)
    expect(tabs).to_contain_text(str(counts['all']))
    for key,label in [('layout','Вёрстка'),('showcases','Витрины'),('reglues','Переклеи'),('brands','Бренды'),('other','Прочее')]:
        button=tabs.get_by_role('button',name=re.compile('^'+label));button.focus();button.press('Enter')
        expect(button).to_have_attribute('aria-pressed','true');expect(page).to_have_url(re.compile('group='+key))
        expect(page.locator('.pilotTasks tbody tr')).to_have_count(min(counts[key],50))
    tabs.get_by_role('button',name=re.compile('^Витрины')).click()
    page.get_by_role('searchbox',name='Поиск заданий').fill('IonicKiss')
    expect(page.locator('.pilotTasks tbody tr')).to_have_count(2)
    page.get_by_role('searchbox',name='Поиск заданий').fill('missing-report-xyz')
    expect(page.get_by_text('По этому запросу заданий не найдено.')).to_be_visible()
    page.get_by_role('button',name='Очистить поиск заданий').click()
    expect(page.locator('.pilotTasks tbody tr')).to_have_count(min(counts['showcases'],50))
    page.reload();expect(tabs.get_by_role('button',name=re.compile('^Витрины'))).to_have_attribute('aria-pressed','true')
    tabs.get_by_role('button',name=re.compile('^Все')).click()
    if counts['all']>50:
        page.locator('.pilotPanel').get_by_role('button',name='Далее',exact=True).click()
        expect(page.locator('.pilotPanel footer')).to_contain_text('51–')
        tabs.get_by_role('button',name=re.compile('^Вёрстка')).click()
        expect(page.locator('.pilotPanel footer')).to_contain_text('1–')
    page.set_viewport_size({'width':390,'height':844})
    expect(tabs).to_be_visible();assert tabs.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
    assert not errors and not writes,(errors,writes)
    browser.close()
print(json.dumps({'status':'passed','counts':counts,'checks':['groups','counts','keyboard','search','empty','reload','pagination','mobile'],'writes':writes,'errors':errors},ensure_ascii=False))
