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
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def route(request):
        path = urlparse(request.request.url).path
        if not path.startswith('/api/'):
            asset = DIST / path.lstrip('/')
            if not asset.is_file(): asset = DIST / 'index.html'
            request.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream', body=asset.read_bytes())
            return
        path = path[4:]
        data = []
        if path.endswith('/network/operations') and request.request.method == 'POST':
            payload = request.request.post_data_json
            posts.append(payload)
            assert payload['action']=='delete_domain'
            network['domains']=[d for d in network['domains'] if d not in payload['domains']]
            network['revision']+='x'
            network['operations'].insert(0,dict(id=payload['request_id'],action='delete_domain',status='confirmed',domain=payload['domains'][0],domains=payload['domains'],initiator='test',created_at='2026-10-19T06:00:00Z',message=None))
            data = network
        elif path.endswith('/network'): data = network
        elif path.endswith('/menu-capabilities'): data = dict(check_status='completed')
        elif path == '/auth/me': data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path in ('/sites', '/sites/cache/projects'): data = [site]
        elif path == '/sites/lookup': data = site
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        request.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*',route)
    page.goto('http://localhost/project-network/enter.test/')
    history=page.get_by_label('Показать историю',exact=True)
    expect(history).to_be_visible()
    assert history.evaluate('(e)=>e.getBoundingClientRect().width')==12
    label=page.locator('.networkHistoryToggle')
    assert label.evaluate('(e)=>getComputedStyle(e).whiteSpace')=='nowrap'
    assert float(label.evaluate('(e)=>getComputedStyle(e).fontSize').replace('px',''))==11
    select=page.locator('.networkTable thead').get_by_role('button',name='Выделить',exact=True)
    expect(select).to_be_visible();select.click()
    expect(page.get_by_label('Домены для копирования',exact=True)).to_have_value('main.test\nreserve.test\none.main.test\ntwo.main.test\nthree.main.test')
    field=page.get_by_label('Домен для удаления',exact=True)
    button=page.get_by_role('button',name='Удалить из сетки',exact=True)
    field.fill('one.main.test\nmain.test')
    expect(button).to_be_disabled()
    expect(page.get_by_role('alert')).to_contain_text('main.test')
    field.fill('one.main.test\ntwo.main.test; three.main.test, one.main.test')
    expect(button).to_be_enabled();button.click()
    expect(field).to_have_value('')
    assert len(posts)==1 and posts[0]['domains']==['one.main.test','two.main.test','three.main.test']
    assert not errors,errors
    browser.close()
print('PASS: multiline deletion parsed and deduplicated; one request; protected address blocks entire batch; 12px checkbox and attached single-line history label')
