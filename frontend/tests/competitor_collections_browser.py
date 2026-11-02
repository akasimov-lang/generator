"""Saving HTML is separate from generating a template."""
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

DIST=Path(os.environ.get('PAGEPILOT_DIST',Path(__file__).resolve().parents[1]/'dist'))
identity={'domain':'competitor.test','title':'Competitor bonus guide','url':'https://competitor.test/'}
rows=[dict(id='old',brand='Pelican',geo='PL',language='pl',status='failed',phase='Error',revision=1,
    created_at='2026-10-20',updated_at='2026-10-20',has_html=False,competitors=[identity]),
    dict(id='ready',brand='Pin-Up',geo='AZ',language='az',status='ready',phase='Ready',revision=1,
    created_at='2026-10-04',updated_at='2026-10-04',has_html=True,competitors=[])]
drafts=[];saved=[];generation=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
    def route(r):
        path=urlparse(r.request.url).path
        if not path.startswith('/api/'):
            asset=DIST/path.lstrip('/')
            if not asset.is_file():asset=DIST/'index.html'
            r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes());return
        path=path[4:];data=[];method=r.request.method
        if path=='/auth/me':data={'id':'admin','username':'admin','is_admin':True,'is_active':True}
        elif path=='/me/favorite-sites':data={'site_ids':[]}
        elif path=='/site-templates/knowledge':data={'count':0,'sources':[],'scopes':[]}
        elif path=='/site-templates':
            if method=='POST':generation.append(r.request.post_data_json)
            data=rows
        elif path.startswith('/site-templates/source-drafts'):
            if method=='GET':data=drafts
            else:
                value=r.request.post_data_json
                data={**value,'id':drafts[0]['id'] if drafts else str(uuid4()),'revision':value['revision']+1,'capture':{'status':'google_ready'},'suggested_brand':'Pelican'}
                drafts[:]=[data]
        elif path=='/site-templates/knowledge/save-drafts':
            saved.append(r.request.post_data_json)
            rows.insert(0,{**rows[0],'id':'new','status':'sources_ready','created_at':'2026-10-21'})
            drafts.clear();data={'saved':1,'duplicates':0}
        r.fulfill(content_type='application/json',body=json.dumps(data))
    page.route('**/*',route);page.goto('http://localhost/template-generator')
    expect(page.get_by_role('heading',name='Конкуренты собраны',exact=True)).to_be_visible()
    generated=page.locator('.tg-generated-templates')
    expect(generated.locator('.tg-row')).to_have_count(1)
    expect(generated).to_contain_text('Pin-Up')
    expect(page.locator('.tg-row-competitors').first).to_contain_text('competitor.test')
    assert page.locator('.tg-row-competitors small').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')<=12
    page.get_by_role('button',name='Загрузить HTML конкурентов',exact=True).click()
    expect(page.get_by_role('button',name='Назад',exact=True)).to_be_visible()
    geo=page.get_by_role('combobox',name='ГЕО',exact=True);geo.fill('PL');geo.press('Enter')
    html='<html><title>Competitor bonus guide</title><body><p>'+('Useful details. '*40)+'</p></body></html>'
    page.get_by_role('textbox',name='HTML конкурента 1',exact=True).fill(html)
    expect(page.locator('.tg-source-field [role=status]')).to_have_text('Сохранено')
    expect(page.get_by_role('combobox',name='Бренд',exact=True)).to_have_value('Pelican')
    save=page.get_by_role('button',name='Сохранить конкурентов',exact=True)
    expect(save).to_be_enabled()  # Saving does not require any Gemini provider.
    save.click()
    expect(page.get_by_role('heading',name='Конкуренты собраны',exact=True)).to_be_visible()
    expect(page.locator('.tg-collection-group .tg-row')).to_have_count(2)
    assert len(saved)==1 and saved[0]['brand']=='Pelican' and not generation
    expect(generated.locator('.tg-row')).to_have_count(1)
    assert not errors,errors
    browser.close()
print('PASS: competitors/templates separated, compact domain/title, HTML saved without Gemini or generation, collection appears in list')
