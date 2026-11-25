"""Run on Linux only: session outage/retry, timeout, expired token, optional cache."""
import json
import mimetypes
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

if sys.platform == 'darwin':
    raise SystemExit('Do not launch a browser on the user Mac. Run this check on Linux.')
from playwright.sync_api import sync_playwright, expect

DIST = Path(os.environ.get('PAGEPILOT_TEST_DIST', Path(__file__).resolve().parents[1] / 'dist'))
BASE = 'https://pagepilot-login.test'
USER = {'id':'editor','username':'editor','is_admin':True,'is_active':True,'allowed_site_ids':None}
SITE = dict(id='own',name='own.test',brand='Example',brand_source='manual',base_url='https://own.test',
            publication_endpoint='',payload_mode='simple_page',editor_version='2',
            default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='own.test',
            cache_geo='PL',cache_language='pl',cache_domains=[],project_status='working',is_test_project=False,
            has_menu=False,domains_count=1,internal_pages_count=0)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    errors = []
    def session(status=200, init='', width=1280):
        context = browser.new_context(viewport={'width':width,'height':900})
        state = {'status':status,'calls':[]}
        context.add_init_script('''
          localStorage.setItem('admin_token','test-token');
          sessionStorage.setItem('popup_permission_prompt_closed','true');
        ''' + init)
        def route(r):
            path = urlsplit(r.request.url).path
            if path.startswith('/api/'):
                state['calls'].append(path)
                data, code = [], 200
                if path == '/api/auth/me':
                    code = state['status']
                    data = USER if code == 200 else {'detail':'Сервис авторизации временно недоступен.'}
                elif path in ('/api/sites','/api/sites/cache/projects'): data = [SITE]
                elif path == '/api/me/favorite-sites': data = {'site_ids':[]}
                r.fulfill(status=code,content_type='application/json',body=json.dumps(data))
            else:
                file = DIST / path.lstrip('/')
                if not file.is_file(): file = DIST / 'index.html'
                r.fulfill(status=200,body=file.read_bytes(),content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/sites')
        return context, page, state

    context, page, state = session(503, width=375)
    expect(page.get_by_role('heading',name='Не удалось проверить сессию',exact=True)).to_be_visible()
    expect(page.get_by_role('alert')).to_contain_text('Повторяем проверку автоматически')
    assert page.locator('.loginLoadingBar').count() == 0
    assert state['calls'].count('/api/auth/me') == 1, state['calls']
    assert not any('/sites' in path for path in state['calls']), state['calls']
    assert page.evaluate('localStorage.getItem("admin_token")') == 'test-token'
    for button in page.locator('.loginRecoveryActions button').all():
        box = button.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 375, box
    state['status'] = 200
    expect(page.get_by_label('Бренд own.test',exact=True)).to_be_visible()
    assert state['calls'].count('/api/auth/me') == 2, state['calls']
    context.close()
    print('PASS: 503 preserves token and access checks; mobile session recovers automatically.', flush=True)

    context, page, state = session(503)
    expect(page.get_by_role('button',name='Войти заново',exact=True)).to_be_visible()
    page.get_by_role('button',name='Войти заново',exact=True).click()
    expect(page.get_by_role('button',name='Войти',exact=True)).to_be_visible()
    assert page.evaluate('localStorage.getItem("admin_token")') is None
    context.close()

    context, page, state = session(401)
    expect(page.get_by_role('button',name='Войти',exact=True)).to_be_visible()
    assert page.evaluate('localStorage.getItem("admin_token")') is None
    context.close()
    print('PASS: explicit re-login and expired-token logout clear the token.', flush=True)

    context, page, state = session(init='''
      const originalFetch = window.fetch.bind(window);
      window.__stallAuth = true;
      window.fetch = (input, options) => {
        if (String(input).endsWith('/auth/me') && window.__stallAuth) {
          window.__authStarted = true;
          return new Promise((resolve, reject) => {
            options.signal.addEventListener('abort', () => reject(options.signal.reason), {once:true});
          });
        }
        return originalFetch(input, options);
      };
    ''')
    page.wait_for_function('window.__authStarted === true')
    expect(page.get_by_role('alert')).to_contain_text('Повторяем проверку автоматически', timeout=30000)
    assert page.locator('.loginLoadingBar').count() == 0
    page.evaluate('window.__stallAuth = false')
    page.get_by_role('button',name='Повторить проверку',exact=True).click()
    expect(page.get_by_label('Бренд own.test',exact=True)).to_be_visible()
    context.close()
    print('PASS: hanging session request stops at deadline and can be retried.', flush=True)

    context, page, state = session(init='''
      Object.defineProperty(window.indexedDB, 'open', {value: () => ({})});
    ''')
    expect(page.get_by_label('Бренд own.test',exact=True)).to_be_visible(timeout=6000)
    assert '/api/sites' in state['calls'], state['calls']
    context.close()
    print('PASS: a stalled local cache does not block verified login or fresh project loading.', flush=True)
    assert not errors, errors
    browser.close()
