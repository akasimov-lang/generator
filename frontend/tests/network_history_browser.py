import os
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME'), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ.get('VITE_TEST_URL', 'http://127.0.0.1:5174') + '/tests/network.html')
    page.get_by_role('button', name='Test network', exact=True).click()
    for label in ['был Main', 'был в альтернейтах', 'x-default', 'БАН']:
        box = page.get_by_label('reserve.test: ' + label, exact=True)
        expect(box).to_be_enabled()
        box.check()
        expect(box).to_be_checked()
        page.get_by_role('button', name='Обновить данные', exact=True).click()
        expect(box).to_be_checked()
        box.uncheck()
        expect(box).not_to_be_checked()
    # Another user's saved checkbox is shown after focus refresh.
    page.evaluate("window.fixture.main_history.push('reserve.test'); window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_label('reserve.test: был Main', exact=True)).to_be_checked()
    assert not errors, errors
    print('PASS: four editable flags, save/reset, refresh and shared updates')
    browser.close()
