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
control = {"lock": 0, "hold": False, "pending": None, "fail": False}

requests = []
with sync_playwright() as p, httpx.Client(base_url=os.environ.get('PAGEPILOT_FRONTEND_URL', 'http://frontend'), timeout=30) as frontend:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def apply(payload):
        network.update(alternateMarkup=payload['alternate_markup'], enableAlternates=payload['enable_alternates'])
        for src,dst in [('canonical_default_markup','canonicalDefaultMarkup'),('canonical_fake_main_markup','canonicalFakeMainMarkup')]:
            if src in payload: network[dst]=payload[src]
        network['revision'] += 'x'
        network['operations'].insert(0,dict(id=payload['request_id'],action='alternates',status='confirmed',initiator='test',created_at='2026-11-18T15:00:00Z',message=None,domain=None))

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
            assert payload['action'] == 'alternates'
            posts.append(payload)
            if control['fail']:
                request.fulfill(status=422, content_type='application/json', body=json.dumps({'detail':'Test rejected'})); return
            if control['hold']:
                control['pending']=(request,payload); return
            apply(payload)
            data = network
        elif path.endswith('/network'):
            if control['lock']:
                control['lock'] -= 1
                request.fulfill(status=409, content_type='application/json', body=json.dumps({'detail':'Ожидает освобождения сетки. Продолжение выполняется автоматически.'})); return
            data = network
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
    editor=page.get_by_role('textbox',name='Альтернейты',exact=True)
    root=page.get_by_role('textbox',name='Каноникл всех страниц',exact=True)
    fake=page.get_by_role('textbox',name='Каноникл главной и фейковых внутренних страниц',exact=True)
    expect(editor).to_have_value(network['alternateMarkup'])
    def clean():
        expect(page.get_by_role('button',name='Сохранить разметку',exact=True)).to_have_count(0,timeout=15000)
        assert not page.locator('.networkSection .saveIndicator.error.visible').count()
    def link(path): return '<link rel="alternate" hreflang="pl" href="https://main.test/'+path+'" />'
    manual=link('manual/')+'\n'
    editor.fill(manual)
    network['alternateMarkup']=link('automatic/')
    network['canonicalFakeMainMarkup']='<link rel="canonical" href="https://main.test/automatic/" />'
    network['revision']+='remote'
    control['lock']=1
    editor.press('Enter')
    clean()
    assert len(posts)==1 and posts[-1]['alternate_markup']==manual
    expect(editor).to_have_value(manual)
    expect(fake).to_have_value(network['canonicalFakeMainMarkup'])
    # A clean field follows automation and does not cause a redundant save.
    automatic=link('next-path/')
    network['alternateMarkup']=automatic;network['revision']+='auto'
    page.get_by_role('button',name='Обновить данные',exact=True).click()
    expect(editor).to_have_value(automatic)
    clean();assert len(posts)==1
    # New typing while the first write is in flight must survive its response.
    first=link('first/');second=link('second/')
    editor.fill(first);control['hold']=True;editor.press('Enter')
    page.wait_for_timeout(150)
    assert control['pending'] is not None
    editor.fill(second);editor.press('Tab')
    control['hold']=False
    request,payload=control['pending'];control['pending']=None
    apply(payload);request.fulfill(content_type='application/json',body=json.dumps(network))
    clean();expect(editor).to_have_value(second)
    assert [p['alternate_markup'] for p in posts[-2:]]==[first,second]
    # Only one canonical field is changed; automatic fake canonical stays fresh.
    root_value='<link rel="canonical" href="https://manual.test/" />'
    root.fill(root_value)
    network['canonicalFakeMainMarkup']='<link rel="canonical" href="https://main.test/new-fake/" />';network['revision']+='auto'
    root.press('Enter');clean()
    expect(fake).to_have_value(network['canonicalFakeMainMarkup'])
    expect(root).to_have_value(root_value)
    before=len(posts);editor.press('Enter');page.wait_for_timeout(100);assert len(posts)==before
    # Whitespace edits save exactly, including blur (no semantic-equality shortcut).
    whitespace=second+'\n'
    editor.fill(whitespace);editor.press('Tab');clean()
    assert posts[-1]['alternate_markup']==whitespace
    # A rejected request retains text and clears the red error after a retry.
    control['fail']=True;editor.fill(link('retry/'));editor.press('Enter')
    expect(page.locator('.networkSection .saveIndicator.error.visible')).to_have_count(1)
    control['fail']=False;editor.press('Enter');clean()
    expect(editor).to_have_value(link('retry/'))
    assert not errors,errors
    browser.close()
print(json.dumps({'ok':True,'checks':['lock retry','manual priority','automatic clean refresh','typing during save','untouched canonical rebase','exact whitespace on blur','failed-save recovery'],'writes':len(posts)}))
