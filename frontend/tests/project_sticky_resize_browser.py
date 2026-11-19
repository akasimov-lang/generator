"""Server-only browser test; inject the built harness as FIXTURE_HTML."""
import json,base64
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 c=b.new_context(viewport={'width':1280,'height':900});c.set_default_timeout(8000)
 c.route('**/*',lambda r:r.fulfill(status=200,content_type='text/html',body=FIXTURE_HTML) if r.request.is_navigation_request() else r.abort())
 p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.goto('https://sticky.test/')
 trigger=p.get_by_role('button',name='Заметка проекта a.test',exact=True);trigger.click();note=p.locator('.projectStickyNote');area=p.get_by_role('textbox',name='Текст заметки a.test');area.fill('Текст остаётся после изменения размера');p.wait_for_function('notes.a?.text.includes("размера")')
 grip=p.locator('.projectStickyGrip').bounding_box();p.mouse.move(grip['x']+20,grip['y']+12);p.mouse.down();p.mouse.move(300,80);p.mouse.up()
 before=note.bounding_box();handle=p.get_by_role('button',name='Изменить размер заметки');box=handle.bounding_box();p.mouse.move(box['x']+10,box['y']+10);p.mouse.down();p.mouse.move(box['x']+210,box['y']+110);p.mouse.up()
 enlarged=note.bounding_box();assert enlarged['width']>before['width']+180 and enlarged['height']>before['height']+80
 assert enlarged['x']==before['x'] and enlarged['y']==before['y'];assert area.input_value()=='Текст остаётся после изменения размера'
 p.get_by_role('button',name='Закрыть заметку',exact=True).click();trigger.click();assert note.bounding_box()==enlarged
 grip=p.locator('.projectStickyGrip').bounding_box();p.mouse.move(grip['x']+20,grip['y']+12);p.mouse.down();p.mouse.move(1275,895);p.mouse.up();moved=note.bounding_box();assert moved['x']+moved['width']<=1272 and moved['y']+moved['height']<=892
 handle.focus();p.keyboard.press('ArrowLeft');assert note.bounding_box()['width']==enlarged['width']-16
 box=handle.bounding_box();p.mouse.move(box['x']+10,box['y']+10);p.mouse.down();p.mouse.move(10,10);p.mouse.up();small=note.bounding_box();assert small['width']==260 and small['height']==220
 handle.focus();p.keyboard.press('ArrowRight');p.keyboard.press('ArrowDown');custom=note.bounding_box()
 p.get_by_role('button',name='Сменить проект').click();p.get_by_role('button',name='Заметка проекта b.test',exact=True).click();assert note.bounding_box()['width']==350
 p.get_by_role('button',name='Сменить проект').click();trigger.click();assert note.bounding_box()['width']==custom['width'] and note.bounding_box()['height']==custom['height']
 p.reload();trigger.click();assert note.bounding_box()['width']==custom['width'] and note.bounding_box()['height']==custom['height']
 p.set_viewport_size({'width':320,'height':480});p.wait_for_timeout(100);mobile=note.bounding_box();assert mobile['x']>=8 and mobile['y']>=8 and mobile['x']+mobile['width']<=312 and mobile['y']+mobile['height']<=472
 assert not errors,errors
 shot=base64.b64encode(p.screenshot()).decode();b.close()
print(json.dumps({'ok':True,'checks':['corner drag','text preserved','close/reopen size','drag bounds use resized dimensions','keyboard resize','minimum size','per-project size','reload persistence','mobile bounds'],'shots':[{'name':'resize-mobile.png','data':shot}]}))
