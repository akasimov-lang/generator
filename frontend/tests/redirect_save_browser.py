"""Run only on the remote test host; FIXTURE_HTML is supplied by the runner."""
import json
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('https://redirect.test/',lambda r:r.fulfill(content_type='text/html',body=FIXTURE_HTML))
 page.goto('https://redirect.test/')
 panel=page.get_by_role('region',name='Доменные редиректы',exact=True)
 edit=lambda:panel.get_by_role('button',name='Редактировать редирект naukaprogramowania.pl',exact=True)
 edit().click();panel.get_by_label('Редирект: куда',exact=True).fill('edited.test/path/')
 panel.get_by_role('button',name='Сохранить',exact=True).click()
 expect(panel.locator('.saveIndicator')).to_contain_text('Ожидает предыдущее изменение')
 assert page.evaluate('calls[0].redirect_original_source')=='naukaprogramowania.pl'
 assert page.evaluate('calls[0].expected.rows[0].value')=='katechezatarnow.pl'
 assert page.evaluate('calls.length')==1
 message='Редактируемое значение изменилось. Проверьте данные перед повторным сохранением.'
 page.evaluate('(m)=>phase("failed",m)',message)
 expect(edit()).to_be_enabled()
 assert panel.locator('.domainRedirectActionSlot').evaluate('el=>{const a=el.querySelector(".domainRedirectInlineActions").getBoundingClientRect(),s=el.querySelector(".networkEditStatus").getBoundingClientRect();return s.top>=a.bottom&&s.height>=30}')
 edit().click();panel.get_by_label('Редирект: куда',exact=True).fill('correct.test/')
 panel.get_by_role('button',name='Сохранить',exact=True).click()
 page.evaluate('phase("completed","Сохранено")')
 expect(panel.locator('tbody')).to_contain_text('correct.test/')
 expect(edit()).to_be_enabled()
 panel.get_by_role('button',name='Добавить редирект',exact=True).click()
 panel.get_by_label('Редирект: откуда',exact=True).fill('https://naukaprogramowania.pl/courses/test/')
 panel.get_by_label('Редирект: куда',exact=True).fill('main.test')
 panel.get_by_role('button',name='Сохранить редирект',exact=True).click()
 expect(panel.locator('.domainRedirectFormError')).to_contain_text('Постраничные редиректы')
 assert page.evaluate('calls.length')==2
 panel.get_by_label('Редирект: откуда',exact=True).fill('https://NAUKAPROGRAMOWANIA.PL/')
 panel.get_by_role('button',name='Сохранить редирект',exact=True).click()
 expect(panel.locator('.domainRedirectFormError')).to_contain_text('уже существует')
 assert page.evaluate('calls.length')==2
 expect(panel.get_by_role('button',name='Отмена',exact=True)).to_be_enabled()
 page.set_viewport_size({'width':390,'height':844})
 assert panel.locator('.domainRedirectFormError').evaluate('e=>e.scrollHeight<=e.clientHeight+1')
 panel.get_by_role('button',name='Отмена',exact=True).click()
 page.set_viewport_size({'width':1440,'height':1000})
 page.evaluate('window.hang=true')
 edit().click();panel.get_by_label('Редирект: куда',exact=True).fill('last.test/')
 panel.get_by_role('button',name='Сохранить',exact=True).click()
 expect(panel.get_by_role('button',name='Проверить отправку')).to_be_visible()
 expect(panel.locator('.saveIndicator')).to_have_class('saveIndicator error visible')
 page.evaluate('phase("completed","Сохранено")')
 expect(edit()).to_be_enabled();assert page.evaluate('calls.length')==3
 policy=page.get_by_role('checkbox',name='301 редирект на главный домен при переклее',exact=True)
 expect(policy).not_to_be_checked();policy.check();expect(policy).to_be_checked()
 assert page.evaluate('window.policy') is True
 page.evaluate('window.failPolicy=true');policy.click();expect(policy).to_be_checked()
 expect(page.get_by_text('Ошибка сохранения настройки',exact=True)).to_be_visible()
 assert page.evaluate('window.policy') is True
 assert not errors,errors
 browser.close()
print(json.dumps({'status':'passed','checks':['edit existing row','queue waiting status','failure unlocks editing','error layout','retry successful edit','reject page source locally','reject duplicate locally','mobile error wraps','hung save recovered without duplicate','policy defaults off','policy saved','failed policy write preserves selection']},ensure_ascii=False))
