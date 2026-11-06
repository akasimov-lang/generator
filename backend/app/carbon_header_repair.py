"""Point repair requested in chat: show the saved Czech header menu."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from app import models
from app.project_network import Remote, network_lock, get_settings

SITE = '8b04f1e3-bd3a-444e-8cd6-daa43aac9026'
KEY = 'site-menu-repair:carboncraftworks-header-2026-11-07'
ASSETS = Path(__file__).parent / 'data' / 'site_repairs'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fields(project):
    return {'header': next(s['data'] for s in project['shortcodes'] if s['name']=='header.hbs'), 'styles': project['styles']}


def proposed(project):
    before=fields(project)
    if 'cc-header' in before['header']:
        raise ValueError('Меню уже подключено.')
    if before['header'].count('<header>')!=1 or before['header'].count('</header>')!=1:
        raise ValueError('Изменился шаблон шапки.')
    menu=project['data'].get('menu',{}).get('header',[])
    pages={p.get('slug') for p in project['data'].get('pages',[])}
    if not menu or any(item.get('slug') not in pages for item in menu):
        raise ValueError('Для пунктов меню не подтверждены опубликованные страницы.')
    header=before['header'].replace('<header>','<header class="cc-header">')
    header=header.replace('<a href="#uvod"','<a class="cc-brand" href="/"',1)
    header=header.replace('</header>',(ASSETS/'carbon-navigation.hbs').read_text()+'</header>')
    return {'header':header,'styles':before['styles']+'\n'+(ASSETS/'carbon-navigation.css').read_text()}


def apply(db):
    site=db.get(models.Site,SITE)
    with network_lock(db,SITE), Remote(db,site) as remote:
        project=remote.project()
        ledger=db.get(models.AutoReglueConfig,KEY)
        if not ledger:
            state={'site_id':SITE,'status':'prepared','created_at':stamp(),'before':fields(project),'after':proposed(project),
                   'menu_before':deepcopy(project['data']['menu']),'receipts':[],
                   'description':'Меню из шести внутренних страниц в шапке: горизонтальное на компьютере, компактное мобильное; подписи на чешском.'}
            ledger=models.AutoReglueConfig(key=KEY,value=state);db.add(ledger);db.commit()
        state=deepcopy(ledger.value)
        remote.client.headers['Accept']='application/json;v=2'
        for field,endpoint in [('styles','/projects/update-style'),('header','/projects/shortcode')]:
            current=fields(remote.project())[field]
            desired=state['after'][field]
            if current==desired:continue
            if current!=state['before'][field]:raise ValueError('Источник изменился: '+field)
            if any(r['field']==field for r in state['receipts']):raise ValueError('Требуется проверить предыдущую запись: '+field)
            receipt={'field':field,'status':'sending','started_at':stamp(),
                     'message':'Добавлены стили адаптивного меню в шапке.' if field=='styles' else state['description']}
            state['receipts'].append(receipt);state['status']='applying';ledger.value=deepcopy(state);db.commit()
            payload={'project':site.name,'contents':desired,'username':get_settings().project_cache_username}
            if field=='header':
                payload={'project':site.name,'filename':'header','contents':quote(desired,safe=";/?:@&=+$,-_.!~*'()#"),'initiator':get_settings().project_cache_username}
            code,_=remote.request('POST',endpoint,payload)
            receipt.update(http_status=code,confirmed_at=stamp(),status='confirmed' if fields(remote.project())[field]==desired else 'unknown')
            ledger.value=deepcopy(state);db.commit()
            if receipt['status']!='confirmed':raise ValueError('Запись не подтверждена: '+field)
        final=remote.project()
        if fields(final)!=state['after'] or final['data']['menu']!=state['menu_before']:
            raise ValueError('Итоговая проверка шаблона/меню не пройдена.')
        state.update(status='applied',applied_at=stamp());ledger.value=state;db.commit()
        return {'status':'applied','project':site.name,'main':final['settings']['canon'],'links':len(state['menu_before']['header'])}


if __name__=='__main__':
    import json
    from app.db import SessionLocal
    with SessionLocal() as db:print(json.dumps(apply(db),ensure_ascii=False))
