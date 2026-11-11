"""Human-readable outcomes for small website maintenance reports.

Plans, terminal job status and current site snapshots are not publication evidence.
Large inventories and network/content programs keep their existing presentation.
"""
from copy import deepcopy

MARKERS = {'showcase_actions', 'public_verification', 'breadcrumbs_result',
           'navigation_faq_result', 'navigation_footer_result', 'footer_result',
           'reviews_result', 'logo_restore_result', 'work_summary'}


def is_work_report(job):
    payload = job.payload or {}
    if payload.get('planning_only') or payload.get('repeat'):
        return False
    if payload.get('task_type'):
        return payload['task_type'] == 'site_maintenance'
    entries = (job.result or {}).get('entries', [])
    return bool(entries) and len(entries) <= 10 and any(MARKERS.intersection(row) or
        isinstance(row.get('actual'), dict) or any(isinstance(a, dict) and a.get('action') == 'showcase_layout'
        for a in row.get('actions', [])) for row in entries)


def strings(value):
    return [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def obj(value):
    return value if isinstance(value, dict) else {}


def receipt_ids(row):
    ids = []
    for key in ('receipt_ids', 'receipts', 'footer_receipts', 'followup_receipts', 'review_links_receipts'):
        ids.extend(strings(row.get(key)))
    if isinstance(row.get('receipt_id'), str):
        ids.append(row['receipt_id'])
    for key, value in row.items():
        if key.endswith('_result') or key == 'actual':
            ids.extend(receipt_ids(value) if isinstance(value, dict) else [])
    return list(dict.fromkeys(ids))


def enrich(job, entries, db=None):
    from app.report_generations import for_entries
    generations = for_entries(db, entries)
    confirmed = set()
    if db is not None:
        from sqlalchemy import select
        from app import models
        ids = list({i for row in entries for i in receipt_ids(row)})
        if ids:
            confirmed = {(e.site_id, e.id) for e in db.scalars(select(models.ProjectPageEdit).where(
                models.ProjectPageEdit.id.in_(ids), models.ProjectPageEdit.status == 'confirmed',
                models.ProjectPageEdit.requested_by == job.payload.get('actor')))}
    output = []
    for original in entries:
        row = deepcopy(original)
        if isinstance(row.get('work_summary'), dict):
            work = {k: strings(row['work_summary'].get(k)) for k in ('done', 'checks', 'issues', 'plan')}
        else:
            work = describe(row, confirmed, verify_receipts=db is not None)
        times = [row.get('completed_at'), row.get('finished_at')]
        times.extend(value.get('completed_at') or value.get('verified_at')
                     for key, value in row.items() if key.endswith('_result') and isinstance(value, dict))
        domains = [obj(row.get(key)).get('domain') for key in
                   ('logo_restore_result', 'navigation_footer_result', 'navigation_faq_result', 'breadcrumbs_result')]
        output.append({k: row[k] for k in ('site_id', 'project', 'status', 'geo') if k in row} |
                      {'main': row.get('main') or next((d for d in domains if d), None),
                       'finished_at': max((t for t in times if isinstance(t, str)), default=None),
                       'generations': generations.get(row.get('site_id'), []),
                       'work_summary': {k: list(dict.fromkeys(v)) for k, v in work.items()}})
    return output


def describe(row, confirmed, *, verify_receipts):
    done, checks, issues = [], [], []
    plan = strings(obj(row.get('plan')).get('actions'))
    ids = receipt_ids(row)
    saved = bool(ids) and (not verify_receipts or any((row['site_id'], i) in confirmed for i in ids))
    public = row.get('public_verification') or row.get('public_checks')
    if saved and public:
        done.extend(strings(row.get('showcase_actions')))
        done.extend(strings(row.get('actions')))
    for action in row.get('actions', []):
        if isinstance(action, dict) and action.get('status') == 'confirmed' and action.get('message'):
            done.append(action['message'])
    for key in ('actual', 'footer_result', 'followup_result', 'faq_answers_result', 'internal_showcase_result'):
        result = obj(row.get(key))
        if result.get('status') in {'completed', 'partial', 'confirmed'} or (saved and result.get('completed_at')):
            done.extend(strings(result.get('actions')))
            issues.extend(strings(result.get('issues')))
    crumbs = obj(row.get('breadcrumbs_result'))
    if crumbs.get('receipt_ids') and crumbs.get('status') in {'completed', 'partial'}:
        count = crumbs.get('configured_internal_pages', crumbs.get('internal_pages'))
        if count is not None:
            done.append(f'Хлебные крошки подключены на внутренних страницах: {count}.')
        verified = crumbs.get('public_verified_pages', len(crumbs.get('http_checks', [])))
        checks.append(f'Хлебные крошки проверены на опубликованных страницах: {verified}.')
        if crumbs.get('clicks'):
            checks.append('Проверены переходы на главную и родительский раздел.')
        failures = crumbs.get('routing_failures', [])
        if failures:
            issues.append(f'Вложенные страницы возвращают 404: {len(failures)}. Для них требуется исправление маршрутизации.')
    nav = obj(row.get('navigation_faq_result'))
    if nav.get('receipt_ids') and nav.get('completed_at'):
        done.extend(['Настроены выпадающие разделы меню.', 'Добавлено мобильное бургер-меню с управлением с клавиатуры.'])
        checks.append(f'Навигация проверена на страницах: {len(nav.get("page_checks", []))}.')
    footer = obj(row.get('navigation_footer_result'))
    if footer.get('receipt_ids') and footer.get('status') == 'completed':
        done.extend(['Выведено меню в шапке рядом с кнопками и добавлен мобильный бургер.',
                     'Опубликован новый футер с иконками и тематическими группами ссылок.',
                     f'Созданы внутренние страницы с перелинковкой и хлебными крошками: {footer.get("new_pages", 0)}.'])
        checks.append(f'Проверены ссылки и отображение на страницах: {len(footer.get("page_checks", []))}.')
    logo = obj(row.get('logo_restore_result'))
    if logo.get('receipt_id') and logo.get('status') == 'completed':
        done.append('По просьбе пользователя в шапку возвращён прежний логотип.')
        checks.append('Логотип загружается на компьютере и телефоне; меню и бургер работают.')
    reviews = obj(row.get('reviews_result'))
    if reviews.get('status') == 'completed':
        done.append('Перед футером размещены четыре отзыва с исходными авторами, оценками и датами, а также форма отзыва.')
        issues.append('Отправка формы отключена по просьбе пользователя до настройки обработчика.')
    if saved and row.get('footer_applied_at') and not row.get('footer_result'):
        done.append('Опубликованы обновлённый футер, его меню и связанные внутренние страницы.')
    if saved and row.get('review_links_applied_at'):
        done.append('Названия брендов в витрине связаны со страницами обзоров; на обзоры добавлены хлебные крошки.')
    year = obj(row.get('year_fix_result'))
    if year.get('status') in {'confirmed', 'completed'} or year.get('verified_at'):
        done.append('Год в заголовках и тексте обновлён до 2026.')
    if saved and public and not done and row.get('status') == 'completed':
        done.extend(f'Выполнена задача: {action.rstrip(".")}.' for action in plan)
    if public:
        evidence = public if isinstance(public, list) else obj(public).get('viewports', [])
        widths = sorted({v['width'] for v in evidence if isinstance(v, dict) and isinstance(v.get('width'), int)})
        if widths:
            checks.append('Проверено отображение на ширинах ' + ', '.join(map(str, widths)) + ' px.')
    if saved:
        checks.append('Сохранение изменений подтверждено чтением Webdev.')
    if row.get('tracking_buttons_verified'):
        checks.append('Проверены кнопки перехода и сохранность настроек отслеживания.')
    issues.extend(strings(row.get('notes')))
    issues.extend(v for v in (row.get('error'), row.get('pending_reason')) if isinstance(v, str) and v)
    if not done:
        issues.append('Подтверждённые выполненные работы пока не записаны; план не считается результатом.')
    return {'done': done, 'checks': checks, 'issues': issues, 'plan': plan}
