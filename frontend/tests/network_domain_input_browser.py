"""Run in the remote browser environment only; all API writes are mocked."""
import base64
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx
from playwright.sync_api import sync_playwright, expect

DIST = Path(os.environ.get('PAGEPILOT_DIST', 'frontend/dist'))
site = dict(id='domain-input', name='domain-input.test', brand='Pelican', base_url='https://main.test',
            publication_endpoint='', payload_mode='simple_page', editor_version='2',
            default_menu={'header': [], 'footer': []}, menu_library=[], default_banners=[],
            cache_canon='main.test', cache_geo='CZ', cache_language='cs', cache_domains=[],
            project_status='working', is_test_project=False, has_menu=True, domains_count=2, internal_pages_count=0)
network = dict(canon='main.test', reserve='reserve.test', domains=['main.test', 'reserve.test'],
               revision='one', main_history=[], x_default_history=[], alternate_history=[],
               alternateMarkup='<link rel="alternate" hreflang="cs" href="https://main.test/" />',
               enableAlternates=True, enableCanonical=True, has_head=True,
               canonicalDefaultMarkup='<link rel="canonical" href="https://main.test/" />',
               canonicalFakeMainMarkup='', fake_main_enabled=True, fake_main_paths=['/cs/'],
               fake_main_current='/cs/', alternates=[], operations=[])
posts = []
requests = []
with sync_playwright() as p, httpx.Client(base_url=os.environ.get('PAGEPILOT_FRONTEND_URL', 'http://frontend'), timeout=30) as frontend:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def route(request):
        path = urlparse(request.request.url).path
        if not path.startswith('/api/'):
            if 'ASSETS' in globals():
                body = base64.b64decode(ASSETS.get(path, ASSETS['/index.html']))
            elif os.environ.get('PAGEPILOT_FRONTEND_URL'):
                response = frontend.get(path)
                assert response.status_code == 200
                body = response.content
            else:
                asset = DIST / path.lstrip('/')
                if not asset.is_file(): asset = DIST / 'index.html'
                body = asset.read_bytes()
            request.fulfill(content_type=mimetypes.guess_type(path if '.' in path.rsplit('/', 1)[-1] else 'index.html')[0] or 'application/octet-stream', body=body)
            return
        path = path[4:]
        requests.append(path)
        data = []
        if path.endswith('/network/operations') and request.request.method == 'POST':
            payload = request.request.post_data_json
            assert payload['action'] == 'create_domains'
            posts.append(payload)
            network['domains'].extend(payload['domains'])
            network['revision'] += 'x'
            network['operations'].insert(0, dict(id=payload['request_id'], action='create_domains', status='confirmed', domain=None, domains=payload['domains'], initiator='test', created_at='2026-11-18T12:00:00Z', message=None))
            data = network
        elif path.endswith('/network'): data = network
        elif path.endswith(('/network/indexing', '/network/sitemap')): data = None
        elif path.endswith(('/network/fake-main-queue', '/network/edit-queue')): data = dict(items=[], limit=30, active_count=0, network=None)
        elif path.endswith(('/showcase/history', '/notifications')): data = dict(items=[])
        elif path.endswith('/structured-data'): data = dict(enabled=False, markup='', source='webdev')
        elif path.endswith('/menu-capabilities'): data = dict(check_status='completed')
        elif path == '/auth/me': data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path in ('/sites', '/sites/cache/projects'): data = [site]
        elif path == '/sites/lookup': data = site
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        request.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('http://localhost/project-network/domain-input.test/')
    field = page.get_by_label('Домены и поддомены', exact=True)
    button = page.get_by_role('button', name='Добавить в сетку', exact=True)
    section = page.locator('.networkSubdomains')
    try:
        expect(field).to_be_visible(timeout=15000)
    except AssertionError:
        raise AssertionError(json.dumps({'body':page.locator('body').inner_text()[:4000], 'errors':errors, 'requests':requests}, ensure_ascii=False)) from None

    def paste(text):
        field.evaluate('''(field, text) => {
            const clipboardData = new DataTransfer();
            clipboardData.setData('text/plain', text);
            field.dispatchEvent(new ClipboardEvent('paste', {clipboardData, bubbles:true, cancelable:true}));
        }''', text)

    field.focus()
    paste(r'https\://bogtrykmuseet.dk/')
    expect(field).to_have_value('bogtrykmuseet.dk')
    expect(button).to_be_enabled()
    expect(section.locator('ul li')).to_have_text(['bogtrykmuseet.dk'])

    field.fill('')
    paste('https://one.dk/, https://two.dk///;\nhttp://ONE.dk\t//three.dk/')
    expect(field).to_have_value('one.dk\ntwo.dk\nthree.dk')
    expect(section.locator('ul li')).to_have_text(['one.dk', 'two.dk', 'three.dk'])
    field.evaluate('(e)=>e.setSelectionRange(7,13)')
    paste('https://replacement.dk/')
    expect(field).to_have_value('one.dk\nreplacement.dk\nthree.dk')

    field.fill('https://main.test/')
    expect(section.get_by_role('alert')).to_contain_text('main.test: уже есть в сетке')
    expect(button).to_be_disabled()
    field.fill('https://one.dk/page/')
    expect(button).to_be_disabled()
    expect(section.get_by_role('alert')).to_contain_text('некорректное имя')

    field.fill(' '.join(f'https://domain{i}.test/' for i in range(101)))
    expect(button).to_be_disabled()
    expect(section).to_contain_text('За один запуск можно создать до 100 доменов.')

    field.fill('https://bogtrykmuseet.dk/, http://second.dk///')
    field.press('Tab')
    expect(field).to_have_value('bogtrykmuseet.dk\nsecond.dk')
    expect(button).to_be_enabled()
    button.click()
    expect(field).to_have_value('')
    assert len(posts) == 1 and posts[0]['domains'] == ['bogtrykmuseet.dk', 'second.dk'], posts
    assert not errors, errors
    browser.close()
print(json.dumps({'ok': True, 'paste': True, 'selection': True, 'multiline': True, 'blur': True,
                  'duplicates': True, 'invalid_path_blocked': True, 'limit_100': True,
                  'submitted_domains': posts[0]['domains'], 'writes_mocked': True, 'browser_errors': errors}))
