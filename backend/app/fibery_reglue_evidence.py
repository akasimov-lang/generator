"""Freeze a six-minute work log from receipts, never from today's project cache."""
from datetime import timedelta
import re

from sqlalchemy import or_, select

from app import models
from app.network_state import alternate_links
from app.project_notifications import safe_text
from app.reglue_history import MOSCOW, utc
from app.reglue_journal import confirmed_at

WINDOW = timedelta(minutes=3)
LABELS = {
    'reglue': 'Переклей Main', 'reserve': 'Выбор резервного домена',
    'create_fake_main': 'Создание/выбор фейковой внутренней страницы',
    'select_fake_main': 'Замена фейковой внутренней страницы',
    'alternates': 'Обновление альтернейтов', 'canonical': 'Обновление canonical',
    'reglue_redirects': 'Обновление редиректов после переклея',
    'domain_redirect': 'Редиректы доменов', 'domain_redirects_main': 'Обновление цели редиректов',
    'create_domains': 'Добавление доменов', 'create_subdomains': 'Создание поддоменов',
    'delete_domain': 'Удаление домена из сетки', 'sitemap': 'Обновление sitemap',
    'indexing': 'Отправка сетки на индексацию', 'structured_data': 'Обновление микроразметки',
}


def network_snapshot(state):
    return {'main': state.get('canon'), 'fake_path': state.get('fake_main_current'),
            'fake_enabled': state.get('fake_main_enabled'),
            'alternates': {'markup': state.get('alternateMarkup'), 'enabled': state.get('enableAlternates')}}


def alternates(payload, side):
    value = (payload.get('fibery_' + side) or {}).get('alternates') or payload.get('alternates_' + side)
    if isinstance(value, dict) and isinstance(value.get('markup'), str):
        return {'markup': value['markup'], 'enabled': value.get('enabled')}
    head = payload.get('head_before' if side == 'before' else 'head_sync') or {}
    if isinstance(head.get('alternateMarkup'), str):
        return {'markup': head['alternateMarkup'], 'enabled': head.get('enableAlternates')}
    if side == 'after' and isinstance(payload.get('alternateMarkup'), str):
        return {'markup': payload['alternateMarkup'], 'enabled': payload.get('enableAlternates')}
    return None


def stamp(value):
    return utc(value).astimezone(MOSCOW).strftime('%d.%m.%Y %H:%M:%S МСК')


def text(value):
    return safe_text(value).replace('\n', ' ').replace('\r', ' ').strip()


def build(db, site, operation):
    at = confirmed_at(operation)
    start, end = at - WINDOW, at + WINDOW
    events, network = [], []
    for row in db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id)):
        event_at = confirmed_at(row)
        if start <= event_at <= end:
            network.append((row, event_at, row.status))
        elif start <= utc(row.created_at) <= end and event_at > end:
            network.append((row, utc(row.created_at), 'pending_at_window_end'))
    network.sort(key=lambda item: (item[1], item[0].id))
    source = operation.request_payload.get('source_domain')
    target = operation.request_payload.get('reserve')
    old_path = new_path = None
    old_alts = new_alts = None
    for row, event_at, event_status in network:
        payload = row.request_payload or {}
        detail = LABELS.get(row.action, 'Изменение сетки: ' + row.action)
        if row.action == 'reglue':
            detail += ': ' + str(payload.get('source_domain') or 'не сохранено') + ' → ' + str(payload.get('reserve') or 'не сохранено')
        elif row.action == 'reserve':
            detail += ': ' + str(payload.get('reserve') or 'не выбран')
        if event_status == 'confirmed':
            before = payload.get('fibery_before') or payload.get('journal_before') or {}
            after = payload.get('fibery_after') or payload.get('journal_after') or {}
            if old_path is None and 'fake_path' in before:
                old_path = before['fake_path']
            candidate = after.get('fake_path')
            if candidate is None:
                candidate = (payload.get('alternate') or {}).get('currentFakeMain')
            if candidate is not None:
                new_path = candidate
            previous, following = alternates(payload, 'before'), alternates(payload, 'after')
            if old_alts is None and previous:
                old_alts = previous
            elif old_alts and previous and old_alts['markup'] == previous['markup'] and old_alts.get('enabled') is None:
                old_alts['enabled'] = previous.get('enabled')
            if following:
                new_alts = following
            if row.action in {'create_fake_main', 'select_fake_main'}:
                detail += ': ' + str(before.get('fake_path') or 'не сохранено') + ' → ' + str(candidate or 'не активирована')
        events.append({'source': 'network', 'id': row.id, 'at': event_at.isoformat(),
                       'status': event_status, 'description': detail, 'actor': row.initiator})

    def changed(model, condition):
        timing = [model.updated_at.between(start, end), model.created_at.between(start, end)]
        if hasattr(model, 'started_at'):
            timing.append(model.started_at.between(start, end))
        return db.scalars(select(model).where(condition, or_(*timing))).all()

    def add(row, source_, description, actor=''):
        in_window = start <= utc(row.updated_at) <= end
        event_at = utc(row.updated_at) if in_window else utc(getattr(row, 'started_at', None)) or utc(row.created_at)
        events.append({'source': source_, 'id': row.id, 'at': event_at.isoformat(),
                       'status': row.status if in_window else 'pending_at_window_end', 'description': text(description), 'actor': actor})

    for row in changed(models.ProjectPageEdit, models.ProjectPageEdit.site_id == site.id):
        before, after = row.before_page or {}, row.after_page or {}
        fields = [key for key in ('title', 'description', 'slug', 'content', 'h1') if before.get(key) != after.get(key)]
        detail = 'Редактирование страницы/шаблона ' + str(after.get('slug') or row.page_key)
        if fields:
            detail += '; изменены: ' + ', '.join(fields)
        add(row, 'page_edit', detail, row.requested_by)
    for row in changed(models.ProjectPageDraft, models.ProjectPageDraft.site_id == site.id):
        add(row, 'page_generation', f'Подготовка текста {row.page_key}: {row.action}', row.requested_by)
    for row in changed(models.AutoLbGeneration, models.AutoLbGeneration.site_id == site.id):
        add(row, 'auto_lb', 'Генерация АвтоЛБ: ' + row.kind)
    for row in changed(models.ArticleImage, models.ArticleImage.site_id == site.id):
        add(row, 'image', 'Подготовка изображения статьи')
    task_ids = select(models.GenerationTask.id).where(models.GenerationTask.site_id == site.id)
    items = db.scalars(select(models.ContentItem).where(or_(models.ContentItem.site_id == site.id,
                       models.ContentItem.task_id.in_(task_ids)))).all()
    for item in items:
        if start <= utc(item.updated_at) <= end or start <= utc(item.created_at) <= end:
            add(item, 'content', 'Работа с текстом: ' + str(item.slug or item.topic))
    item_ids = [item.id for item in items]
    if item_ids:
        for log in db.scalars(select(models.PublicationLog).where(models.PublicationLog.content_item_id.in_(item_ids),
                models.PublicationLog.created_at >= start, models.PublicationLog.created_at <= end)):
            events.append({'source': 'publication', 'id': log.id, 'at': utc(log.created_at).isoformat(),
                           'description': 'Публикация текста; HTTP ' + str(log.response_status or 'не получен'),
                           'status': 'completed' if log.response_status and 200 <= log.response_status < 300 and not log.error_message else 'unknown', 'actor': ''})
    for row in changed(models.BackgroundJob, or_(models.BackgroundJob.payload['site_id'].as_string() == site.id,
            models.BackgroundJob.payload['content_id'].as_string().in_(item_ids),
            models.BackgroundJob.payload['task_id'].as_string().in_(task_ids))):
        if row.kind != 'fibery_reglue':
            add(row, 'job', 'Фоновая работа: ' + row.kind)
    events.sort(key=lambda row: (row['at'], row['source'], row['id']))
    result = {'operation_id': operation.id, 'site_id': site.id, 'project': site.name,
              'fibery_name': site.fibery_name, 'confirmed_at': at.isoformat(),
              'window_start': start.isoformat(), 'window_end': end.isoformat(),
              'source': source, 'target': target, 'old_path': old_path, 'new_path': new_path,
              'alternates_before': old_alts, 'alternates_after': new_alts, 'events': events}
    result['description'] = render(result)
    return result


def render(evidence):
    e = evidence
    lines = [f'Переклей: {text(e["source"])} → {text(e["target"])}', '',
        f'- Main: {text(e["source"])} → {text(e["target"])}.',
        f'- Фейковая внутренняя страница: {e["old_path"] if e["old_path"] is not None else "исходное значение не сохранено"} → {e["new_path"] if e["new_path"] is not None else "результат не сохранён"}.', '']
    for side, heading, domain in [('before', 'Альтернейты до изменений', e['source']), ('after', 'Альтернейты после изменений', e['target'])]:
        value = e['alternates_' + side]
        lines += [heading + ':', '']
        if value is None:
            lines += ['- Исторический снимок не сохранён. Текущие настройки не подставлялись вместо него.', '']
            continue
        links = alternate_links(value['markup'])
        for link in links:
            href = link['href'].replace('{{settings.canon}}', domain or '')
            lines.append(f'- {text(link.get("hreflang") or link.get("lang") or "alternate")}: {text(href)}')
        if not value['markup'].strip():
            lines.append('- Разметка пустая.')
        elif not links:
            lines.append('- Сохранена нестандартная разметка: ' + text(value['markup']))
        # Keep exact templates as well as the readable, domain-resolved list.
        fence = '`' * max(3, max((len(part) for part in re.findall(r'`+', value['markup'])), default=0) + 1)
        lines += ['', fence + 'html', value['markup'], fence, '']
    return '\n'.join(lines).rstrip()
