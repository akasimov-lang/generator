"""Reviewed, reversible template repair for the explicitly requested Pelican site."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import argparse
import hashlib
import json

from app import models
from app.project_network import Remote, network_lock, get_settings
from app.maintenance_reports import upsert

SITE = '0c64f0fc-3617-4f60-a576-7e0abc391fb7'
REPORT = '28fd2a61-a7cc-48dd-995d-f775ca1f5583'
KEY = 'site-template-repair:' + REPORT
NAME = 'Pelican · Шаблон внутренних страниц, меню и кнопки · alldaybabyla.com'
ASSETS = Path(__file__).parent / 'data' / 'site_repairs'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fields(project):
    header = next(row['data'] for row in project['shortcodes'] if row['name'] == 'header.hbs')
    return {'header': header, 'layout': project['layout'], 'styles': project['styles']}


def proposed(project):
    before = fields(project)
    header = before['header']
    if 'pp-main-menu' in header:
        raise ValueError('Исправление меню уже присутствует; повторная подготовка не нужна.')
    if '<details class="mobile-menu"' not in header or header.count('<div class="account-actions">') != 1:
        raise ValueError('Шаблон шапки изменён; требуется повторная проверка.')
    header = header.split('<details class="mobile-menu"', 1)[0]
    header = header.replace('href="./index.html"', 'href="/"')
    header = header.replace('<div class="account-actions">', (ASSETS / 'allday-navigation.hbs').read_text() + '\n<div class="account-actions">')
    header += '\n</header>\n'
    layout = before['layout']
    if layout.count('<body>') != 1:
        raise ValueError('Тег body изменён; требуется повторная проверка.')
    layout = layout.replace('<body>', '<body data-pilot-page="{{page.slug}}">')
    layout = layout.replace('content="/uploads/img/webp/logo-mostbet.webp"', 'content="/assets/logo.webp"')
    return {**before, 'header': header, 'layout': layout,
            'styles': before['styles'] + '\n' + (ASSETS / 'allday-navigation.css').read_text()}


def report(db, status, **details):
    return upsert(db, REPORT, NAME, 'anton', [SITE], [{'site_id': SITE, 'status': status, **details}],
                  status='completed' if status == 'completed' else 'running' if status in {'pending','running'} else 'partial')


def prepare(db):
    site = db.get(models.Site, SITE)
    report(db, 'pending', planned={'changes': ['Меню Header между логотипом и кнопками', 'Компактный бургер на мобильном',
        'Ширина и отступы внутренних статей', 'Стили кнопок в контенте'], 'site': 'alldaybabyla.com'})
    with network_lock(db, SITE), Remote(db, site) as remote:
        project = remote.project()
        if project['settings']['canon'] != 'alldaybabyla.com':
            raise ValueError('Main проекта изменён; подготовка остановлена.')
        existing = db.get(models.AutoReglueConfig, KEY)
        if existing:
            return {'status': existing.value['status'], 'report_id': REPORT}
        before, after = fields(project), proposed(project)
        db.add(models.AutoReglueConfig(key=KEY, value={'site_id': SITE, 'status': 'prepared', 'created_at': stamp(),
            'before': before, 'after': after, 'receipts': [], 'menu_before': deepcopy(project['data']['menu'])}))
        db.commit()
        report(db, 'pending', before={'template_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()},
               comment='Подготовлены шаблон, стили и меню. Исходные файлы сохранены для восстановления.')
    return {'status': 'prepared', 'report_id': REPORT}


def apply(db):
    site = db.get(models.Site, SITE)
    with network_lock(db, SITE), Remote(db, site) as remote:
        ledger = db.get(models.AutoReglueConfig, KEY)
        if not ledger:
            raise ValueError('Сначала подготовьте исправление.')
        state = deepcopy(ledger.value)
        project = remote.project()
        if project['settings']['canon'] != 'alldaybabyla.com':
            raise ValueError('Main проекта изменён; запись остановлена.')
        if fields(project) == state['after']:
            return {'status': 'already_applied', 'report_id': REPORT}
        remote.client.headers['Accept'] = 'application/json;v=2'
        report(db, 'running', comment='Сохраняем шаблон, стили и меню с проверкой каждого файла.')
        for field, endpoint in [('styles','/projects/update-style'), ('layout','/projects/update-layout'), ('header','/projects/shortcode')]:
            current = fields(remote.project())[field]
            desired = state['after'][field]
            if current == desired: continue
            if current != state['before'][field]:
                raise ValueError(f'Файл {field} изменён после подготовки; чужие изменения сохранены.')
            if any(r['field'] == field and r['status'] == 'sending' for r in state['receipts']):
                raise ValueError(f'Ответ записи {field} не подтверждён; повторная отправка остановлена.')
            actor = get_settings().project_cache_username
            payload = {'project': site.name, 'contents': desired, 'username': actor}
            if field != 'styles':
                payload['contents'] = quote(desired, safe=";/?:@&=+$,-_.!~*'()#")
                payload['filename'] = 'layout' if field == 'layout' else 'header'
            if field == 'header':
                payload.pop('username'); payload['initiator'] = actor
            receipt = {'field': field, 'status': 'sending', 'started_at': stamp()}
            state['receipts'].append(receipt); state['status'] = 'applying'
            ledger.value = deepcopy(state); db.commit()
            code, response = remote.request('POST', endpoint, payload)
            receipt.update(http_status=code, confirmed_at=stamp())
            receipt['status'] = 'confirmed' if fields(remote.project())[field] == desired else 'unknown'
            ledger.value = deepcopy(state); db.commit()
            if receipt['status'] != 'confirmed':
                raise ValueError(f'Сохранение {field} пока не подтверждено.')
        final = remote.project()
        if fields(final) != state['after']:
            raise ValueError('Не все файлы подтверждены.')
        state.update(status='applied', applied_at=stamp())
        ledger.value = deepcopy(state); db.commit()
        report(db, 'running', after={'saved_at': stamp(), 'fields': list(state['after'])},
               comment='Шапка, шаблон и стили сохранены в Webdev. Проверяем публичные страницы.')
    return {'status': 'applied', 'report_id': REPORT}


def main():
    from app.db import SessionLocal
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            if args.prepare: print(json.dumps(prepare(db)))
            if args.apply: print(json.dumps(apply(db)))
        except Exception as error:
            db.rollback()
            report(db, 'partial', comment=str(error)[:500])
            raise


if __name__ == '__main__':
    main()
