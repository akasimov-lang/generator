"""External login, project cache isolation and removal of local credential UI."""
import json
import os
from playwright.sync_api import sync_playwright, expect

site=lambda id:dict(id=id,name=id+'.test',brand='Example',brand_source='manual',base_url='https://'+id+'.test',publication_endpoint='',payload_mode='simple_page',editor_version='2',default_menu={'header':[],'footer':[]},menu_library=[],default_banners=[],cache_canon=id+'.test',cache_geo='DE',cache_language='de',cache_domains=[],project_status='working',is_test_project=False,has_menu=False,domains_count=1,internal_pages_count=0)
base=os.environ.get('VITE_TEST_URL','http://127.0.0.1:5174')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME'),headless=True)
    page=browser.new_page(viewport={'width':1280,'height':900})
    errors=[]; calls=[]; state={'user':'editor','revoked':False,'unavailable':False,'expired':False}
    page.on('pageerror',lambda e:errors.append(str(e)))
    def route(r):
        path=r.request.url.split('/api')[-1].split('?')[0]
        calls.append(path)
        username=state['user'];admin=username=='anton'
        user={'id':username,'username':username,'is_admin':admin,'is_active':True,'allowed_site_ids':None if admin else ([] if state['revoked'] else ['own'])}
        data=[];status=200
        if path=='/auth/login':
            body=r.request.post_data_json
            assert body['password']=='external-password'
            state['user']=body['username'];data={'access_token':'external-'+state['user']}
            if state['unavailable']:status=503;data={'detail':'Сервис авторизации временно недоступен.'}
        elif path=='/auth/me':
            if state['expired']:status=401;data={'detail':'Срок действия токена Webdev истёк.'}
            else:data=user
        elif path in ['/sites','/sites/cache/projects']:data=[site('own'),site('other')] if admin else ([] if state['revoked'] else [site('own')])
        elif path=='/me/favorite-sites':data={'site_ids':[]}
        elif path.startswith('/admin/'):data=[]
        r.fulfill(status=status,content_type='application/json',body=json.dumps(data))
    page.route('**/api/**',route)
    page.goto(base+'/sites')
    page.evaluate('sessionStorage.setItem("popup_permission_prompt_closed","true")')
    page.get_by_label('Логин',exact=True).fill('editor')
    page.get_by_label('Пароль',exact=True).fill('external-password')
    state['unavailable']=True
    page.get_by_role('button',name='Войти',exact=True).click()
    expect(page.get_by_text('Сервис авторизации временно недоступен.',exact=True)).to_be_visible()
    state['unavailable']=False
    page.get_by_role('button',name='Войти',exact=True).click()
    expect(page.get_by_label('Бренд own.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд other.test',exact=True)).to_have_count(0)
    # Seed both the legacy shared snapshot and a stale user snapshot with another user's project.
    page.evaluate('''async projects => {
      const db = await new Promise((resolve,reject) => { const r=indexedDB.open('pagepilot-projects',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error); });
      await new Promise((resolve,reject)=>{const tx=db.transaction('snapshots','readwrite'); for(const key of ['shared-projects-v1','webdev-projects-v2:editor'])tx.objectStore('snapshots').put({projects,updatedAt:'2026-09-17T00:00:00Z'},key);tx.oncomplete=resolve;tx.onerror=reject;});db.close();
    }''',[site('own'),site('other')])
    calls.clear();page.reload()
    expect(page.get_by_label('Бренд own.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд other.test',exact=True)).to_have_count(0)
    assert '/sites' not in calls
    page.goto(base+'/settings')
    expect(page.get_by_text('Вход и пароль управляются в Webdev. Администратор панели — anton.',exact=True)).to_be_visible()
    expect(page.locator('input[type=password]')).to_have_count(0)
    assert '/users' not in calls
    page.get_by_title('Выйти',exact=True).click()
    page.get_by_label('Логин',exact=True).fill('anton');page.get_by_label('Пароль',exact=True).fill('external-password')
    page.get_by_role('button',name='Войти',exact=True).click()
    expect(page.get_by_text('Вход и пароль управляются в Webdev. Администратор панели — anton.',exact=True)).to_be_visible()
    expect(page.locator('input[type=password]')).to_have_count(0)
    page.goto(base+'/sites')
    expect(page.get_by_label('Бренд other.test',exact=True)).to_be_visible()
    page.get_by_title('Выйти',exact=True).click()
    page.get_by_label('Логин',exact=True).fill('editor');page.get_by_label('Пароль',exact=True).fill('external-password')
    page.get_by_role('button',name='Войти',exact=True).click()
    expect(page.get_by_label('Бренд own.test',exact=True)).to_be_visible()
    expect(page.get_by_label('Бренд other.test',exact=True)).to_have_count(0)
    state['revoked']=True;page.evaluate('window.dispatchEvent(new Event("focus"))')
    expect(page.get_by_label('Бренд own.test',exact=True)).to_have_count(0)
    state['expired']=True;page.evaluate('window.dispatchEvent(new Event("focus"))')
    expect(page.get_by_role('button',name='Войти',exact=True)).to_be_visible()
    expect(page.get_by_text('Срок действия токена истёк. Войдите заново, чтобы получить новый токен.',exact=True)).to_be_visible()
    assert page.evaluate('localStorage.getItem("admin_token")') is None
    assert not errors,errors
    browser.close()
    print('PASS: external login, unavailable auth, user/admin isolation, revoked rights, expired-token logout, no local password/user controls.')
