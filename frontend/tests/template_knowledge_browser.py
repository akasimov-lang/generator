import json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
DIST=Path(os.environ['PAGEPILOT_DIST'])
sites=[dict(id=str(i),name=f'project-{i}.test',brand=brand,cache_geo=geo,base_url=f'https://project-{i}.test',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon=f'project-{i}.test',cache_language='pl',cache_domains=[],project_status='mass_actions',is_test_project=False,is_active=True,has_menu=False,domains_count=1,internal_pages_count=0) for i,(brand,geo) in enumerate([('Lemon Casino','PL'),('Betonred','PL'),('Fontan','CZ')])]
sources=[dict(id='seed',brand='Lemon Casino',geo='PL',title='Existing example',filename='existing.html',url='',structure={})]
uploads=[]
def library(brand='',geo=''):
 generic=brand in ['Онлайн казино','Общие ключи']
 chosen=[s for s in sources if (s['brand']=='Общие ключи' if generic else s['brand']==brand and s['geo']==geo)]
 groups={}
 for s in sources:groups[(s['brand'],s['geo'])]=groups.get((s['brand'],s['geo']),0)+1
 return dict(count=len(chosen),sources=chosen,scopes=[dict(brand=b,geo=g,count=n) for (b,g),n in groups.items()])
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1600,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
 def route(r):
  u=urlparse(r.request.url);path=u.path;q=parse_qs(u.query);data=[]
  if not path.startswith('/api/'):
   f=DIST/path.lstrip('/')
   if not f.is_file():f=DIST/'index.html'
   r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
  path=path[4:]
  if path=='/auth/me':data={'id':'test','username':'test','is_admin':True,'is_active':True}
  elif path in ['/sites','/sites/cache/projects']:data=sites
  elif path=='/ai-providers':data=[dict(id='gemini',name='Gemini',provider_type='gemini',is_active=True)]
  elif path=='/me/favorite-sites':data={'site_ids':[]}
  elif path=='/site-templates/knowledge':
   if r.request.method=='POST':
    payload=r.request.post_data_json;uploads.append(payload)
    general=payload['brand']=='Онлайн казино'
    source=dict(id=str(len(sources)),brand='Общие ключи' if general else payload['brand'],geo='*' if general else payload['geo'],title='Uploaded example',filename=payload['filename'],url=payload['url'],structure={'status':'completed','pages':[{'url':payload['url'],'path':'/','title':'Home'},{'url':payload['url']+'bonus/','path':'/bonus/','title':'Bonus page'}]} if general else {})
    sources.append(source);data={**library(payload['brand'],'PL' if general else payload['geo']),'source':{**source,'duplicate':False}}
   else:data=library(q.get('brand',[''])[0],q.get('geo',[''])[0])
  r.fulfill(content_type='application/json',body=json.dumps(data))
 page.route('**/*',route);page.goto('http://localhost/template-generator')
 section=page.get_by_role('region',name='База знаний конкурентов')
 brand=page.get_by_role('combobox',name='Бренд базы знаний',exact=True)
 brand.click();expect(page.get_by_role('option',name='Lemon Casino',exact=True)).to_be_visible();expect(page.get_by_role('option',name='Betonred',exact=True)).to_be_visible();expect(page.get_by_role('option',name='Fontan',exact=True)).to_have_count(0)
 brand.fill('lemon');brand.press('Enter');expect(section.get_by_role('status').first).to_have_text('В базе: 1')
 html=('<html><title>Example</title><body>'+('Competitor content. '*30)+'</body></html>').encode()
 page.get_by_label('Файлы примеров конкурентов',exact=True).set_input_files({'name':'new.html','mimeType':'text/html','buffer':html})
 page.get_by_role('button',name='Сохранить в базу знаний',exact=True).click();expect(section.get_by_role('status').first).to_have_text('В базе: 2')
 assert uploads[-1]['brand']=='Lemon Casino' and uploads[-1]['geo']=='PL'
 geo=page.get_by_role('combobox',name='ГЕО базы знаний',exact=True);geo.fill('CZ');geo.press('Enter')
 brand.click();expect(page.get_by_role('option',name='Fontan',exact=True)).to_be_visible();expect(page.get_by_role('option',name='Lemon Casino',exact=True)).to_have_count(0);brand.press('Escape')
 brand.fill('общие');brand.press('Enter');expect(page.get_by_text('Все GEO',exact=True)).to_be_visible()
 page.get_by_role('textbox',name='URL примера конкурента',exact=True).fill('https://generic.example/')
 page.get_by_label('Файлы примеров конкурентов',exact=True).set_input_files({'name':'generic.html','mimeType':'text/html','buffer':html})
 page.get_by_role('button',name='Сохранить в базу знаний',exact=True).click();expect(section.get_by_role('status').first).to_have_text('В базе: 1')
 assert uploads[-1]['geo']==''
 section.get_by_text('Загруженные примеры · 1',exact=True).click();section.get_by_text('Структура сайта',exact=True).click();expect(section.get_by_text('Bonus page',exact=False)).to_be_visible()
 page.screenshot(path='/tmp/pagepilot-knowledge-library-20261020/library-desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path='/tmp/pagepilot-knowledge-library-20261020/library-mobile.png',full_page=True)
 page.set_viewport_size({'width':1600,'height':1100})
 page.get_by_role('button',name='Загрузить HTML конкурентов',exact=True).click()
 controls=page.get_by_role('group',name='GEO, бренд и язык',exact=True)
 expect(controls).to_be_visible()
 assert controls.bounding_box()['y'] < page.get_by_role('heading',name='Шаблон из HTML конкурентов',exact=True).bounding_box()['y']
 expect(page.get_by_role('button',name='Сохранить конкурентов',exact=True)).to_be_visible()
 geo=page.get_by_role('combobox',name='ГЕО',exact=True);geo.fill('PL');geo.press('Enter')
 brand=page.get_by_role('combobox',name='Бренд',exact=True);brand.click();expect(page.get_by_role('option',name='Lemon Casino',exact=True)).to_be_visible();expect(page.get_by_role('option',name='Betonred',exact=True)).to_be_visible();expect(page.get_by_role('option',name='Fontan',exact=True)).to_have_count(0)
 brand.fill('Lemon');brand.press('Enter');expect(page.get_by_text('База знаний: 2 примеров подключатся автоматически.',exact=True)).to_be_visible()
 boxes=[controls.get_by_role('combobox',name=name,exact=True).bounding_box() for name in ['ГЕО','Бренд','Язык']]
 assert max(b['y'] for b in boxes)-min(b['y'] for b in boxes)<3
 page.screenshot(path='/tmp/pagepilot-menu-editor-20261020/template-compact-desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path='/tmp/pagepilot-menu-editor-20261020/template-compact-mobile.png',full_page=True)
 assert not errors,errors
 browser.close()
print('PASS: persistent scoped upload/count; GEO brand inventory including Lemon and Betonred; generic all-GEO home and structure; generator automatic knowledge count; mobile')
