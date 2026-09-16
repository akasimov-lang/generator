"""Run against Vite with Playwright installed; all API traffic is mocked."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base = os.environ.get('VITE_TEST_URL', 'http://127.0.0.1:5174')
artifacts = Path(os.environ.get('DESIGN_ARTIFACTS', '/private/tmp/pagepilot-design-tests'))
artifacts.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME'), headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors, writes = [], []
    admin = True
    page.on('pageerror', lambda e: errors.append(str(e)))
    def api(route):
        if route.request.method != 'GET':
            writes.append(route.request.url)
        path = route.request.url.split('/api')[-1].split('?')[0]
        data = {'id': 'test', 'username': 'design-review', 'is_admin': admin, 'is_active': True} if path == '/auth/me' else {} if path == '/dashboard' else []
        route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
    context.route('**/api/**', api)
    page.goto(base)
    page.evaluate('localStorage.setItem("admin_token", "mock"); sessionStorage.setItem("popup_permission_prompt_closed", "true")')
    page.goto(base + '/settings')
    choices = page.get_by_role('radiogroup', name='Версия дизайна')
    expect(choices).to_be_visible()
    for theme in ['light', 'dark']:
        page.evaluate('(theme)=>localStorage.setItem("theme_mode",theme)', theme)
        page.reload()
        for version in ['1.0', '2.0']:
            page.locator(f'input[name="design-version"][value="{version}"]').check()
            expect(page.locator('html')).to_have_attribute('data-design-version', version)
            assert page.evaluate('localStorage.getItem("pagepilot_design_version")') == version
            expect(page.locator('.brand strong')).to_have_text('Content Admin' if version == '1.0' else 'PagePilot')
            expected = ('rgb(22, 101, 52)' if theme == 'light' else 'rgb(74, 222, 128)') if version == '1.0' else ('rgb(49, 87, 216)' if theme == 'light' else 'rgb(65, 103, 229)')
            assert page.locator('.button.primary').first.evaluate('(e)=>getComputedStyle(e).backgroundColor') == expected
            page.screenshot(path=str(artifacts / f'settings-{version}-{theme}.png'), full_page=True, animations='disabled')
            page.reload()
            expect(page.locator(f'input[name="design-version"][value="{version}"]')).to_be_checked()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate('Array.from(document.querySelectorAll("body *")).filter(e=>e.getBoundingClientRect().right>innerWidth).slice(0,15).map(e=>({tag:e.tagName,cls:e.className,w:e.getBoundingClientRect().width}))')
    page.screenshot(path=str(artifacts / 'settings-mobile.png'), full_page=True, animations='disabled')
    # A change in another tab propagates without reloading the current tab.
    other = context.new_page()
    other.goto(base + '/settings')
    other.locator('input[name="design-version"][value="1.0"]').check()
    expect(page.locator('html')).to_have_attribute('data-design-version', '1.0')
    other.close()
    admin = False
    page.reload()
    expect(page.get_by_text('Аккаунт', exact=True)).to_be_visible()
    expect(choices).to_have_count(0)
    for version in ['1.0', '2.0']:
        page.evaluate('(v)=>{localStorage.removeItem("admin_token");localStorage.setItem("pagepilot_design_version",v)}', version)
        page.reload()
        expect(page.locator('.loginBrandRow h1')).to_contain_text('Версия ' + version)
        expect(page.locator('link[rel="icon"]')).to_have_attribute('href', '/favicon-v1.svg' if version == '1.0' else '/pagepilot-mark.svg?v=20260916')
    assert not writes, writes
    assert not errors, errors
    browser.close()
print('PASS: admin-only design selector, 1.0/2.0 colors and logos, both themes, persistence, cross-tab sync, login, mobile, no API writes or JS errors.')
print('Screenshots:', artifacts)
