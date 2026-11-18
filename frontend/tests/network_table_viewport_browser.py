"""Remote browser only; built assets and mocked API, without project mutations."""
import base64
import json
import mimetypes
import os
from urllib.parse import urlparse
import httpx
from playwright.sync_api import sync_playwright, expect

site = dict(id='viewport', name='main.test', brand='Mostbet', base_url='https://main.test',
            publication_endpoint='', payload_mode='simple_page', editor_version='2',
            default_menu={'header': [], 'footer': []}, menu_library=[], default_banners=[],
            cache_canon='main.test', cache_geo='AZ', cache_language='az', cache_domains=[],
            project_status='working', is_test_project=False, has_menu=True, domains_count=70, internal_pages_count=0)
network = dict(canon='main.test', reserve='', domains=['main.test'] + [f'domain-{n}.test' for n in range(1, 70)],
               revision='one', main_history=['historical.test'], x_default_history=[], alternate_history=[],
               amp_domains=[f'amp-{n}.test' for n in range(35)],
               alternateMarkup='', enableAlternates=False, enableCanonical=False, has_head=True,
               alternates=[], operations=[])

with sync_playwright() as p, httpx.Client(base_url='http://frontend', timeout=30) as frontend:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def route(r):
        assert r.request.method == 'GET', 'Read-only test'
        path = urlparse(r.request.url).path
        if not path.startswith('/api/'):
            if 'ASSETS' in globals():
                body = base64.b64decode(ASSETS.get(path, ASSETS['/index.html']))
            else:
                response = frontend.get(path)
                assert response.status_code == 200
                body = response.content
            mime = mimetypes.guess_type(path if '.' in path.rsplit('/', 1)[-1] else 'index.html')[0]
            r.fulfill(content_type=mime or 'application/octet-stream', body=body)
            return
        path = path[4:]
        data = []
        if path.endswith('/network'): data = network
        elif path.endswith(('/network/indexing', '/network/sitemap')): data = None
        elif path.endswith(('/network/fake-main-queue', '/network/edit-queue')): data = dict(items=[], limit=30, active_count=0, network=None)
        elif path.endswith(('/showcase/history', '/notifications')): data = dict(items=[])
        elif path.endswith('/structured-data'): data = dict(enabled=False, markup='', source='webdev')
        elif path.endswith('/menu-capabilities'): data = dict(check_status='completed')
        elif path == '/auth/me': data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path in ('/sites', '/sites/cache/projects'): data = [site]
        elif path == '/sites/lookup': data = site
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        r.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('http://localhost/project-network/main.test/')
    rows = page.locator('.networkTable tbody tr')
    viewport = page.get_by_role('region', name='Домены сетки', exact=True)
    expect(rows).to_have_count(70)
    assert page.locator('.networkDomainNumber').all_text_contents() == [str(n) for n in range(1, 71)]
    expect(page.locator('.networkDomainTotal')).to_have_text('Доменов: 70')

    def cap_at_thirty():
        values = viewport.evaluate('''e => {
          const rows=e.querySelectorAll('tbody tr'), top=e.getBoundingClientRect().top;
          return {height:e.clientHeight, bottom30:rows[29].getBoundingClientRect().bottom-top+e.scrollTop,
            bottom31:rows[30].getBoundingClientRect().bottom-top+e.scrollTop, scroll:e.scrollHeight};
        }''')
        assert abs(values['height'] - values['bottom30']) <= 2, values
        assert values['bottom31'] > values['height'] and values['scroll'] > values['height'], values

    cap_at_thirty()
    viewport.evaluate('e => e.scrollTop = e.scrollHeight')
    assert viewport.evaluate('e => Math.abs(e.querySelector("thead").getBoundingClientRect().top-e.getBoundingClientRect().top)<2')
    assert viewport.evaluate('e => e.querySelector("tbody tr:last-child").getBoundingClientRect().bottom <= e.getBoundingClientRect().top+e.clientHeight+1')
    search = page.get_by_label('Поиск по доменам сетки', exact=True)
    search.fill('domain-69.test')
    expect(rows).to_have_count(1)
    assert page.locator('.networkDomainNumber').all_text_contents() == ['1']
    expect(page.locator('.networkDomainTotal')).to_have_text('Доменов: 1')
    assert viewport.evaluate('e => !e.style.maxHeight && e.scrollTop === 0')
    search.fill('')
    expect(rows).to_have_count(70)
    cap_at_thirty()
    page.get_by_label('Показать историю', exact=True).check()
    expect(rows).to_have_count(71)
    cap_at_thirty()
    page.get_by_role('button', name='Ампы', exact=True).click()
    expect(rows).to_have_count(35)
    cap_at_thirty()
    page.get_by_role('button', name='Основная сетка', exact=True).click()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(200)
    cap_at_thirty()
    assert viewport.evaluate('e => e.scrollWidth > e.clientWidth')
    assert viewport.evaluate('e => e.getBoundingClientRect().right <= innerWidth')
    page.get_by_label('Показать историю', exact=True).uncheck()
    network['domains'] = ['main.test'] + [f'domain-{n}.test' for n in range(1, 30)]
    page.reload()
    expect(rows).to_have_count(30)
    assert viewport.evaluate('e => !e.style.maxHeight && e.scrollHeight <= e.clientHeight+1')
    assert not errors, errors
    browser.close()
print(json.dumps({'passed': True, 'checks': ['30-row cap', 'sticky header', 'last row reachable',
    'numbering and count', 'filter resets scroll', 'history', 'AMP', 'mobile', 'uncapped 30-row table']}))
