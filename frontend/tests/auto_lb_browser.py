"""Browser contract using built assets and mocked APIs; no paid Gemini calls."""
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'reports/auto-lb'
ART.mkdir(exist_ok=True)
anchors = '\n'.join(['BetOnRed']*298+['current.example','https://current.example'])
topics = '\n'.join(f'Téma {i}' for i in range(300))
site = dict(id='own', name='own.test', brand='BetOnRed',brand_source='manual',base_url='https://own.test',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='current.example',cache_geo='CZ',cache_language='cs',cache_domains=[],project_status='working',is_test_project=False,has_menu=False,domains_count=1,internal_pages_count=0)
ctx={'brand':'BetOnRed','geo':'CZ','language':'cs','main':'current.example','main_url':'https://current.example'}
state={'context':ctx,'context_error':None,'provider_ready':True,'anchor_count':300,'topic_count':300,'topic_text':'','prompts':{'anchors':'Anchor prompt','topics':'Topic prompt'},'generations':[]}
writes=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true");Object.defineProperty(navigator,"clipboard",{value:{writeText:async text=>{window.copied=text}}})')
    def route(r):
        path=urlparse(r.request.url).path
        if not path.startswith('/api/'):
            f=ROOT/'frontend/dist'/path.lstrip('/')
            if not f.is_file():f=ROOT/'frontend/dist/index.html'
            r.fulfill(content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes());return
        path=path[4:];data=[]
        if path=='/auth/me':data={'id':'editor','username':'editor','is_admin':False,'is_active':True,'allowed_site_ids':['own']}
        elif path=='/sites':data=[site]
        elif path=='/sites/lookup':data=site
        elif path=='/me/favorite-sites':data={'site_ids':[]}
        elif path=='/sites/own/auto-lb':
            if r.request.method=='POST':
                kind=r.request.post_data_json['kind'];writes.append(kind)
                row={'id':kind+str(len(writes)),'kind':kind,'status':'queued','context':dict(ctx),'prompt':kind+' prompt','text':'','error':None,'line_count':0,'unique_count':0,'created_at':'2026-10-09T12:00:00Z'}
                state['generations'].insert(0,row);data=row
            else:data=state
        r.fulfill(content_type='application/json',body=json.dumps(data))
    page.route('**/*',route)
    page.goto('http://localhost/project-auto-lb/own.test')
    expect(page.get_by_role('heading',name='АвтоЛБ',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='Скопировать анкор-лист')).to_be_disabled()
    page.get_by_role('button',name='Сгенерировать анкор-лист').click()
    page.get_by_role('button',name='Добавить 300 тем').click()
    assert writes==['anchors','topics']
    for row in state['generations']:
        row['status']='completed';row['text']=anchors if row['kind']=='anchors' else topics
        row['line_count']=len(row['text'].splitlines());row['unique_count']=len(set(row['text'].splitlines()))
    state['topic_text']=topics
    page.reload()
    expect(page.get_by_label('Результат: Анкор-лист',exact=True)).to_have_value(anchors)
    expect(page.get_by_label('Результат: Генерация тем',exact=True)).to_have_value(topics)
    for kind,value in [('анкор-лист',anchors),('темы',topics)]:
        page.get_by_role('button',name='Скопировать '+kind).click()
        assert page.evaluate('window.copied')==value
    # Repeated generation retains the old list while queued, then appends a new batch.
    page.get_by_role('button',name='Добавить 300 тем').click()
    expect(page.get_by_label('Результат: Генерация тем',exact=True)).to_have_value(topics)
    more='\n'.join(f'Nové téma {i}' for i in range(300))
    row=state['generations'][0];row.update(status='completed',text=more,line_count=300,unique_count=300)
    state['topic_text']=topics+'\n'+more
    page.reload()
    expect(page.get_by_label('Результат: Генерация тем',exact=True)).to_have_value(state['topic_text'])
    page.get_by_role('button',name='Скопировать темы').click()
    assert page.evaluate('window.copied')==state['topic_text']
    cards=page.locator('.autoLbCard')
    assert abs(cards.nth(0).bounding_box()['width']-cards.nth(1).bounding_box()['width'])<2
    page.screenshot(path=str(ART/'desktop.png'),full_page=True)
    state['context']={**ctx,'main':'changed.example','main_url':'https://changed.example'}
    page.reload();expect(page.get_by_text('Параметры проекта изменились',exact=False).first).to_be_visible()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(ART/'mobile.png'),full_page=True)
    state['context']=None;state['context_error']='Укажите бренд проекта.'
    page.reload();expect(page.get_by_role('button',name='Сгенерировать анкор-лист')).to_be_disabled()
    assert not errors,errors
    browser.close()
print('PASS: split layout, independent generation, reload persistence, exact copy with repeats, changed Main notice, mobile, missing context')
