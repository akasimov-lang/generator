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
            project_team='4:19', project_status='working', is_test_project=False, has_menu=True, domains_count=70, internal_pages_count=0)
network = dict(canon='main.test', reserve='', domains=['main.test'] + [f'domain-{n}.test' for n in range(1, 70)],
               revision='one', main_history=['historical.test'], x_default_history=[], alternate_history=[],
               amp_domains=[f'amp-{n}.test' for n in range(35)],
               alternateMarkup='', enableAlternates=False, enableCanonical=False, has_head=True,
               alternates=[], operations=[])

network.update(domain_types={d: 'drop' if i % 2 else 'newreg' for i,d in enumerate(network['domains'])},
    domain_classification={'domain-1.test':dict(is_subdomain=True,parent_domain='parent.test',parent_type='newreg',unused_as_main=False),
                           'domain-2.test':dict(is_subdomain=True,parent_domain='drop.test',parent_type='drop',unused_as_main=True),
                           'domain-3.test':dict(is_subdomain=True,parent_domain='unknown.test',parent_type=None,unused_as_main=False)},
    domain_added_at={'domain-1.test':'2026-01-02T00:00:00Z','domain-2.test':'2025-12-31T00:00:00Z'},
    domain_removed_at={'historical.test':'2026-02-01T00:00:00Z','removed.test':'2025-01-02T00:00:00Z'},
    alternate_history=['domain-1.test'], x_default_history=['domain-2.test'], domain_bans={'domain-3.test':True},
    recent_network_changes=[dict(id=str(n), kind='alternates', at=f'2026-11-18T10:{n:02d}:00Z',
      old_main=None, new_main=None, old_path=None, new_path=None, initiator='test',
      alternates_before=dict(markup='before\n'*70, enabled=True),
      alternates_after=dict(markup='after\n'*70, enabled=True)) for n in range(20)])
peers = [site] + [{**site, 'id':f'peer-{n}', 'name':f'peer-{n}.test', 'cache_canon':f'peer-{n}.test'} for n in range(1, 20)]
pending = []
checks = []
with sync_playwright() as p, httpx.Client(base_url='http://frontend', timeout=30) as frontend:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def route(r):
        if r.request.method == 'POST' and urlparse(r.request.url).path.endswith('/notifications'):
            r.fulfill(content_type='application/json',body='{}')
            return
        if r.request.method != 'GET':
            assert r.request.method == 'PATCH' and urlparse(r.request.url).path.endswith('/network/domain-history'), r.request.url
            pending.append((r, r.request.post_data_json))
            return
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
        elif path in ('/sites', '/sites/cache/projects'): data = peers
        elif path == '/sites/lookup': data = site
        elif path == '/me/favorite-sites': data = {'site_ids': []}
        r.fulfill(content_type='application/json', body=json.dumps(data))

    page.route('**/*', route)
    page.goto('http://localhost/project-network/main.test/')
    table = page.locator('.networkTable')
    rows = table.locator('tbody tr')
    viewport = page.get_by_role('region', name='Домены сетки', exact=True)
    expect(rows).to_have_count(70)
    assert table.locator('th').all_text_contents()[1:] == ['Тип домена','Status','Main','Alternate','x-default','БАН','Действия','Дата добавления','Дата исключения']
    assert table.locator('[data-label="Поддомен"]').count() == 0
    expect(table.get_by_text('Поддомен N', exact=True)).to_be_visible()
    expect(table.get_by_text('Поддомен D', exact=True)).to_be_visible()
    expect(table.get_by_text('Поддомен', exact=True)).to_be_visible()
    assert 'drop.test' in table.get_by_text('Поддомен D', exact=True).get_attribute('title')
    checks.append('merged domain type column with N/D and unknown parent')

    def dimensions():
        return page.evaluate("""() => {
          const wrap=document.querySelector('.networkTableWrap'), sidebar=document.querySelector('.networkSidebar');
          const boxes=[...sidebar.children].map(e=>e.getBoundingClientRect());
          const rows=wrap.querySelectorAll('tbody tr');
          return {height:wrap.clientHeight,bottom30:rows[29]?.getBoundingClientRect().bottom-wrap.getBoundingClientRect().top+wrap.scrollTop,
            sidebarBottom:sidebar.getBoundingClientRect().bottom, tableBottom:wrap.getBoundingClientRect().bottom,
            boxHeights:boxes.map(r=>r.height)};
        }""")
    page.wait_for_timeout(100)
    measured=dimensions()
    assert abs(measured['height']-measured['bottom30'])<=2, measured
    assert abs(measured['sidebarBottom']-measured['tableBottom'])<=2, measured
    assert abs(measured['boxHeights'][0]-measured['boxHeights'][1])<=2, measured
    history=page.locator('.networkSidebar .lastReglueHistory')
    history.locator('summary').first.click()
    page.wait_for_timeout(100)
    expanded=dimensions()
    assert expanded['boxHeights']==measured['boxHeights'] and expanded['height']==measured['height'], (measured,expanded)
    assert abs(expanded['sidebarBottom']-expanded['tableBottom'])<=2
    assert history.evaluate('e=>e.scrollHeight>e.clientHeight')
    nav=page.locator('.networkBrandNavigation ul')
    assert nav.evaluate('e=>e.scrollHeight>e.clientHeight')
    nav.evaluate('e=>e.scrollTop=e.scrollHeight')
    assert nav.evaluate('e=>e.lastElementChild.getBoundingClientRect().bottom<=e.getBoundingClientRect().bottom+1')
    checks.append('equal sidebar heights follow 30-row cap, independent scrolling')

    def names(): return rows.locator('td:first-child').evaluate_all(r"es=>es.map(e=>e.textContent.replace(/^\d+/, '').trim())")
    def sort(label):
        table.get_by_role('button',name='Сортировать: '+label,exact=True).click()
        page.wait_for_timeout(40)
    sort('Домены')
    assert names().index('domain-2.test') < names().index('domain-10.test')
    assert table.locator('th').first.get_attribute('aria-sort')=='ascending'
    before=names();sort('Домены');assert names()==list(reversed(before))
    for label in ['Тип домена','Status']:
        sort(label)
        assert rows.locator('td[data-label="'+label+'"]').evaluate_all("""es=>{
          const values=es.map(e=>e.querySelector('select')?.selectedOptions[0].textContent||e.textContent);
          return values.every((v,i)=>!i||new Intl.Collator('ru',{numeric:true,sensitivity:'base'}).compare(values[i-1],v)<=0);
        }"""), label
        sort(label)
        assert table.locator('th[aria-sort="descending"]').count()==1
    for label in ['Main','Alternate','x-default','БАН']:
        sort(label)
        values=rows.locator('td[data-label="'+label+'"] input').evaluate_all('es=>es.map(e=>Number(e.checked))')
        assert values==sorted(values), (label,values)
        sort(label)
        values=rows.locator('td[data-label="'+label+'"] input').evaluate_all('es=>es.map(e=>Number(e.checked))')
        assert values==sorted(values, reverse=True), (label,values)
    sort('Дата добавления');assert names()[:2]==['domain-2.test','domain-1.test']
    sort('Дата добавления');assert names()[:2]==['domain-1.test','domain-2.test']
    page.get_by_label('Показать историю',exact=True).check()
    sort('Дата исключения');assert names()[:2]==['removed.test','historical.test']
    sort('Дата исключения');assert names()[:2]==['historical.test','removed.test']
    search=page.get_by_label('Поиск по доменам сетки',exact=True)
    search.fill('domain-1.test');expect(rows).to_have_count(1)
    sort('Домены');expect(rows).to_have_count(1)
    assert viewport.evaluate('e=>!e.style.maxHeight')
    assert abs(dimensions()['sidebarBottom']-dimensions()['tableBottom'])<=2
    search.fill('');page.get_by_label('Показать историю',exact=True).uncheck()
    expect(rows).to_have_count(70)
    table.get_by_role('button',name='Сортировать: Домены',exact=True).focus()
    direction=table.locator('th').first.get_attribute('aria-sort')
    page.keyboard.press('Enter')
    assert table.locator('th').first.get_attribute('aria-sort')!=direction
    checks.append('sorting all value columns, dates missing last, natural domains, filter, keyboard')

    widths=table.locator('th').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().width)')
    a=page.get_by_label('domain-5.test: Main',exact=True)
    b=page.get_by_label('domain-6.test: Alternate',exact=True)
    a.check();b.check()
    expect(a).to_be_disabled();expect(b).to_be_disabled()
    save=page.locator('.networkTableSave .saveIndicator')
    expect(save).to_have_class('saveIndicator saving visible')
    assert save.evaluate('e=>getComputedStyle(e).color')=='rgb(22, 160, 100)'
    assert save.locator('svg').evaluate('e=>getComputedStyle(e).animationName')=='saveIndicatorPulse'
    assert save.inner_text()==''
    assert table.locator('th').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().width)')==widths
    def finish(domain, error=False):
        r, payload=next(item for item in pending if item[1]['domain']==domain)
        pending.remove((r,payload))
        if error:
            r.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'Сервер временно недоступен. Повторите попытку через несколько секунд.'}))
        else:
            field=payload['field']
            prop={'main':'main_history','alternate':'alternate_history','x_default':'x_default_history'}[field]
            network[prop]=[d for d in network[prop] if d!=domain]+([domain] if payload['checked'] else [])
            r.fulfill(content_type='application/json',body=json.dumps(network))
    finish('domain-5.test')
    expect(a).to_be_enabled();expect(a).to_be_checked()
    expect(save).to_have_class('saveIndicator saving visible')
    finish('domain-6.test',True)
    expect(b).to_be_enabled();expect(b).not_to_be_checked()
    log=page.locator('.networkTableSaveHistory')
    expect(log.locator('[role=alert]')).to_contain_text('Сервер временно недоступен')
    assert 'domain-6.test' in log.inner_text() and 'Alternate' in log.inner_text()
    assert table.locator('th').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().width)')==widths
    assert not any(word in table.inner_text() for word in ['Сохранено','Сохраняем','Сервер временно'])
    page.reload();expect(rows).to_have_count(70)
    expect(page.get_by_label('domain-5.test: Main',exact=True)).to_be_checked()
    expect(log.locator('[role=alert]')).to_contain_text('Сервер временно недоступен')
    checks.append('concurrent saves, green blinking icon, no width change, errors in lower history, reload')
    page.get_by_role('button',name='Ампы',exact=True).click()
    expect(rows).to_have_count(35)
    assert rows.locator('td[data-label="Тип домена"]').all_text_contents()==['AMP']*35
    sort('Домены');assert names()[:3]==['amp-0.test','amp-1.test','amp-2.test']
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100)
    assert abs(dimensions()['height']-dimensions()['bottom30'])<=2
    assert viewport.evaluate('e=>e.getBoundingClientRect().right<=innerWidth')
    assert page.locator('.networkSidebar').evaluate('e=>getComputedStyle(e).gridTemplateColumns.split(" ").length')==1
    checks.append('AMP sorting and mobile layout')
    assert not errors, errors
    browser.close()
print(json.dumps({'passed':True,'checks':checks},ensure_ascii=False))
