"""Confirmed template, showcase and menu work used by weekly reports."""
from sqlalchemy import select
from app import models
from app.reglue_history import utc


def in_period(value, start, end):
    at = utc(value)
    return bool(at and start <= at <= end)


def template_event(edit):
    if edit.status != 'confirmed':
        return None
    before = (edit.before_page or {}).get('node', edit.before_page)
    after = (edit.after_page or {}).get('node', edit.after_page)
    if not isinstance(after, dict) or not isinstance(after.get('data'), str) or not after.get('name'):
        return None
    if isinstance(before, dict) and before.get('data') == after['data']:
        return None
    name = after['name']
    showcase = 'casino' in name.lower() or 'pp-standard-card' in after['data']
    categories = ['showcase'] if showcase else ['template']
    if any(word in name.lower() for word in ('header', 'footer', 'menu', 'navigation')):
        categories.append('menu')
    return {'id': edit.id, 'kind': 'layout', 'categories': categories,
            'label': 'Вёрстка витрины' if showcase else 'Правка шаблона и меню' if 'menu' in categories else 'Правка шаблона',
            'at': utc(edit.updated_at).isoformat(), 'message': 'Обновлён шаблон: ' + name,
            'source': 'confirmed_page_edit'}


def ledger_events(ledger, start, end):
    value = ledger.value or {}
    receipts = list(value.get('receipts') or [])
    if value.get('contrast_receipt'):
        receipts.append({**value['contrast_receipt'], 'field': 'contrast'})
    showcase = ledger.key.startswith('showcase-')
    events = []
    for index, receipt in enumerate(receipts):
        if receipt.get('status') != 'confirmed':
            continue
        at = next((receipt.get(k) for k in ('confirmed_at', 'verified_at', 'checked_at', 'at') if receipt.get(k)), value.get('applied_at'))
        if not in_period(at, start, end):
            continue
        field = receipt.get('field') or receipt.get('kind') or ''
        if field in {'casinos', 'logo'}:
            label = 'Логотип витрины' if field == 'logo' else 'Данные карточек витрины'
            kind, categories = 'showcase', []
            message = ('Загружен логотип: ' + str(receipt.get('brand') or 'бренд')) if field == 'logo' else 'Обновлены данные карточек витрины.'
        elif field in {'styles', 'layout', 'header', 'footer', 'menu_click_fix', 'contrast', 'shortcode'} or field.endswith('.hbs'):
            kind = 'layout'
            categories = ['showcase'] if showcase else ['template']
            if field in {'header', 'footer', 'menu_click_fix'}:
                categories.append('menu')
            label = 'Вёрстка витрины' if showcase else 'Правка меню' if 'menu' in categories else 'Правка шаблона'
            message = {'styles': 'Обновлены стили внутренних страниц и кнопок.',
                       'layout': 'Исправлен общий шаблон страниц.',
                       'header': 'Обновлена шапка и вывод меню на компьютере и телефоне.',
                       'footer': 'Исправлен шаблон подвала и адреса ресурсов на внутренних страницах.',
                       'menu_click_fix': 'Исправлено открытие пунктов меню.',
                       'contrast': 'Улучшены контраст и читаемость карточек.',
                       'shortcode': 'Обновлены оформление и вывод карточек витрины.'}.get(field, 'Обновлён шаблон: ' + field)
        else:
            continue
        event = {'id': ledger.key + ':' + str(index), 'kind': kind, 'categories': categories,
                 'label': label, 'at': utc(at).isoformat(), 'message': message,
                 'source': 'confirmed_native_receipts'}
        if ledger.key.startswith(('site-template-repair:', 'site-menu-repair:')):
            event['report_url'] = '/auto-reglue/pilot/report?maintenance=' + ledger.key.split(':', 1)[1]
        events.append(event)
    return events


def source_ledgers(db):
    return list(db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.like('site-%repair:%') |
        models.AutoReglueConfig.key.like('showcase-%'))))


def source_menu_logs(db, end):
    return list(db.scalars(select(models.PublicationLog).where(
        models.PublicationLog.request_payload['action'].as_string() == 'menu_sync',
        models.PublicationLog.created_at <= end).order_by(models.PublicationLog.created_at, models.PublicationLog.id)))


def menu_events(db, project, start, end):
    logs = db.info.get('state_report_menu_logs')
    if logs is None:
        logs = source_menu_logs(db, end)
    events, previous = [], {}
    for log in logs:
        payload = log.request_payload or {}
        if payload.get('action') != 'menu_sync' or payload.get('project_name') != project:
            continue
        if not log.response_status or not 200 <= log.response_status < 300 or log.error_message:
            continue
        menu = payload.get('type') or 'header'
        items = payload.get('list')
        if not isinstance(items, list):
            continue
        unchanged = menu in previous and previous[menu] == items
        previous[menu] = items
        if unchanged or not in_period(log.created_at, start, end):
            continue
        def names(nodes):
            result = []
            for item in nodes:
                if not isinstance(item, dict):
                    continue
                title = item.get('title') or item.get('name') or item.get('label')
                if title:
                    result.append(str(title))
                result.extend(names(item.get('children') or []))
            return result
        titles = names(items)
        events.append({'id': log.id, 'kind': 'menu', 'label': 'Обновлены пункты меню · ' + menu.title(),
                       'at': utc(log.created_at).isoformat(), 'message': 'Опубликовано меню: ' + (', '.join(titles) if titles else 'пустой список'),
                       'menu_type': menu, 'menu_items': len(titles), 'source': 'successful_menu_publication'})
    return events


def work_flags(events):
    categories = {category for event in events for category in event.get('categories', [])}
    return {'layout_work': any(e['kind'] == 'layout' for e in events),
            'showcase_layout_work': 'showcase' in categories,
            'template_work': 'template' in categories,
            'menu_work': 'menu' in categories or any(e['kind'] == 'menu' for e in events),
            'showcase_work': 'showcase' in categories or any(e['kind'] == 'showcase' for e in events)}
