"""Enter saves markup through the network API; Shift+Enter keeps multiline editing."""
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs
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
peers = [site, dict(site, id='peer', name='peer.test', cache_canon='peer-main.test', domains_count=7),
         dict(site, id='pl', name='polish.test', cache_geo='PL'),
         dict(site, id='other', name='other.test', brand='Other'),
         dict(site, id='removed', name='removed-project.test', is_active=False)]
peer_network = dict(network, canon='peer-main.test', reserve='', domains=['peer-main.test', 'peer-free.test'])
posts = []
fail = False
network.update(added_to_system_at='2026-10-18T09:00:00+00:00', main_history=['old.test'],
               amp_domains=['mobile.test'], amp='mobile.test', domain_types={'old-mobile.test': 'amp'},
               domain_added_at={'removed.test': '2026-10-01T09:00:00+00:00'},
               domain_removed_at={'removed.test': '2026-10-10T09:00:00+00:00', 'old-mobile.test': '2026-10-11T09:00:00+00:00'},
               domain_membership_history=[{'domain': 'removed.test', 'added_at': '2026-10-01T09:00:00+00:00', 'removed_at': '2026-10-10T09:00:00+00:00'}])
network['domains'].append(site['name'])
site['added_to_system_at']=network.pop('added_to_system_at')
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
        elif path.endswith('/network'): data = peer_network if path == '/sites/peer/network' else network
        elif path.endswith('/menu-capabilities'): data = dict(check_status='completed')
        elif path == '/auth/me': data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path in ('/sites', '/sites/cache/projects'): data = peers
        elif path == '/sites/lookup': data = next((s for s in peers if s['id'] == parse_qs(urlparse(request.request.url).query).get('site_id', ['enter'])[0]), site)
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        request.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('http://localhost/project-network/enter.test/')
    history = page.get_by_label('Показать историю', exact=True)
    table = page.locator('.networkTable')
    expect(history).not_to_be_checked()
    expect(table.locator('tbody tr')).to_have_count(3)
    reserve_row = table.locator('tbody tr').filter(has=page.get_by_text('reserve.test', exact=True))
    expect(reserve_row.locator('[data-label="Домен"] strong')).to_have_text('reserve.test')
    expect(reserve_row.locator('[data-label="Статус"] strong')).to_have_text('Резерв')
    expect(table.locator('tbody tr').nth(-2).locator('[data-label="Домен"]')).to_have_text('reserve.test')
    expect(table.locator('tbody tr').last.locator('[data-label="Домен"]')).to_have_text('main.test')
    expect(table.get_by_text('old.test', exact=True)).to_have_count(0)
    expect(page.locator('.networkSystemAdded')).to_have_text('Добавлен в систему: 18.10.2026')
    project_row = table.locator('tbody tr').filter(has=page.get_by_text(site['name'], exact=True))
    expect(project_row.locator('[data-label="Дата добавления"]')).to_have_text('18.10.2026, 12:00')
    expect(project_row.locator('[data-label="Дата добавления"]')).to_have_attribute('title', 'Дата добавления проекта в систему (МСК)')
    history.check()
    expect(table.locator('tbody tr')).to_have_count(5)
    expect(table.locator('tbody tr').nth(-2).locator('[data-label="Домен"]')).to_have_text('reserve.test')
    expect(table.locator('tbody tr').last.locator('[data-label="Домен"]')).to_have_text('main.test')
    removed = table.locator('tbody tr').filter(has=page.get_by_text('removed.test', exact=True))
    expect(removed).to_have_class('networkHistoricalDomain')
    expect(removed.locator('[data-label="Дата добавления"]')).to_have_text('01.10.2026, 12:00')
    expect(removed.locator('[data-label="Дата исключения"]')).to_have_text('10.10.2026, 12:00')
    normal = table.locator('tbody tr').filter(has=page.get_by_text('main.test', exact=True))
    assert removed.locator('td').first.evaluate('(el)=>getComputedStyle(el).color') != normal.locator('td').first.evaluate('(el)=>getComputedStyle(el).color')
    expect(normal.locator('[data-label="Дата добавления"]')).to_have_text('—')
    expect(normal.locator('[data-label="Дата исключения"]')).to_have_text('—')
    page.get_by_role('button', name='Ампы', exact=True).click()
    expect(table.locator('tbody tr')).to_have_count(2)
    expect(table.get_by_text('old-mobile.test', exact=True)).to_be_visible()
    history.uncheck()
    expect(table.locator('tbody tr')).to_have_count(1)
    page.get_by_role('button', name='Основная сетка', exact=True).click()
    page.get_by_role('button', name='Выделить', exact=True).click()
    expect(page.get_by_label('Домены для копирования', exact=True)).to_have_value('enter.test\nreserve.test\nmain.test')
    query = page.get_by_role('textbox', name='Поиск по доменам сетки', exact=True)
    query.fill('removed.test')
    expect(table.locator('tbody tr')).to_have_count(0)
    history.check()
    expect(table.locator('tbody tr')).to_have_count(1)
    expect(page.get_by_label('Домены для копирования', exact=True)).to_have_value('removed.test')
    page.reload()
    expect(page.get_by_label('Показать историю', exact=True)).not_to_be_checked()
    query.fill('')
    query.press('Enter')
    network['domain_added_at'][site['name']] = '2026-10-19T05:25:00+00:00'
    page.reload()
    expect(project_row.locator('[data-label="Дата добавления"]')).to_have_text('19.10.2026, 08:25')
    expect(project_row.locator('[data-label="Дата добавления"]')).to_have_attribute('title', 'Добавление в сетку зафиксировано системой (МСК)')
    nav = page.get_by_role('navigation', name='Навигация по сеткам бренда')
    expect(nav.get_by_role('link')).to_have_count(3)
    current = nav.get_by_role('link', name='Открыть сетку enter.test', exact=True)
    expect(current).to_have_attribute('aria-current', 'page')
    expect(nav.get_by_role('link', name='Открыть сетку polish.test', exact=True)).to_be_visible()
    expect(nav.locator('[aria-current="page"] .networkBrandNavigationCount')).to_have_text('3')
    assert nav.bounding_box()['x'] >= page.locator('.networkMembership').bounding_box()['x'] + page.locator('.networkMembership').bounding_box()['width']
    page.screenshot(path='/tmp/pagepilot-reserve-status-20261020/network-navigation.png', full_page=True)
    nav.get_by_role('link', name='Открыть сетку peer.test', exact=True).click()
    expect(page).to_have_url('http://localhost/project-network/peer.test/')
    expect(nav.get_by_role('link', name='Открыть сетку peer.test', exact=True)).to_have_attribute('aria-current', 'page')
    expect(nav.locator('[aria-current="page"] .networkBrandNavigationCount')).to_have_text('2')
    expect(table.locator('tbody tr').last.locator('[data-label="Домен"]')).to_have_text('peer-main.test')
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(nav).to_be_visible()
    assert nav.bounding_box()['width'] < 390
    assert nav.bounding_box()['y'] < page.locator('.networkMembership').bounding_box()['y']
    page.screenshot(path='/tmp/pagepilot-reserve-status-20261020/network-navigation-mobile.png', full_page=True)
    assert not posts
    assert not errors, errors
    browser.close()
print('PASS: all brand networks including other GEO, current highlight, navigation, fresh counts and mobile; bold reserve and Main at the bottom, including history; hidden history, system dates, AMP history, search/copy, project entry date in table, membership date precedence')
