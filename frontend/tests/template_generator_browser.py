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
state = {'items': [], 'created': None, 'saved': None, 'sources': [], 'drafts': []}
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
        elif path.startswith('/site-templates/source-drafts'):
            if method == 'GET': data=state['drafts']
            else:
                draft=route.request.post_data_json
                index=int(path.rsplit('/',1)[-1].removeprefix('draft-')) if method=='PUT' else len(state['drafts'])
                data={**draft,'id':f'draft-{index}','revision':draft['revision']+1,'capture':{'status':'google_ready'}}
                if method=='PUT':state['drafts'][index]=data
                else:state['drafts'].append(data)
        elif path == '/site-templates': data = state['items']
        elif path == '/site-templates/template' and method == 'PUT':
            state['saved'] = route.request.post_data_json
            detail['revision'] += 1; detail['document']['menu'] = state['saved']['menu']
            data = detail; status = 202
        elif path.startswith('/site-templates/template/sources'):
            if method == 'GET': data = state['sources']
            else:
                draft = route.request.post_data_json
                index = int(path.rsplit('/',1)[-1].removeprefix('source-')) if method == 'PUT' else len(state['sources'])
                data = {**draft, 'id': f'source-{index}', 'revision': draft['revision']+1, 'capture': {'status':'google_ready'}}
                if method == 'PUT': state['sources'][index]=data
                else: state['sources'].append(data)
        elif path == '/site-templates/template': data = detail
        elif '/download/' in path: data = {'filename': 'index.html', 'mime': 'text/html', 'base64': base64.b64encode(detail['html'].encode()).decode()}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))
    page.route('**/api/**', route)
    page.goto(base+'/template-generator')
    expect(page.get_by_role('heading', name='Новый шаблон', exact=True)).to_be_visible()
    page.get_by_role('button', name='Новый шаблон', exact=True).click()
    expect(page.get_by_label('Искать конкурентов в Google')).to_be_checked()
    # Drafts persist before creating a task, with one independent field per competitor.
    draft_html='<html><body>'+('Research source. '*30)+'</body></html>'
    page.get_by_role('textbox',name='HTML конкурента 1',exact=True).fill(draft_html)
    expect(page.locator('.tg-source-field [role=status]').first).to_have_text('Сохранено')
    expect(page.get_by_label('Искать конкурентов в Google')).to_be_checked()
    page.get_by_role('button',name='Добавить конкурента',exact=True).click()
    page.get_by_role('textbox',name='HTML конкурента 2',exact=True).fill(draft_html+'second')
    expect(page.locator('.tg-source-field [role=status]').nth(1)).to_have_text('Сохранено')
    assert len(state['drafts'])==2
    page.reload()
    page.get_by_role('button',name='Новый шаблон',exact=True).click()
    expect(page.get_by_role('textbox',name='HTML конкурента 1',exact=True)).to_have_value(draft_html)
    expect(page.get_by_role('textbox',name='HTML конкурента 2',exact=True)).to_have_value(draft_html+'second')
    page.get_by_role('textbox',name='HTML конкурента 1',exact=True).fill(draft_html+'updated')
    expect(page.locator('.tg-source-field [role=status]').first).to_have_text('Сохранено')
    assert state['drafts'][0]['revision']==2
    page.get_by_label('Искать конкурентов в Google').check()
    expect(page.get_by_role('combobox', name='ГЕО', exact=True)).to_have_value('')
    expect(page.get_by_role('combobox', name='Язык', exact=True)).to_have_value('')
    brand = page.get_by_role('combobox', name='Бренд', exact=True)
    brand.fill('Mostbet')
    brand.press('Enter')
    expect(brand).to_have_value('Mostbet')
    brand.fill('Custom Brand')
    brand.press('Tab')
    expect(brand).to_have_value('Custom Brand')
    expect(page.get_by_role('button', name='Этап 1 — собрать конкурентов', exact=True)).to_be_disabled()
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
    page.get_by_role('button', name='Этап 1 — собрать конкурентов', exact=True).click()
    expect(page.get_by_role('tab', name='Предпросмотр')).to_be_visible()
    assert state['created']['source_drafts']==[{'id':'draft-0','revision':2},{'id':'draft-1','revision':1}]
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
    # Autosave every edit, independent competitor fields, and the extension bridge.
    html='<html><body><p>'+('Competitor content. '*30)+'</p></body></html>'
    field=page.get_by_role('textbox',name='HTML конкурента 1',exact=True)
    field.fill(html)
    page.wait_for_function("document.querySelector('.tg-source-field [role=status]').textContent === 'Сохранено'")
    assert state['sources'][0]['html']==html
    field.fill(html.replace('Competitor','Updated'))
    page.wait_for_function("document.querySelector('.tg-source-field [role=status]').textContent === 'Сохранено'")
    assert state['sources'][0]['revision']==2 and 'Updated' in state['sources'][0]['html']
    page.get_by_role('button',name='Добавить конкурента').click()
    page.get_by_role('textbox',name='HTML конкурента 2',exact=True).fill('Second draft')
    page.wait_for_function("document.querySelectorAll('.tg-source-field [role=status]')[1].textContent === 'Сохранено'")
    assert len(state['sources'])==2
    page.evaluate("window.chrome = {runtime:{id:'test-extension',sendMessage:async m=>{window.extensionStart=m;return {started:true}},onMessage:{addListener:fn=>window.extensionReceive=fn}}}")
    page.add_script_tag(path='extensions/pagepilot-chrome/pagepilot.js')
    page.get_by_text('Адрес и получение HTML через Google', exact=True).first.click()
    page.get_by_text('Действия с HTML', exact=True).first.click()
    page.get_by_role('textbox',name='Адрес конкурента 1',exact=True).fill('https://example.com')
    page.get_by_role('button',name='Получить через Chrome',exact=True).first.click()
    page.wait_for_function('window.extensionStart?.sourceId === "source-0"')
    result=page.evaluate("""html=>new Promise(resolve=>window.extensionReceive({type:'SAVE_HTML',templateId:'template',sourceId:'source-0',html},{id:'test-extension'},resolve))""", html)
    assert result=={'saved':True}
    expect(field).to_have_value(html)
    assert not errors, errors
    browser.close()
    print('PASS: create, GEO/language, scope, competitors, sandbox preview, menu edit, download, mobile overflow')
