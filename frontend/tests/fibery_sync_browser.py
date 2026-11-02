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
remote_name='#1715_lemon casino_PL_NEWSPLIT'
site.update(fibery_name=None,fibery_name_manual=True,project_status='mass_actions')
fail = False
network.update(added_to_system_at='2026-10-18T09:00:00+00:00', main_history=['old.test'],
               amp_domains=['mobile.test'], amp='mobile.test', domain_types={'old-mobile.test': 'amp'},
               domain_added_at={'removed.test': '2026-10-01T09:00:00+00:00'},
               domain_removed_at={'removed.test': '2026-10-10T09:00:00+00:00', 'old-mobile.test': '2026-10-11T09:00:00+00:00'},
               domain_membership_history=[{'domain': 'removed.test', 'added_at': '2026-10-01T09:00:00+00:00', 'removed_at': '2026-10-10T09:00:00+00:00'}])
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
            assert payload['action'] in ('alternates', 'select_fake_main'), payload
            if fail:
                request.fulfill(status=422, content_type='application/json', body=json.dumps({'detail': 'Не удалось сохранить тестовую разметку'}))
                return
            network.update(alternateMarkup=payload['alternate_markup'], enableAlternates=payload['enable_alternates'])
            if 'enable_canonical' in payload: network['enableCanonical'] = payload['enable_canonical']
            if 'enable_dynamic_routes' in payload: network['fake_main_enabled'] = payload['enable_dynamic_routes']
            for key, field in [('canonical_default_markup', 'canonicalDefaultMarkup'), ('canonical_fake_main_markup', 'canonicalFakeMainMarkup')]:
                if key in payload: network[field] = payload[key]
            network['revision'] += 'x'
            network['operations'].insert(0, dict(id=payload['request_id'], action=payload['action'], status='confirmed', domain=None,
                                                initiator='test', created_at='2026-10-19T06:00:00Z', message=None))
            data = network
        elif path.endswith('/network'):
            site['fibery_name']=remote_name
            network['fibery_name']=remote_name
            data=network
        elif path.endswith('/menu-capabilities'): data = dict(check_status='completed')
        elif path == '/auth/me': data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path in ('/sites', '/sites/cache/projects'): data = [site]
        elif path == '/sites/lookup': data = site
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        request.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('http://localhost/project-network/enter.test/')
    name=page.locator('.workspaceFiberyName')
    expect(name).to_contain_text('#1715_lemon casino_PL_NEWSPLIT')
    expect(name.locator('a')).to_have_attribute('href','https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/1715')
    revision=network['revision']
    remote_name='#999_Changed_In_Webdev'
    page.get_by_role('button',name='Обновить данные',exact=True).click()
    expect(name).to_contain_text('#999_Changed_In_Webdev')
    expect(name.locator('a')).to_have_attribute('href','https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/999')
    assert network['revision']==revision
    assert site['fibery_name_manual'] is True and site['project_status']=='mass_actions'
    remote_name=None
    page.get_by_role('button',name='Обновить данные',exact=True).click()
    expect(name).to_contain_text('Не задано')
    expect(name.locator('a')).to_have_count(0)
    assert not posts
    assert not errors,errors
    browser.close()
print('PASS: fresh Webdev Fibery metadata updates workspace on initial network read and metadata-only refresh, including link and explicit clear; manual flag/status stay unchanged')
