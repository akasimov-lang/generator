"""Manual competitor upload flow; all API requests are intercepted."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

state = {'drafts': [], 'created': None, 'next_id': 0}
base = os.environ.get('VITE_TEST_URL', 'http://127.0.0.1:5182')
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1050})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","test"); sessionStorage.setItem("popup_permission_prompt_closed","true")')
    def route(route):
        path = route.request.url.split('/api')[-1].split('?')[0]
        method = route.request.method
        data = []
        if path == '/auth/me': data = {'id': 'test', 'username': 'tester', 'is_admin': True, 'is_active': True, 'allowed_site_ids': None}
        elif path == '/ai-providers': data = [{'id': 'gemini', 'name': 'Gemini', 'provider_type': 'gemini', 'is_active': True}]
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        elif path.startswith('/site-templates/source-drafts'):
            if method == 'GET': data = state['drafts']
            elif method == 'DELETE':
                state['drafts'] = [row for row in state['drafts'] if row['id'] != path.rsplit('/', 1)[-1]]
                data = {'deleted': True}
            else:
                payload = route.request.post_data_json
                if method == 'POST':
                    state['next_id'] += 1
                    source_id = f"draft-{state['next_id']}"
                else: source_id = path.rsplit('/', 1)[-1]
                data = {**payload, 'id': source_id, 'revision': payload['revision'] + 1,
                        'suggested_brand': 'Mostbet' if 'Mostbet' in payload['html'] else 'Онлайн казино', 'capture': {'status': 'google_ready'}}
                if method == 'POST': state['drafts'].append(data)
                else: state['drafts'] = [data if row['id'] == source_id else row for row in state['drafts']]
        elif path == '/site-templates' and method == 'POST':
            state['created'] = route.request.post_data_json
            data = {'id': 'created', **state['created'], 'status': 'awaiting_sources', 'revision': 1, 'request': {'uniqueness_scope': 'brand_geo'}}
        route.fulfill(content_type='application/json', body=json.dumps(data))
    page.route('**/api/**', route)
    page.goto(base + '/template-generator')
    page.get_by_role('button', name='Загрузить HTML конкурентов', exact=True).click()
    expect(page.get_by_role('heading', name='Шаблон из HTML конкурентов', exact=True)).to_be_visible()
    expect(page.get_by_label('Искать конкурентов в Google')).to_have_count(0)
    brand = page.get_by_role('combobox', name='Бренд', exact=True)
    expect(brand).to_have_value('Онлайн казино — общие ключи')
    geo = page.get_by_role('combobox', name='ГЕО', exact=True)
    language = page.get_by_role('combobox', name='Язык', exact=True)
    geo.fill('Герм'); geo.press('Enter')
    expect(geo).to_have_value('🇩🇪 DE — Германия')
    expect(language).to_have_value('Deutsch (DE)')
    geo.click(); assert page.get_by_role('option').count() > 200
    geo.fill('zzzzzz'); expect(page.get_by_text('Ничего не найдено. Попробуйте название или код.')).to_be_visible()
    geo.press('Escape'); expect(geo).to_have_value('🇩🇪 DE — Германия')
    language.fill('English'); language.press('Enter'); expect(language).to_have_value('English (EN)')
    language.click(); assert page.get_by_role('option').count() > 50
    language.fill('missing language'); language.press('Escape'); expect(language).to_have_value('English (EN)')
    html = '<html><title>Mostbet</title><body>' + 'Competitor content. ' * 30 + '</body></html>'
    upload = page.get_by_label('Загрузить HTML конкурента 1', exact=True)
    upload.set_input_files({'name': 'homepage.html', 'mimeType': 'text/html', 'buffer': html.encode()})
    expect(page.locator('.tg-source-field [role=status]').first).to_have_text('Сохранено')
    expect(brand).to_have_value('Mostbet')
    expect(page.get_by_role('textbox', name='HTML конкурента 1', exact=True)).to_have_value(html)
    brand.fill('Мой бренд'); brand.press('Tab')
    page.get_by_role('textbox', name='HTML конкурента 1', exact=True).fill(html + 'Updated')
    expect(page.locator('.tg-source-field [role=status]').first).to_have_text('Сохранено')
    expect(brand).to_have_value('Мой бренд')
    upload.set_input_files({'name': 'empty.html', 'mimeType': 'text/html', 'buffer': b''})
    expect(page.get_by_text('Файл пуст. Выберите HTML главной страницы.')).to_be_visible()
    expect(page.get_by_role('textbox', name='HTML конкурента 1', exact=True)).to_have_value(html + 'Updated')
    upload.set_input_files({'name': 'large.html', 'mimeType': 'text/html', 'buffer': b'x' * 2_000_001})
    expect(page.get_by_text('HTML превышает 2 МБ. Выберите файл меньшего размера.')).to_be_visible()
    for number in range(2, 6):
        page.get_by_role('button', name='Добавить конкурента', exact=True).click()
        page.get_by_role('textbox', name=f'HTML конкурента {number}', exact=True).fill(html)
        expect(page.locator('.tg-source-field [role=status]').nth(number - 1)).to_have_text('Сохранено')
    expect(page.get_by_role('button', name='Добавить конкурента', exact=True)).to_be_disabled()
    page.get_by_role('button', name='Удалить конкурента 3', exact=True).click()
    expect(page.locator('.tg-source-field')).to_have_count(4)
    assert len(state['drafts']) == 4
    expect(page.get_by_role('button', name='Добавить конкурента', exact=True)).to_be_enabled()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='/tmp/pagepilot-template-upload-mobile.png', full_page=True)
    page.set_viewport_size({'width': 1440, 'height': 1050})
    page.screenshot(path='/tmp/pagepilot-template-upload-desktop.png', full_page=True)
    page.get_by_role('button', name='Сохранить конкурентов', exact=True).click()
    expect(page.get_by_role('heading', name='Мой бренд / DE')).to_be_visible()
    assert state['created']['brand'] == 'Мой бренд'
    assert state['created']['language'] == 'en' and state['created']['geo'] == 'DE'
    assert state['created']['collect_competitors'] is False
    assert len(state['created']['source_drafts']) == 4
    assert not errors, errors
    browser.close()
print('PASS: file upload, paste, GEO/language, brand override, five-source limit, deletion, responsive layout, creation')
