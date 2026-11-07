"""Run only in a server/container browser; intercept all API and asset requests."""
import copy
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

site = dict(id='preview', name='example.cz', brand='Brand', base_url='https://example.cz',
    cache_canon='example.cz', cache_geo='CZ', cache_language='cs', homepage_title='Home',
    is_active=True, is_test_project=False, project_status='working', site_type='mono',
    default_menu={'header': [], 'footer': []}, menu_library=[], default_banners=[],
    internal_pages_count=0, domains_count=1, cache_domains=['example.cz'],
    main_domain_history=[], x_default_history=[], alternate_domain_history=[])
home = dict(key='home', title='Home', description='Original description', slug='/', is_home=True,
    revision='a'*64, content={'blocks':[{'id':'p','type':'paragraph','data':{'text':'Original paragraph'}}]})
state = {'page':copy.deepcopy(home),'draft':None,'receipt':None,'writes':0}
dist = Path(os.environ.get('PAGEPILOT_DIST', Path(__file__).resolve().parents[1] / 'dist'))

def asset(path):
    name = path.lstrip('/')
    if not name or not (dist/name).is_file():name='index.html'
    return (dist/name).read_bytes(), mimetypes.guess_type(name)[0] or 'application/octet-stream'

with sync_playwright() as pw:
    # No Mac executable fallback: this check is explicitly for container Chromium.
    browser = pw.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
    def route(r):
        parsed=urlsplit(r.request.url);path=parsed.path;method=r.request.method
        if not path.startswith('/api/'):
            data,mime=asset(path);r.fulfill(body=data,content_type=mime);return
        path=path[4:];data=[];status=200
        if path=='/auth/me':data={'id':'user','username':'anton','is_admin':True,'is_active':True,'allowed_site_ids':None}
        elif path in ['/sites','/sites/cache/projects']:data=[site]
        elif path=='/sites/lookup':data=site
        elif 'favorite-sites' in path:data={'site_ids':['preview']}
        elif path.endswith('/overview'):data={'site':site,'stats':{},'recent_content':[]}
        elif path.endswith('/notifications'):data={'items':[],'total':0,'active_count':0}
        elif path=='/sites/preview/pages':data={'pages':[state['page']],'total':1}
        elif path=='/sites/preview/pages/home/draft':
            if method=='PUT':
                body=r.request.post_data_json;state['draft']={**body,'id':body['request_id'],'status':'ready','created_at':'2026-11-07T15:00:00Z','updated_at':'2026-11-07T15:00:00Z'}
            data=None if not state['draft'] or state['receipt'] and state['receipt']['status']=='confirmed' else {**state['draft'],'operation':state['receipt']}
        elif '/edits/' in path:
            data=state['receipt']
            if not data:status=404;data={'detail':'Операция не найдена.'}
        elif path=='/sites/preview/pages/home':
            data=state['page']
            if method=='PUT':
                assert 'background=true' in parsed.query
                body=r.request.post_data_json;state['writes']+=1
                state['receipt']={'id':body['request_id'],'status':'pending','background':True}
                data=state['receipt']
        r.fulfill(status=status,content_type='application/json',body=json.dumps(data))
    page.route('**/*',route)
    url='https://pagepilot.test/page-editor/preview/home/'
    page.goto(url)
    expect(page.get_by_label('Title страницы')).to_have_value('Home')
    page.get_by_label('Title страницы').fill('Updated home')
    page.get_by_role('button',name='Сохранить на сайте',exact=True).click()
    expect(page.get_by_text('Сохраняем в фоне. Можно покинуть страницу; результат появится в проекте.')).to_be_visible()
    expect(page.get_by_role('button',name='Назад',exact=True)).to_be_enabled()
    expect(page.get_by_label('Title страницы')).to_be_disabled()
    page.get_by_role('button',name='Назад',exact=True).click()
    expect(page).not_to_have_url(url)
    assert state['writes']==1
    # Returning while the worker is pending restores the submitted draft.
    page.goto(url)
    expect(page.get_by_label('Title страницы')).to_have_value('Updated home')
    expect(page.get_by_text('Сохраняем в фоне. Можно покинуть страницу.',exact=True)).to_be_visible()
    state['page']={**home,'title':'Updated home','revision':'b'*64}
    state['receipt']={**state['receipt'],'status':'confirmed','page':state['page']}
    expect(page.get_by_text('Изменения сохранены в Webdev и подтверждены.')).to_be_visible(timeout=12000)
    expect(page.get_by_label('Title страницы')).to_be_enabled()
    assert state['writes']==1
    page.get_by_label('Title страницы').fill('Second edit')
    page.get_by_role('button',name='Сохранить на сайте',exact=True).click()
    expect(page.get_by_text('Сохраняем в фоне. Можно покинуть страницу; результат появится в проекте.')).to_be_visible()
    state['receipt']={**state['receipt'],'status':'failed','error':'Страница изменилась в Webdev.'}
    expect(page.get_by_role('alert')).to_contain_text('Страница изменилась',timeout=12000)
    expect(page.get_by_label('Title страницы')).to_have_value('Second edit')
    expect(page.get_by_role('button',name='Назад',exact=True)).to_be_enabled()
    assert state['writes']==2 and not errors,errors
    print('PASS background navigation, draft recovery, polling confirmation, failed draft preserved; 2 submissions')
    browser.close()
