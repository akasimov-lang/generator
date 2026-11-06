"""Reviewed, reversible template repair for the explicitly requested Pelican site."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import argparse
import hashlib
import html
import json
import re

from app import models
from app.project_network import Remote, network_lock, get_settings
from app.maintenance_reports import upsert

SITE = 'b76715b0-6568-4bcf-ac96-bce6edf03f7d'
REPORT = 'ba84729c-4909-5064-9e57-eb6e02043fb0'
KEY = 'site-menu-repair:' + REPORT
NAME = 'Pelican · Меню в шапке и внутренние страницы · pelicancasinop.pl'
ASSETS = Path(__file__).parent / 'data' / 'site_repairs'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fields(project):
    header = next(row['data'] for row in project['shortcodes'] if row['name'] == 'header.hbs')
    footer = next(row['data'] for row in project['shortcodes'] if row['name'] == 'footer.hbs')
    return {'header': header, 'footer': footer, 'layout': project['layout'], 'styles': project['styles']}


def proposed(project):
    before = fields(project)
    header = before['header']
    if 'pp-main-menu' in header:
        raise ValueError('Исправление меню уже присутствует; повторная подготовка не нужна.')
    pattern = r'<nav\b[^>]*class="top-nav"[^>]*>.*?</nav>'
    if len(re.findall(pattern, header, flags=re.S)) != 1 or header.count('<div class="actions">') != 1:
        raise ValueError('Шаблон шапки изменён; требуется повторная проверка.')
    navigation = (ASSETS / 'allday-navigation.hbs').read_text()
    navigation += '\n<noscript><style>.pp-main-menu{display:block!important}.pp-menu-toggle{display:none!important}</style></noscript>'
    navigation += '\n{{#if amp}}<style>.pp-main-menu{display:block!important}.pp-menu-toggle{display:none!important}</style>{{/if}}'
    header = re.sub(pattern, lambda _: navigation, header, count=1, flags=re.S)
    header = header.replace('href="./index.html"', 'href="/"')
    layout = before['layout']
    if layout.count('<body>') != 1:
        raise ValueError('Тег body изменён; требуется повторная проверка.')
    layout = layout.replace('<body>', '<body data-pilot-page="{{page.slug}}">')
    layout = layout.replace('content="/uploads/img/webp/logo-mostbet.webp"', 'content="/assets/pelican-logo.webp"')
    footer = before['footer'].replace('src="assets/', 'src="/assets/').replace('href="./index.html"', 'href="/"')
    return {**before, 'header': header, 'footer': footer, 'layout': layout,
            'styles': before['styles'] + '\n' + (ASSETS / 'pelicancasinop-navigation.css').read_text()}


def clean_page(page):
    """Remove introductory labels, retaining their text and unrelated sections."""
    from app.page_generation_structure import is_intro_heading
    content = deepcopy(page['content'])
    changes = {'intro_removed': 0, 'translated_headings': 0}
    if not str(page.get('slug') or '').strip('/'):
        return content, changes
    removed_anchors = set()
    kept = []
    for block in content['blocks']:
        if block.get('type') != 'header':
            kept.append(block)
            continue
        data = block.get('data') or {}
        text = data.get('text', '')
        label = html.unescape(re.sub(r'<[^>]*>', '', text)).strip()
        if data.get('level') != 1:
            if is_intro_heading(text) or label.casefold().startswith('wstęp do '):
                removed_anchors.update(re.findall(r'id="([^"]+)"', text))
                changes['intro_removed'] += 1
                continue
            if label.startswith('Methodik:'):
                data['text'] = text.replace('Methodik:', 'Metodyka:', 1)
                changes['translated_headings'] += 1
        kept.append(block)
    for block in kept:
        if block.get('pagepilot_toc') and block.get('type') == 'list':
            block['data']['items'] = [item.replace('Methodik:', 'Metodyka:')
                for item in block['data']['items']
                if not any(f'href="#{anchor}"' in item for anchor in removed_anchors)]
    content['blocks'] = kept
    return content, changes


def report(db, status, **details):
    return upsert(db, REPORT, NAME, 'anton', [SITE], [{'site_id': SITE, 'status': status, **details}],
                  status='completed' if status == 'completed' else 'running' if status in {'pending','running'} else 'partial')


def prepare(db):
    site = db.get(models.Site, SITE)
    report(db, 'pending', planned={'changes': ['Меню Header между логотипом и кнопками', 'Компактный бургер на мобильном',
        'Ширина и отступы внутренних статей', 'Стили кнопок в контенте',
        'Исправление путей изображений футера', 'Удаление заголовков Intro с сохранением текста'], 'site': 'pelicancasinop.pl'})
    with network_lock(db, SITE), Remote(db, site) as remote:
        project = remote.project()
        if project['settings']['canon'] != 'pelicancasinop.pl':
            raise ValueError('Main проекта изменён; подготовка остановлена.')
        existing = db.get(models.AutoReglueConfig, KEY)
        if existing and existing.value.get('after'):
            return {'status': existing.value['status'], 'report_id': REPORT}
        if existing and fields(project) != fields(existing.value['project_before']):
            raise ValueError('Шаблон изменён после исходного снимка; подготовка остановлена.')
        before, after = fields(project), proposed(project)
        state = {**(existing.value if existing else {}), 'site_id': SITE, 'status': 'prepared', 'created_at': stamp(),
            'before': before, 'after': after, 'receipts': [], 'menu_before': deepcopy(project['data']['menu'])}
        if existing: existing.value = state
        else: db.add(models.AutoReglueConfig(key=KEY, value=state))
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
        if project['settings']['canon'] != 'pelicancasinop.pl':
            raise ValueError('Main проекта изменён; запись остановлена.')
        if fields(project) == state['after']:
            return {'status': 'already_applied', 'report_id': REPORT}
        remote.client.headers['Accept'] = 'application/json;v=2'
        report(db, 'running', comment='Сохраняем шаблон, стили и меню с проверкой каждого файла.')
        for field, endpoint in [('styles','/projects/update-style'), ('layout','/projects/update-layout'),
                                ('footer','/projects/shortcode'), ('header','/projects/shortcode')]:
            current = fields(remote.project())[field]
            desired = state['after'][field]
            if current == desired: continue
            if current != state['before'][field]:
                raise ValueError(f'Файл {field} изменён после подготовки; чужие изменения сохранены.')
            if any(r['field'] == field and r['status'] in {'sending', 'unknown'} for r in state['receipts']):
                raise ValueError(f'Ответ записи {field} не подтверждён; повторная отправка остановлена.')
            actor = get_settings().project_cache_username
            payload = {'project': site.name, 'contents': desired, 'username': actor}
            if field != 'styles':
                payload['contents'] = quote(desired, safe=";/?:@&=+$,-_.!~*'()#")
                payload['filename'] = field
            if field in {'header', 'footer'}:
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
        if final['data'].get('menu') != state['menu_before']:
            raise ValueError('Структура меню изменилась во время сохранения.')
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
