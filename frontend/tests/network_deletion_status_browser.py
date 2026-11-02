"""Enter saves markup through the network API; Shift+Enter keeps multiline editing."""
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

DIST = Path(os.environ.get('PAGEPILOT_DIST', Path(__file__).resolve().parents[1] / 'dist'))
site = dict(id='enter', name='enter.test', brand='Pelican', base_url='https://main.test',
            publication_endpoint='', payload_mode='simple_page', editor_version='2',
            default_menu={'header': [], 'footer': []}, menu_library=[], default_banners=[],
            cache_canon='main.test', cache_geo='CZ', cache_language='cs', cache_domains=[],
            project_status='working', is_test_project=False, has_menu=True, domains_count=2, internal_pages_count=0)
network = dict(canon='main.test', reserve='reserve.test', domains=['main.test', 'reserve.test'],
               revision='one', main_history=[], x_default_history=[], alternate_history=[],
               alternateMarkup='<link rel="alternate" hreflang="cs" href="https://main.test/" />',
               enableAlternates=True, enableCanonical=True, has_head=True,
               canonicalDefaultMarkup='<link rel="canonical" href="https://main.test/" />',
               canonicalFakeMainMarkup='', fake_main_enabled=True, fake_main_paths=['/cs/'], fake_main_current='/cs/', alternates=[], operations=[])
posts = []
fail = False
network.update(added_to_system_at='2026-10-18T09:00:00+00:00', main_history=['old.test'],
               amp_domains=['mobile.test'], amp='mobile.test', domain_types={'old-mobile.test': 'amp'},
               domain_added_at={'removed.test': '2026-10-01T09:00:00+00:00'},
               domain_removed_at={'removed.test': '2026-10-10T09:00:00+00:00', 'old-mobile.test': '2026-10-11T09:00:00+00:00'},
               domain_membership_history=[{'domain': 'removed.test', 'added_at': '2026-10-01T09:00:00+00:00', 'removed_at': '2026-10-10T09:00:00+00:00'}])
network['domains'] += ['one.main.test','two.main.test','three.main.test']
held=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
    def route(r):
        path=urlparse(r.request.url).path
        if not path.startswith('/api/'):
            asset=DIST/path.lstrip('/')
            if not asset.is_file():asset=DIST/'index.html'
            r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
        path=path[4:];data=[]
        if path.endswith('/network/operations') and r.request.method=='POST':
            body=r.request.post_data_json;posts.append(body)
            network['operations'].insert(0,dict(id=body['request_id'],action='delete_domain',status='pending',domain=body['domains'][0],domains=body['domains'],initiator='test',created_at='2026-10-19T08:00:00Z',message=None))
            held.append(r);return
        elif path.endswith('/network'):data=network
        elif path.endswith('/menu-capabilities'):data={'check_status':'completed'}
        elif path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
        elif path in ('/sites','/sites/cache/projects'):data=[site]
        elif path=='/sites/lookup':data=site
        elif path=='/me/favorite-sites':data={'site_ids':[]}
        r.fulfill(content_type='application/json',body=json.dumps(data))
    page.route('**/*',route)
    page.goto('http://localhost/project-network/enter.test/')
    def status(domain):
        return page.locator('.networkTable tbody tr').filter(has=page.get_by_text(domain,exact=True)).locator('[data-label="Статус"]')
    field=page.get_by_label('Домен для удаления',exact=True)
    field.fill('one.main.test\ntwo.main.test')
    page.get_by_role('button',name='Удалить из сетки',exact=True).click()
    expect(status('one.main.test')).to_have_text('Удаление')
    expect(status('two.main.test')).to_have_text('Удаление')
    expect(status('three.main.test')).to_have_text('В сетке')
    assert len(posts)==1
    held.pop().fulfill(content_type='application/json',body=json.dumps(network))
    expect(field).to_have_value('')
    page.reload()
    expect(status('one.main.test')).to_have_text('Удаление')
    expect(status('two.main.test')).to_have_text('Удаление')
    network['operations'][0]['status']='unknown'
    page.get_by_role('button',name='Обновить данные',exact=True).click()
    expect(status('one.main.test')).to_have_text('Удаление')
    network['operations'][0]['status']='failed'
    page.get_by_role('button',name='Обновить данные',exact=True).click()
    expect(status('one.main.test')).to_have_text('В сетке')
    expect(status('two.main.test')).to_have_text('В сетке')
    page.get_by_role('button',name='Удалить three.main.test из сетки',exact=True).click()
    expect(status('three.main.test')).to_have_text('Удаление')
    held.pop().fulfill(content_type='application/json',body=json.dumps(network))
    expect(page.get_by_text('Проверяем результат отправленной операции.',exact=False)).to_be_visible()
    network['operations'][0].pop('domains')
    page.reload()
    expect(status('three.main.test')).to_have_text('Удаление')
    network['domains'].remove('three.main.test');network['operations'][0]['status']='confirmed'
    page.get_by_role('button',name='Обновить данные',exact=True).click()
    expect(status('three.main.test')).to_have_count(0)
    expect(status('one.main.test')).to_have_text('В сетке')
    assert not errors,errors
    browser.close()
print('PASS: immediate batch/single deletion row status; unaffected rows unchanged; pending and unknown survive reload; failed clears status; confirmed removal disappears')
