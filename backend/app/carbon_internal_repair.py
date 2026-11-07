"""Point repair: match all CarbonCraftworks internal articles to the home width."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from urllib.parse import quote

from app import models
from app.project_network import Remote, get_settings, network_lock

SITE = '8b04f1e3-bd3a-444e-8cd6-daa43aac9026'
KEY = 'site-template-repair:carboncraft-internal-2026-11-07'
ASSET = Path(__file__).parent / 'data' / 'site_repairs' / 'carbon-internal-pages.css'
MARKER = 'PagePilot: CarbonCraftworks internal article layout, 2026-11-07'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fields(project):
    return {name: project[name] for name in ('layout', 'styles')}


def proposed(project, css=None):
    before = fields(project)
    if MARKER in before['styles'] or 'data-cc-page=' in before['layout']:
        raise ValueError('Исправление внутренних страниц уже присутствует.')
    if before['layout'].count('<body>') != 1 or '{{{renderedBlocks}}}' not in before['layout']:
        raise ValueError('Общий шаблон изменился; требуется повторная проверка.')
    if not any(page.get('slug') == '/prehled-bonusu/' for page in project.get('data', {}).get('pages', [])):
        raise ValueError('Внутренняя страница не найдена в исходнике.')
    return {'layout': before['layout'].replace('<body>', '<body data-cc-page="{{page.slug}}">'),
            'styles': before['styles'] + '\n' + (css if css is not None else ASSET.read_text())}


def apply(db, css=None):
    site = db.get(models.Site, SITE)
    with network_lock(db, SITE), Remote(db, site) as remote:
        project = remote.project()
        if (project.get('settings') or {}).get('canon') != 'carboncraftworks.com':
            raise ValueError('Main изменился; запись остановлена.')
        ledger = db.get(models.AutoReglueConfig, KEY)
        if not ledger:
            state = {'site_id': SITE, 'status': 'prepared', 'created_at': stamp(),
                     'before': fields(project), 'after': proposed(project, css), 'receipts': [],
                     'protected': {key: deepcopy(project.get(key)) for key in ('data', 'settings', 'head', 'shortcodes')},
                     'description': 'Все внутренние страницы: контейнер текста 960 px по центру, адаптивные отступы, фирменные кнопки, безопасная ширина изображений и таблиц.'}
            ledger = models.AutoReglueConfig(key=KEY, value=state)
            db.add(ledger); db.commit()
        state = deepcopy(ledger.value)
        remote.client.headers['Accept'] = 'application/json;v=2'
        for field, endpoint in [('styles', '/projects/update-style'), ('layout', '/projects/update-layout')]:
            current = fields(remote.project())[field]
            desired = state['after'][field]
            previous = next((receipt for receipt in state['receipts'] if receipt['field'] == field), None)
            if current == desired:
                if previous and previous.get('status') != 'confirmed':
                    previous.update(status='confirmed', confirmed_at=stamp(), reconciled=True)
                    ledger.value = deepcopy(state); db.commit()
                continue
            if current != state['before'][field]:
                raise ValueError('Источник изменился после подготовки: ' + field)
            if previous:
                raise ValueError('Предыдущая отправка требует проверки: ' + field)
            payload = {'project': site.name, 'contents': desired, 'username': get_settings().project_cache_username}
            if field == 'layout':
                payload.update(contents=quote(desired, safe=";/?:@&=+$,-_.!~*'()#"), filename='layout')
            receipt = {'field': field, 'status': 'sending', 'started_at': stamp(),
                       'sha256': hashlib.sha256(desired.encode()).hexdigest(),
                       'message': state['description'] if field == 'styles' else 'Общий шаблон применяет оформление ко всем внутренним страницам, включая новые.'}
            state['receipts'].append(receipt); state['status'] = 'applying'
            ledger.value = deepcopy(state); db.commit()
            code, _ = remote.request('POST', endpoint, payload)
            receipt.update(http_status=code, confirmed_at=stamp(),
                           status='confirmed' if fields(remote.project())[field] == desired else 'unknown')
            ledger.value = deepcopy(state); db.commit()
            if receipt['status'] != 'confirmed':
                raise ValueError('Запись не подтверждена: ' + field)
        final = remote.project()
        if fields(final) != state['after']:
            raise ValueError('Не все изменения подтверждены.')
        if any(final.get(key) != value for key, value in state['protected'].items()):
            raise ValueError('Данные, меню, SEO или шорткоды изменились во время записи; требуется сверка.')
        state.update(status='applied', applied_at=stamp())
        ledger.value = deepcopy(state); db.commit()
        return {'status': 'applied', 'project': site.name,
                'pages': [page['slug'] for page in final['data']['pages'] if page.get('slug') not in {'', '/'}]}
