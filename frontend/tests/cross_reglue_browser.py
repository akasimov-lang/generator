import os
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME'), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ.get('VITE_TEST_URL', 'http://127.0.0.1:5174') + '/tests/cross-reglue.html')
    select = page.get_by_role('combobox', name='Режим массового переклея')
    select.click()
    expect(page.get_by_role('listbox', name='Режим массового переклея').get_by_role('option')).to_have_count(2)
    select.fill('Перекрёстный'); select.press('Enter')
    expect(select).to_have_value('Перекрёстный — между сетками бренда и GEO')
    select.click()
    expect(page.get_by_role('listbox', name='Режим массового переклея').get_by_role('option')).to_have_count(2)
    select.fill('неизвестно')
    expect(page.get_by_text('Ничего не найдено', exact=False)).to_be_visible()
    select.press('Escape')
    expect(select).to_have_value('Перекрёстный — между сетками бренда и GEO')
    page.get_by_label('Чистый альтернейт — очистить альтернейты при переклее').check()
    page.get_by_role('button', name='Сохранить общие настройки').click()
    assert page.evaluate('window.saved.execution_mode') == 'cross_network'
    assert page.evaluate('window.saved.scheme_mode') == 'clean'
    page.get_by_text('Результат и история изменений',exact=True).click()
    page.get_by_text('Альтернейты: было / стало',exact=True).click()
    expect(page.get_by_text('Стало · выключены',exact=True)).to_be_visible()
    expect(page.locator('pre').filter(has_text='https://old.test/')).to_be_visible()
    expect(page.get_by_text('Пусто',exact=True)).to_be_visible()
    assert not errors, errors
    print('PASS: searchable modes, clean save, confirmed before/after history')
    browser.close()
