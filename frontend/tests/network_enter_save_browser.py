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
            alternates_before = dict(markup=network['alternateMarkup'], enabled=network['enableAlternates'])
            network.update(alternateMarkup=payload['alternate_markup'], enableAlternates=payload['enable_alternates'])
            if 'enable_canonical' in payload: network['enableCanonical'] = payload['enable_canonical']
            if 'enable_dynamic_routes' in payload: network['fake_main_enabled'] = payload['enable_dynamic_routes']
            for key, field in [('canonical_default_markup', 'canonicalDefaultMarkup'), ('canonical_fake_main_markup', 'canonicalFakeMainMarkup')]:
                if key in payload: network[field] = payload[key]
            network['revision'] += 'x'
            network['operations'].insert(0, dict(id=payload['request_id'], action=payload['action'], status='confirmed', domain=None,
                                                initiator='test', created_at='2026-10-19T06:00:00Z', message=None,
                                                alternates_before=alternates_before,
                                                alternates_after=dict(markup=network['alternateMarkup'],enabled=network['enableAlternates'])))
            data = network
        elif path.endswith('/network'): data = network
        elif path.endswith('/menu-capabilities'): data = dict(check_status='completed')
        elif path == '/auth/me': data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path in ('/sites', '/sites/cache/projects'): data = [site]
        elif path == '/sites/lookup': data = site
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        request.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('http://localhost/project-network/enter.test/')
    alternates = page.get_by_role('textbox', name='Альтернейты', exact=True)
    standard = page.get_by_role('textbox', name='Каноникл всех страниц', exact=True)
    fake = page.get_by_role('textbox', name='Каноникл главной и фейковых внутренних страниц', exact=True)
    alternates_status = page.get_by_role('status', name='Статус альтернейтов', exact=True)
    canonical_status = page.get_by_role('status', name='Статус каноникла', exact=True)
    expect(alternates).to_have_value(network['alternateMarkup'])
    expect(page.get_by_role('button', name='Добавить альтернейт', exact=True)).to_have_count(0)
    expect(alternates_status).to_have_text('Actual')
    expect(canonical_status).to_have_text('Actual')
    expect(page.get_by_role('button', name='Сохранить канониклы и альтернейты', exact=True)).to_have_count(0)
    alternates.press('Enter')
    assert not posts
    toggle = page.get_by_role('switch', name='Альтернейты', exact=True)
    expect(toggle).to_have_attribute('aria-checked', 'true')
    assert toggle.evaluate('(el)=>getComputedStyle(el).backgroundColor') == 'rgb(52, 199, 89)'
    heading = page.get_by_role('heading', name='Альтернейты', exact=True)
    assert abs(toggle.bounding_box()['y'] - heading.bounding_box()['y']) < 12
    toggle.click()
    expect(alternates_status).to_have_text('All Good')
    assert posts[-1]['enable_alternates'] is False and network['enableAlternates'] is False
    expect(toggle).to_have_attribute('aria-checked', 'false')
    toggle.press('Space')
    expect(alternates_status).to_have_text('All Good')
    assert posts[-1]['enable_alternates'] is True and network['enableAlternates'] is True
    expect(toggle).to_have_attribute('aria-checked', 'true')
    for label, parameter in [('Каноникл', 'enable_canonical'), ('Динамические страницы', 'enable_dynamic_routes')]:
        switch = page.get_by_role('switch', name=label, exact=True)
        expect(switch).to_have_attribute('aria-checked', 'true')
        assert switch.bounding_box()['width'] == 44
        assert switch.bounding_box()['height'] == 26
        switch.click()
        expect(switch).to_have_attribute('aria-checked', 'false')
        assert posts[-1][parameter] is False
        switch.press('Space')
        expect(switch).to_have_attribute('aria-checked', 'true')
        assert posts[-1][parameter] is True
    heading = page.get_by_role('heading', name='Сетка проекта', exact=True)
    view = page.get_by_role('group', name='Вид сетки', exact=True)
    assert abs(heading.bounding_box()['y'] + heading.bounding_box()['height']/2 - view.bounding_box()['y'] - view.bounding_box()['height']/2) < 3
    page.get_by_role('button', name='Ампы', exact=True).click()
    expect(alternates).to_have_count(0)
    page.get_by_role('button', name='Основная сетка', exact=True).click()
    expect(alternates).to_be_visible()
    for field, key, value in [
        (alternates, 'alternate_markup', '<link rel="alternate" hreflang="cs-CZ" href="https://main.test/cs/" />'),
        (standard, 'canonical_default_markup', '<link rel="canonical" href="https://{{settings.canon}}/" />'),
        (fake, 'canonical_fake_main_markup', '<link rel="canonical" href="https://{{settings.canon}}/cs/" />')]:
        status = alternates_status if key == 'alternate_markup' else canonical_status
        field.fill(value)
        expect(status).to_have_text('Upload')
        before = len(posts)
        field.press('Enter')
        expect(status).to_have_text('All Good')
        assert len(posts) == before + 1 and posts[-1][key] == value, posts
        expect(field).to_have_value(value)
        field.press('Enter')
        assert len(posts) == before + 1
    before = len(posts)
    alternates.press('End')
    alternates.press('Shift+Enter')
    assert len(posts) == before
    assert alternates.input_value().endswith('\n')
    alternates.press('Enter')
    expect(alternates).to_be_enabled()
    expect(alternates_status).to_have_text('All Good')
    assert len(posts) == before + 1 and posts[-1]['alternate_markup'].endswith('\n')
    # A failed save retains the draft and can be retried with Enter.
    fail = True
    standard.fill('<link rel="canonical" href="https://main.test/retry/" />')
    standard.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='Не удалось сохранить тестовую разметку')).to_be_visible()
    expect(standard).to_have_value('<link rel="canonical" href="https://main.test/retry/" />')
    expect(canonical_status).to_have_text('Upload')
    fail = False
    standard.press('Enter')
    expect(standard).to_be_enabled()
    expect(canonical_status).to_have_text('All Good')
    # The base button replaces even an unsaved draft and saves before/after history.
    before_markup = network['alternateMarkup']
    alternates.fill('<link rel="alternate" hreflang="de" href="https://old.test/" />')
    before = len(posts)
    page.get_by_role('button', name='Добавить Alternate', exact=True).click()
    expect(alternates_status).to_have_text('All Good')
    assert len(posts) == before + 1
    new_markup = posts[-1]['alternate_markup']
    assert new_markup.count('<link ') == 3 and 'old.test' not in new_markup
    assert 'href="https://{{settings.canon}}/" hreflang="cs"' in new_markup
    assert 'href="https://{{settings.canon}}/cs/" hreflang="cs-CZ"' in new_markup
    assert 'href="https://{{settings.canon}}/" hreflang="x-default"' in new_markup
    expect(alternates).to_have_value(new_markup)
    history = page.locator('.networkAlternatesHistory').first
    history.locator('summary').click()
    expect(history.locator('pre').nth(0)).to_have_text(before_markup.strip())
    expect(history.locator('pre').nth(1)).to_have_text(new_markup)
    # Server changes must block Enter as well as the base button.
    alternates.fill('<link rel="alternate" hreflang="de" href="https://main.test/de/" />')
    network['alternateMarkup'] = '<link rel="alternate" hreflang="pl" href="https://main.test/pl/" />'
    network['revision'] += 'remote'
    page.get_by_role('button', name='Обновить данные', exact=True).click()
    expect(page.get_by_text('Разметка в Webdev изменилась', exact=False)).to_be_visible()
    expect(page.get_by_role('button', name='Добавить Alternate', exact=True)).to_be_disabled()
    before = len(posts)
    alternates.press('Enter')
    expect(alternates_status).to_have_text('Upload')
    assert len(posts) == before
    assert not errors, errors
    browser.close()
print('PASS: Enter saves all three fields, Shift+Enter inserts newline, failed saves retain drafts, conflicts block writes')
