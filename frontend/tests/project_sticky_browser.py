"""Run with FIXTURE_HTML injected, in the server container only."""
import json,base64
from playwright.sync_api import sync_playwright
shots=[];checks=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 c=b.new_context(viewport={'width':1280,'height':900});c.set_default_timeout(8000)
 c.route('**/*',lambda r:r.fulfill(status=200,content_type='text/html',body=FIXTURE_HTML) if r.request.is_navigation_request() else r.abort())
 p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.goto('https://sticky.test/')
 trigger=p.get_by_role('button',name='Заметка проекта a.test',exact=True);trigger.click();area=p.get_by_role('textbox',name='Текст заметки a.test')
 area.fill('Первая заметка\nВажная запись 📝');p.wait_for_function('notes.a?.text.includes("Важная запись")');assert p.locator('.stickyPaperPen').count()==1
 assert p.locator('.projectStickySave').get_attribute('aria-label')=='Сохранено'
 # Typing while the previous request is in flight must save the latest draft, in order.
 p.evaluate('window.delay=900');area.fill('Первое изменение');p.wait_for_function('puts.length===2');assert p.locator('.projectStickySave.isSaving').count()==1
 area.fill('Последнее изменение');p.wait_for_function('notes.a?.text==="Последнее изменение"');p.evaluate('window.delay=0')
 p.get_by_role('button',name='Закрыть заметку',exact=True).click();assert p.get_by_role('dialog').count()==0;trigger.click();assert area.input_value()=='Последнее изменение'
 # Drag by header; close and reopen retains position. Keyboard can also move it.
 grip=p.locator('.projectStickyGrip');box=grip.bounding_box();old=p.locator('.projectStickyNote').bounding_box();p.mouse.move(box['x']+15,box['y']+10);p.mouse.down();p.mouse.move(box['x']-160,box['y']+100);p.mouse.up();new=p.locator('.projectStickyNote').bounding_box();assert new['x']<old['x'] and new['y']>old['y']
 grip.focus();p.keyboard.press('ArrowLeft');assert p.locator('.projectStickyNote').bounding_box()['x']<new['x'];p.keyboard.press('Escape');trigger.click()
 # Switching project flushes a debounce immediately and does not copy text.
 area.fill('Сохранить при смене');p.get_by_role('button',name='Сменить проект').click();p.wait_for_function('notes.a.text==="Сохранить при смене"');p.get_by_role('button',name='Заметка проекта b.test',exact=True).click();area=p.get_by_role('textbox',name='Текст заметки b.test');assert area.input_value()==''
 area.fill('Заметка B');p.wait_for_function('notes.b?.text==="Заметка B"');assert p.locator('#order li').all_text_contents()==['a','b','c']
 # Transport error preserves the draft and an explicit retry recovers.
 p.evaluate('window.fail=true');area.fill('Черновик без связи');p.get_by_role('button',name='Повторить',exact=True).wait_for();assert area.input_value()=='Черновик без связи';assert p.locator('.projectStickySave.hasError').count()==1
 p.get_by_role('button',name='Закрыть заметку',exact=True).click();p.evaluate('window.fail=false');p.get_by_role('button',name='Заметка проекта b.test',exact=True).click();p.get_by_role('button',name='Повторить',exact=True).click();p.wait_for_function('notes.b.text==="Черновик без связи"')
 # Concurrent edits cannot silently overwrite another user's note.
 p.evaluate('notes.b={text:"Другой автор",revision:"external"}');area.fill('Моя версия');p.get_by_role('button',name='Сохранить мой текст',exact=True).wait_for();assert p.evaluate('notes.b.text')=='Другой автор';assert area.input_value()=='Моя версия';p.get_by_role('button',name='Сохранить мой текст',exact=True).click();p.wait_for_function('notes.b.text==="Моя версия"')
 shots.append({'name':'desktop.png','data':base64.b64encode(p.screenshot()).decode()})
 # Clearing a note removes its filled icon and sort priority.
 area.fill('  \n ');p.wait_for_function('notes.b.text.trim()===""');assert p.locator('.stickyPaperPen').count()==0
 p.get_by_role('button',name='Сменить проект').click();p.get_by_role('button',name='Заметка проекта a.test',exact=True).click();area=p.get_by_role('textbox',name='Текст заметки a.test');area.fill('');p.wait_for_function('notes.a.text===""');assert p.locator('#order li').all_text_contents()==['a','b','c']
 p.get_by_role('button',name='Сменить проект').click();p.get_by_role('button',name='Заметка проекта b.test',exact=True).click();area=p.get_by_role('textbox',name='Текст заметки b.test');area.fill('Теперь B выше');p.wait_for_function('notes.b.text==="Теперь B выше"');assert p.locator('#order li').all_text_contents()==['b','a','c']
 p.set_viewport_size({'width':320,'height':568});p.wait_for_timeout(100);box=p.locator('.projectStickyNote').bounding_box();assert box['x']>=0 and box['x']+box['width']<=320 and box['y']+box['height']<=568
 shots.append({'name':'mobile.png','data':base64.b64encode(p.screenshot()).decode()});assert not errors,errors
 checks=['autosave','latest typing during save','close/reopen','drag','keyboard move/Escape','project isolation','flush on project switch','offline draft/retry','concurrent conflict','empty note loses priority','notes before pagination','mobile bounds']
 c.close();b.close()
print(json.dumps({'checks':checks,'ok':True,'shots':shots},ensure_ascii=False))
