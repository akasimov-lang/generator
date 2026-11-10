"""Server-only check of deployed dashboard assets and real, read-only task data."""
import json
import os
import re
import sys
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

assert sys.platform != 'darwin', 'Run this browser check on the server, not on the Mac.'

from app.db import SessionLocal
from app.fibery_tasks import feed

base = os.environ.get('PAGEPILOT_BROWSER_URL', 'https://ai-seo-content-panel.site').rstrip('/')
asset_origin = os.environ.get('PAGEPILOT_ASSET_ORIGIN', 'http://frontend').rstrip('/')
user = {'username': 'anton', 'allowed_site_ids': None}
with SessionLocal() as db:
    snapshot = feed(db, user)
assert {'33302', '33312', '33313'}.issubset({row['number'] for row in snapshot['items']})

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors, writes, task_reads = [], [], []
    fail = {'next': False}
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def assets(route):
        parsed = urlparse(route.request.url)
        result = route.fetch(url=asset_origin + parsed.path + ('?' + parsed.query if parsed.query else ''))
        route.fulfill(response=result)

    def api(route):
        parsed = urlparse(route.request.url)
        path = parsed.path[4:]
        if route.request.method != 'GET':
            writes.append(path)
        data = []
        if path == '/auth/me':
            data = dict(id='test', username='test', is_admin=True, is_active=True)
        elif path == '/dashboard':
            data = {'stats': {k: 0 for k in ('total_tasks', 'awaiting_approve', 'scheduled', 'published', 'errors')},
                    'recent_errors': [], 'active_tasks': [], 'publication_queue': []}
        elif path == '/dashboard-activity':
            data = {'active': [], 'items': [], 'next_before': None}
        elif path == '/reglue-journal/summary':
            data = {'today_count': 2}
        elif 'favorite-sites' in path:
            data = {'site_ids': []}
        elif path == '/dashboard-activity/fibery-tasks':
            task_reads.append(parsed.query)
            if fail['next']:
                route.fulfill(status=503, content_type='application/json', body=json.dumps({'detail': 'Проверка недоступности'}))
                return
            query = parse_qs(parsed.query)
            with SessionLocal() as db:
                # Small pages exercise navigation using actual saved tasks.
                data = feed(db, user, query=query.get('q', [''])[0], before=query.get('before', [None])[0], limit=2)
        route.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', assets)
    page.route('**/api/**', api)
    page.goto(base + '/dashboard')
    choose = page.get_by_role('button', name='Задачи Fibery', exact=True)
    choose.focus(); choose.press('Enter')
    expect(choose).to_have_attribute('aria-pressed', 'true')
    panel = page.locator('.dashboardFibery')
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(2)
    expect(page).to_have_url(re.compile('collection=fibery'))
    panel.get_by_role('button', name='Следующие', exact=True).click()
    expect(panel).to_contain_text('Страница 2')
    panel.get_by_role('button', name='Предыдущие', exact=True).click()
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(2)
    search = panel.get_by_role('searchbox', name='Поиск задач Fibery')
    search.fill('#33302')
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(1)
    expect(panel).to_contain_text('Ionickiss: витрина и ссылки')
    search.fill('BetOnRed')
    expect(panel).to_contain_text('www.textilbrno.cz → www.mapovani.cz')
    search.fill('#33313')
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(1)
    link = panel.get_by_role('link', name='Открыть задачу')
    expect(link).to_have_attribute('href', 'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Tasks/33313')
    expect(link).to_have_attribute('target', '_blank')
    search.fill('missing-fibery-task')
    expect(panel).to_contain_text('По вашему запросу задачи не найдены.')
    search.fill('')
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(2)
    fail['next'] = True
    panel.get_by_role('button', name='Обновить', exact=True).click()
    expect(panel.get_by_role('alert')).to_be_visible(timeout=15000)
    fail['next'] = False
    panel.get_by_role('button', name='Обновить', exact=True).click()
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(2)
    before = len(task_reads)
    page.wait_for_timeout(16000)
    assert len(task_reads) > before, 'visible collection did not refresh'
    page.reload()
    expect(page.get_by_role('button', name='Задачи Fibery', exact=True)).to_have_attribute('aria-pressed', 'true')
    expect(panel.locator('.dashboardFiberyTask')).to_have_count(2)
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(search).to_be_visible()
    expect(panel.get_by_role('link', name='Открыть задачу').first).to_be_visible()
    assert panel.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'), 'task list overflows mobile width'
    page.get_by_role('button', name='История действий', exact=True).click()
    expect(page.locator('.dashboardActivity')).to_be_visible()
    reads = len(task_reads)
    page.wait_for_timeout(16000)
    assert len(task_reads) == reads, 'unselected collection keeps polling'
    assert not writes, writes
    assert not errors, errors
    browser.close()

print(json.dumps({'status': 'passed', 'total': snapshot['total'], 'checks': ['switch', 'keyboard', 'deep-link',
    'pagination', 'search', 'safe-task-link', 'empty', 'retry', 'auto-refresh', 'mobile', 'stop-on-switch'],
    'api_writes': writes, 'page_errors': errors}, ensure_ascii=False))
