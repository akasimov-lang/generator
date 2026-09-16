"""Shared brand column/edit/filter, using mocked API only."""
import json
import os
from playwright.sync_api import sync_playwright, expect
site=dict(id='brand-site',name='project.test',brand='Mostbet',brand_source='detected',base_url='https://main.test',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon='main.test',cache_geo='AZ',cache_language='az',homepage_title='Mostbet Casino',internal_pages_count=0,domains_count=1,cache_domains=['main.test'],main_domain_history=[],x_default_history=[],alternate_domain_history=[],project_status='working',is_test_project=False,has_menu=False)
variants=[dict(site,id='variant-'+str(i),name='variant-'+str(i)+'.test',cache_geo=geo) for i,geo in enumerate(['AZ_AZ','AZ-AZ','en-US','UA'])]
variants[0]['project_status']='mass_actions'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME'), headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1000})
    errors=[]; writes=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def route(r):
        path=r.request.url.split('/api')[-1].split('?')[0]
        data=[]
        if path=='/auth/me':data={'id':'user','username':'user','is_admin':False,'is_active':True}
        elif path in ['/sites','/sites/cache/projects']:data=[site,*variants]
        elif path=='/dashboard':data={}
        elif '/favorite-sites' in path:data={'site_ids':[]}
        elif path=='/sites/brand-site/brand':
            writes.append(r.request.post_data_json)
            site['brand']=writes[-1]['brand'] or 'Общие ключи'; site['brand_source']='manual'; data=site
        r.fulfill(status=200,content_type='application/json',body=json.dumps(data))
    page.route('**/api/**',route)
    base=os.environ.get('VITE_TEST_URL','http://127.0.0.1:5174')
    page.goto(base)
    page.evaluate('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
    page.evaluate('localStorage.setItem("sites-table-preferences:user",JSON.stringify({geoFilter:"AZ_AZ",statusFilters:["test","working","not_in_focus","duplicate"]}))')
    page.goto(base+'/sites')
    mass=page.locator('.siteCacheStats button').filter(has_text='Массовые действия')
    expect(mass).to_contain_text('1')
    expect(page.locator('.siteCacheStats').get_by_text('Тестовые',exact=True)).to_have_count(0)
    mass.click()
    expect(page.get_by_label('Бренд variant-0.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд project.test',exact=True)).to_have_count(0)
    mass.click()
    geo=page.get_by_label('Фильтр сайтов по GEO')
    expect(geo).to_contain_text('AZ')
    geo.click()
    search=page.get_by_role('textbox',name='Введите GEO',exact=True)
    expect(search).to_be_focused()
    expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(4)
    search.fill('u')
    expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(2)
    expect(page.get_by_role('listbox').get_by_role('option').first).to_contain_text('UA')
    search.fill('zz')
    expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(0)
    search.press('Escape')
    expect(page.get_by_label('Бренд variant-0.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд variant-1.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд variant-2.test',exact=True)).to_have_count(0)
    geo.focus()
    geo.press('u')
    search.fill('us')
    search.press('Enter')
    expect(page.get_by_label('Бренд variant-2.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд project.test',exact=True)).to_have_count(0)
    geo.click()
    search.fill('a')
    expect(page.get_by_role('listbox').get_by_role('option')).to_have_count(1)
    search.press('Enter')
    field=page.get_by_label('Бренд project.test',exact=True)
    expect(field).to_have_value('Mostbet')
    assert not writes
    field.fill('My Brand')
    assert not writes
    field.press('Enter')
    expect(field).to_have_value('My Brand')
    expect(page.get_by_role('button',name='Сохранить бренд project.test',exact=True)).to_have_count(0)
    page.get_by_label('Фильтр сайтов по бренду').fill('My Brand')
    expect(field).to_be_visible()
    page.get_by_label('Фильтр сайтов по бренду').fill('Mostbet')
    expect(field).to_have_count(0)
    assert writes==[{'brand':'My Brand'}]
    assert not errors,errors
    browser.close()
print('PASS: shared brand visible/editable to regular user; persisted edit and actual brand filter; no automatic writes; GEO aliases grouped and saved selection normalized.')
