"""Server-only smoke check: deployed icons and read-only Webdev showcase data."""
import json
import sys
from urllib.parse import urlparse

import httpx
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import select

assert sys.platform != 'darwin', 'Run on the server only.'
from app import models, showcase_editor
from app.db import SessionLocal
from app.project_network import Remote

catalog = httpx.get('http://frontend/brand-icons/catalog.json').json()['brands']
with SessionLocal() as db:
    actual = db.scalar(select(models.Site).where(models.Site.name == 'top-polskie-kasyno.pl'))
    with Remote(db, actual) as remote:
        remote.client.headers['Accept'] = 'application/json;v=2'
        showcase = showcase_editor.view(remote.project())
assert len(showcase['rows']) == 15
assert all(row.get('logo') and any(f['key'] == 'rating' for f in row['fields']) for row in showcase['rows'])

site = dict(id='preview', name='top-polskie-kasyno.pl', brand='Общие ключи', site_type='general',
    external_project_id='project', base_url='https://ionickiss.pl', publication_endpoint='',
    payload_mode='simple_page', editor_version='2', default_menu={'header': [], 'footer': []},
    menu_library=[], default_banners=[], cache_canon='ionickiss.pl', cache_geo='pl-PL',
    cache_language='pl', homepage_title='Home', internal_pages_count=1, domains_count=2,
    cache_domains=['ionickiss.pl'], main_domain_history=[], x_default_history=[],
    alternate_domain_history=[], cache_server_host='test.example', project_status='mass_actions',
    is_test_project=False, has_menu=False, cache_synced_at='2026-11-10T12:00:00Z')
sites = [site, *[dict(site, id=str(i), name=f'catalog-{i}.example', brand=brand, site_type='monobrand')
                 for i, brand in enumerate(catalog)]]
home = {'key': 'home', 'title': 'Home', 'slug': '/', 'is_home': True, 'revision': 'a' * 64,
        'content': {'version': '2.28', 'blocks': []}}
errors, writes = [], []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def route(request):
        parsed = urlparse(request.request.url)
        if parsed.hostname != 'ai-seo-content-panel.site':
            request.continue_()
            return
        if not parsed.path.startswith('/api/'):
            request.fulfill(response=request.fetch(url='http://frontend' + parsed.path + ('?' + parsed.query if parsed.query else '')))
            return
        path = parsed.path[4:]
        if request.request.method != 'GET':
            writes.append(path)
        data = []
        if path == '/auth/me':
            data = {'id': 'anton', 'username': 'anton', 'is_admin': True, 'is_active': True, 'allowed_site_ids': None}
        elif path in ['/sites', '/sites/cache/projects']:
            data = sites
        elif path == '/sites/lookup':
            data = site
        elif 'favorite-sites' in path:
            data = {'site_ids': []}
        elif path.endswith('/overview'):
            data = {'site': site, 'stats': {}, 'recent_content': []}
        elif path.endswith('/menu-capabilities'):
            data = {'check_status': 'completed'}
        elif path.endswith('/pages'):
            data = {'pages': [home], 'total': 1}
        elif path.endswith('/showcase'):
            data = showcase
        request.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('https://ai-seo-content-panel.site/project-content/top-polskie-kasyno.pl/')
    brand_button = page.get_by_role('button', name='Бренд текущего проекта', exact=True)
    brand_button.click()
    options = page.get_by_role('listbox').get_by_role('option')
    expect(options).to_have_count(len(catalog) + 1)
    boxes = []
    for brand in catalog:
        option = page.get_by_role('option', name=brand, exact=True)
        option.scroll_into_view_if_needed()
        logo = option.locator('img')
        expect(logo).to_have_count(1)
        expect(logo).to_have_js_property('complete', True)
        assert logo.evaluate('(e) => e.naturalWidth > 0'), brand
        box = option.locator('.brandCatalogIcon').bounding_box()
        boxes.append((box['width'], box['height']))
    assert set(boxes) == {(34, 28)}, set(boxes)
    search = page.get_by_placeholder('Найти бренд', exact=True)
    search.fill('Joe Fortune')
    expect(options).to_have_count(1)
    search.press('Escape')
    expect(brand_button).to_contain_text('Общие ключи')
    for width in [1440, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        brand_button.click()
        search.fill('Hugo')
        expect(options).to_have_count(1)
        expect(options.locator('img')).to_have_js_property('complete', True)
        assert options.locator('.brandCatalogIcon').bounding_box()['width'] == 34
        search.press('Escape')
    page.set_viewport_size({'width': 1440, 'height': 1000})
    expect(page.locator('.showcaseTable tbody tr')).to_have_count(15)
    logos = page.locator('.showcaseLogo')
    expect(logos).to_have_count(15)
    for logo in logos.all():
        logo.scroll_into_view_if_needed()
        expect(logo).to_have_js_property('complete', True)
        assert logo.evaluate('(e) => e.naturalWidth > 0'), logo.get_attribute('src')
    for brand in ['Dieselwin', "Hit'n'spin"]:
        row = next(row for row in showcase['rows'] if row['brand'] == brand)
        rating = next(field['value'] for field in row['fields'] if field['key'] == 'rating')
        page.get_by_role('button', name='Редактировать ' + brand, exact=True).click()
        expect(page.get_by_role('textbox', name='Рейтинг — ' + brand, exact=True)).to_have_value(rating)
        page.locator('.showcaseTable').get_by_role('button', name='Отмена', exact=True).click()
    assert not errors and not writes, (errors, writes)
    browser.close()
print(json.dumps({'status': 'passed', 'catalog_logos': len(catalog), 'uniform_box': [34, 28],
    'showcase_logos': len(showcase['rows']), 'rating_fields': len(showcase['rows']),
    'checks': ['desktop', 'mobile', 'image loading', 'search', 'Escape', 'editable ratings'],
    'writes': writes, 'errors': errors}, ensure_ascii=False))
