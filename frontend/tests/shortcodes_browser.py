import copy,json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
site=dict(id='preview',name='example.pl',brand='Lemon Casino',base_url='https://example.pl',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='example.pl',cache_geo='PL',cache_language='pl',cache_domains=['example.pl'],project_status='mass_actions',is_test_project=False,has_menu=False,domains_count=1,internal_pages_count=1)
value=dict(key='home',title='Page',description='Description',slug='/',is_home=True,revision='a'*64,
 shortcodes=[{'name':n,'uses_on_site':4 if n!='footer' else 0,'pages_count':2 if n!='footer' else 0,'defined':True} for n in ['section-open','section-close','footer']],
 content={'version':'2.28','custom':'keep-document','blocks':[
 {'id':'open-1','type':'shortcode','data':{'shortcode':'section-open','custom':'keep-shortcode'}},
 {'id':'heading','type':'header','data':{'text':'Page heading','level':1}},
 {'id':'p1','type':'paragraph','data':{'text':'First paragraph with <strong>bold</strong> and a <a href="/terms/">link</a>.','custom':'keep-paragraph'}},
 {'id':'p2','type':'paragraph','data':{'text':'Second paragraph.'}},
 {'id':'close-1','type':'shortcode','data':{'shortcode':'section-close'}},
 {'id':'open-2','type':'shortcode','data':{'shortcode':'section-open'}},
 {'id':'close-2','type':'shortcode','data':{'shortcode':'section-close'}}]})
before=copy.deepcopy(value);saved=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1700,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  path=urlparse(r.request.url).path;data=[]
  if not path.startswith('/api/'):
   asset=DIST/path.lstrip('/')
   if not asset.is_file():asset=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
  path=path[4:]
  if path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=[site]
  elif path=='/sites/preview/pages/home':
   data=value
   if r.request.method=='PUT':
    b=r.request.post_data_json;saved.append(b)
    for k in ['title','description','content']:value[k]=b[k]
    value['revision']='b'*64;data={'id':b['request_id'],'status':'confirmed','page':value}
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/page-editor/preview/home/')
 sidebar=page.get_by_role('complementary',name='Шорткоды сайта',exact=True);expect(sidebar).to_be_visible()
 expect(sidebar).to_contain_text('На странице: 4');expect(sidebar.locator('li')).to_have_count(3)
 expect(sidebar.get_by_role('button',name='Перейти к шорткоду section-open',exact=True)).to_contain_text('×2')
 assert sidebar.bounding_box()['x']<page.locator('.pp-editor-content').bounding_box()['x']
 inputs=page.get_by_role('textbox',name='Шорткод',exact=True);expect(inputs).to_have_count(4)
 assert inputs.first.evaluate('el=>el.tagName')=='INPUT'
 assert inputs.first.bounding_box()['height']<=34
 assert page.locator('.pp-shortcode-block').first.bounding_box()['height']<100
 rich=page.locator('[data-block-type="paragraph"] .pp-rich-text')
 gap=rich.nth(1).bounding_box()['y']-(rich.first.bounding_box()['y']+rich.first.bounding_box()['height'])
 assert gap<40,gap
 jump=sidebar.get_by_role('button',name='Перейти к шорткоду section-open',exact=True)
 jump.click();assert page.evaluate('document.activeElement.closest(".pp-content-block").id')=='page-editor-block-0'
 jump.click();assert page.evaluate('document.activeElement.closest(".pp-content-block").id')=='page-editor-block-5'
 inputs.first.fill('new-code');expect(sidebar.get_by_role('button',name='Перейти к шорткоду new-code',exact=True)).to_contain_text('×1')
 inputs.first.fill('section-open')
 # The HTML source toolbar remains accessible after compacting its idle spacing.
 rich.first.click();page.locator('#page-editor-block-2').get_by_role('button',name='HTML текста',exact=True).click()
 html=page.get_by_role('textbox',name='Текст: HTML',exact=True).first
 html.fill('Edited <strong>bold</strong> paragraph with <a href="/terms/">link</a>.')
 page.get_by_role('button',name='Сохранить на сайте',exact=True).click()
 expect(page.get_by_role('status').filter(has_text='Изменения сохранены')).to_be_visible()
 assert len(saved)==1
 result=saved[0]['content'];assert result['custom']=='keep-document'
 assert result['blocks'][0]==before['content']['blocks'][0]
 assert result['blocks'][2]['data']['custom']=='keep-paragraph'
 assert '<strong>bold</strong>' in result['blocks'][2]['data']['text']
 assert '<a href="/terms/">' in result['blocks'][2]['data']['text']
 page.evaluate('window.scrollTo(0,500)');page.wait_for_timeout(100)
 assert sidebar.bounding_box()['y']>=page.locator('.pp-editor-header').bounding_box()['y']+page.locator('.pp-editor-header').bounding_box()['height']
 page.screenshot(path=str(DIST.parent/'shortcodes-desktop.png'),full_page=True)
 page.goto('http://localhost/page-preview/preview/home/');expect(sidebar).to_be_visible();expect(sidebar).to_contain_text('section-open')
 page.set_viewport_size({'width':390,'height':844});expect(sidebar).to_be_visible()
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 page.screenshot(path=str(DIST.parent/'shortcodes-mobile.png'),full_page=True)
 assert not errors,errors;browser.close()
print('PASS: left shortcode inventory in editor/preview, live counts and cycling navigation, compact inputs/paragraph gaps, HTML tools and all unknown document fields preserved on save, mobile')
