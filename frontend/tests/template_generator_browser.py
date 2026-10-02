"""End-to-end UI behavior with deterministic API responses and no paid generation."""
import base64
import copy
import json
import os
from pathlib import Path
import runpy
from playwright.sync_api import sync_playwright, expect

fixture = runpy.run_path('backend/tests/test_site_templates.py')
from app.site_templates import render
r = fixture['row']()
detail = {'id': 'template', 'brand': 'Brand', 'geo': 'PL', 'language': 'pl', 'status': 'ready', 'phase': 'Готово',
          'error': None, 'revision': 1, 'created_at': '2026-10-02T10:00:00Z', 'updated_at': '2026-10-02T10:00:00Z',
          'request': {'uniqueness_scope': 'brand_geo'}, 'document': r.document, 'html': render(r, r.document)}
state = {'items': [], 'created': None, 'saved': None}
base = os.environ.get('VITE_TEST_URL', 'http://127.0.0.1:5178')
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1050})
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script('if(window === window.top){localStorage.setItem("admin_token","test");sessionStorage.setItem("popup_permission_prompt_closed","true")}')
    def route(route):
        path = route.request.url.split('/api')[-1].split('?')[0]; method = route.request.method
        data = []; status = 200
        if path == '/auth/me': data = {'id': 'test', 'username': 'anton', 'is_admin': True, 'is_active': True, 'allowed_site_ids': None}
        elif path == '/ai-providers': data = [{'id': 'gemini', 'name': 'Gemini', 'provider_type': 'gemini', 'is_active': True}]
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        elif path == '/site-templates' and method == 'POST':
            state['created'] = route.request.post_data_json
            state['items'] = [detail]; data = detail; status = 202
        elif path == '/site-templates': data = state['items']
        elif path == '/site-templates/template' and method == 'PUT':
            state['saved'] = route.request.post_data_json
            detail['revision'] += 1; detail['document']['menu'] = state['saved']['menu']
            data = detail; status = 202
        elif path == '/site-templates/template': data = detail
        elif '/download/' in path: data = {'filename': 'index.html', 'mime': 'text/html', 'base64': base64.b64encode(detail['html'].encode()).decode()}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))
    page.route('**/api/**', route)
    page.goto(base+'/template-generator')
    expect(page.get_by_role('heading', name='Новый шаблон', exact=True)).to_be_visible()
    page.get_by_role('button', name='Новый шаблон', exact=True).click()
    expect(page.get_by_label('Искать конкурентов в Google')).to_be_checked()
    expect(page.get_by_role('combobox', name='ГЕО', exact=True)).to_have_value('')
    expect(page.get_by_role('combobox', name='Язык', exact=True)).to_have_value('')
    brand = page.get_by_role('combobox', name='Бренд', exact=True)
    brand.fill('Mostbet')
    brand.press('Enter')
    expect(brand).to_have_value('Mostbet')
    brand.fill('Custom Brand')
    brand.press('Tab')
    expect(brand).to_have_value('Custom Brand')
    expect(page.get_by_role('button', name='Сгенерировать шаблон', exact=True)).to_be_disabled()
    geo = page.get_by_role('combobox', name='ГЕО', exact=True)
    geo.click()
    assert page.locator('.tg-combobox-list [role=option]').count() > 200
    geo.fill('Герм')
    expect(page.locator('.tg-combobox-list [role=option]')).to_have_count(1)
    expect(page.locator('.tg-combobox-list [role=option]')).to_contain_text('🇩🇪')
    geo.press('Enter')
    expect(geo).to_have_value('🇩🇪 DE — Германия')
    language = page.get_by_role('combobox', name='Язык', exact=True)
    expect(language).to_have_value('Deutsch (DE)')
    geo.fill('Нидерланды')
    geo.press('Enter')
    expect(language).to_have_value('Nederlands (NL)')
    geo.fill('Германия')
    geo.press('Enter')
    language.fill('польский')
    expect(page.locator('.tg-combobox-list [role=option]')).to_have_count(1)
    language.press('Enter')
    expect(language).to_have_value('Polski (PL)')
    geo.click()
    assert page.locator('.tg-combobox-list [role=option]').count() > 200
    geo.fill('unknown-country-xyz')
    expect(page.get_by_text('Ничего не найдено. Попробуйте название или код.')).to_be_visible()
    geo.press('Escape')
    expect(geo).to_have_value('🇩🇪 DE — Германия')
    page.get_by_label('Ключевые запросы', exact=False).fill('brand review, brand bonus')
    page.get_by_placeholder('example.com, https://example.org/review/').fill('example.com, example.org example.net')
    page.get_by_placeholder('https://brand.com').fill('https://brand.example')
    page.get_by_label('Все шаблоны', exact=False).check()
    page.screenshot(path='/private/tmp/template-ui-create-desktop.png', full_page=True)
    page.get_by_role('button', name='Сгенерировать шаблон', exact=True).click()
    expect(page.get_by_role('tab', name='Предпросмотр')).to_be_visible()
    assert state['created']['uniqueness_scope'] == 'global'
    assert state['created']['collect_competitors'] is True
    assert state['created']['brand'] == 'Custom Brand'
    assert state['created']['brand_url'] == 'https://brand.example'
    assert state['created']['language'] == 'pl'
    assert state['created']['keywords'] == 'brand review, brand bonus'
    assert state['created']['competitors'] == 'example.com, example.org example.net'
    expect(page.locator('iframe')).to_have_attribute('sandbox', '')
    page.get_by_role('button', name='Телефон', exact=True).click()
    assert page.locator('iframe').bounding_box()['width'] == 390
    page.get_by_role('tab', name='Меню', exact=True).click()
    page.get_by_label('Назначение').first.select_option('real')
    page.get_by_placeholder('/page/ или https://…').fill('/bonus/')
    page.get_by_role('button', name='Сохранить и проверить').click()
    expect(page.get_by_role('tab', name='Предпросмотр')).to_be_visible()
    assert state['saved']['menu'][0]['mode'] == 'real' and state['saved']['menu'][0]['url'] == '/bonus/'
    with page.expect_download() as downloaded:
        page.get_by_role('button', name='HTML', exact=True).click()
    assert downloaded.value.suggested_filename == 'index.html'
    page.screenshot(path='/private/tmp/template-ui-preview-desktop.png', full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path='/private/tmp/template-ui-preview-mobile.png', full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert not errors, errors
    browser.close()
    print('PASS: create, GEO/language, scope, competitors, sandbox preview, menu edit, download, mobile overflow')
