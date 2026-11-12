"""A read-only view of project logs plus a durable journal of interface failures."""
import re
from datetime import datetime, timezone

from sqlalchemy import case, or_, select

from app import models


def safe_text(value):
    text = str(value or '')[:20000]
    text = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[скрыто]', text)
    return re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|password|authorization|secret|token)["\']?\s*[=:]\s*["\']?)[^\s&"\'<>]+', r'\1[скрыто]', text)


def collect(db, site):
    entries = []
    def add(source, id, status, message, at, *, active=False, code='', context='', severity=None):
        entries.append({'id': f'{source}:{id}', 'source': source, 'status': status,
            'code': safe_text(code), 'message': safe_text(message or status), 'context': safe_text(context),
            'severity': severity or ('error' if status in {'failed', 'error', 'generation_failed'} else 'warning' if active else 'info'),
            'active': active, 'created_at': at, 'occurrences': 1})

    for row in db.scalars(select(models.ProjectNotification).where(models.ProjectNotification.site_id == site.id)):
        add('interface', row.id, 'active' if row.active else 'resolved', row.message, row.updated_at,
            active=row.active, code=row.code, context=row.context, severity=row.severity)
        entries[-1].update(occurrences=row.occurrences, resolved_at=row.resolved_at)
        entries[-1]['client_key'] = row.event_key.split(':', 2)[-1]

    # Keep historical failures in the log; only unresolved issues contribute to the badge.
    operations = db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id)
        .order_by(models.NetworkOperation.created_at.desc())).all()
    completed = set()
    for row in operations:
        payload = row.request_payload or {}
        subject = (row.action, str(payload.get('domains') or payload.get('reserve') or payload.get('alternate', {}).get('currentFakeMain') or ''))
        active = row.status in {'failed', 'unknown', 'pending', 'index_unknown'} and subject not in completed
        if active and row.status in {'failed', 'unknown'}:
            from app.project_network import operation_matches
            try:
                if operation_matches(row, site.network_state or {}):
                    active = False
            except (KeyError, TypeError, ValueError):
                pass
        if payload.get('parent_id') or payload.get('fake_main_parent_id'):
            active = False  # The parent operation already represents the same issue.
        add('network', row.id, row.status, row.message, row.created_at, active=active,
            code=f'HTTP_{row.response_status}' if row.response_status and row.response_status >= 400 else row.action.upper(),
            context=f'{row.action} · {row.initiator}')
        if row.status in {'confirmed', 'index_submitted'}:
            completed.add(subject)

    for cls, source in ((models.AutoReglueRun, 'reglue'), (models.ProjectPageEdit, 'page_edit'),
                        (models.ProjectPageDraft, 'page_generation'), (models.AutoLbGeneration, 'auto_lb'),
                        (models.ArticleImage, 'image')):
        error = cls.error if hasattr(cls, 'error') else cls.message
        for row in db.execute(select(cls.id, cls.status, error, cls.updated_at).where(cls.site_id == site.id)):
            id, status, message, at = row
            add(source, id, status, message, at, active=status in {'failed', 'error', 'unknown', 'waiting'}, code=source.upper())

    checks = db.scalars(select(models.MenuVisibilityCheck).where(models.MenuVisibilityCheck.site_id == site.id)
        .order_by(models.MenuVisibilityCheck.created_at.desc())).all()
    for i, row in enumerate(checks):
        add('menu', row.id, row.status, row.error_message or 'Проверка меню: ' + row.status, row.updated_at,
            active=i == 0 and row.status == 'failed', code=row.error_code or 'MENU_CHECK')

    for menu in ('header', 'footer'):
        menu_data = site.default_menu if isinstance(site.default_menu, dict) else {}
        has_items = bool(menu_data.get(menu)) or bool(db.scalar(select(models.Section.id).where(
            models.Section.site_id == site.id, models.Section.menu_type == menu,
            models.Section.sync_status != 'external_deleted', models.Section.is_temporary_parent.is_(False)).limit(1)))
        if has_items and getattr(site, menu + '_menu_rendered') is False:
            add('menu', menu, 'warning', f'Меню {menu.title()} добавлено, но не отображается на сайте.',
                site.menu_capabilities_checked_at or site.updated_at, active=True, code='MENU_NOT_RENDERED', severity='warning')
    if site.core_update_notice and site.core_update_notice != site.core_update_acknowledged:
        add('project', 'core_update', 'warning', 'Ядро проекта обновлено. Проверьте изменения проекта.', site.updated_at, active=True, code='CORE_UPDATE', severity='info')

    task_ids = select(models.GenerationTask.id).where(models.GenerationTask.site_id == site.id)
    item_scope = or_(models.ContentItem.site_id == site.id, models.ContentItem.task_id.in_(task_ids))
    item_ids = select(models.ContentItem.id).where(item_scope)
    cls = models.ContentItem
    content_columns = [cls.id, cls.status, cls.slug, cls.updated_at, cls.published_at, cls.generation_error,
        cls.competitor_research_error, cls.indexing_error, cls.deletion_error]
    archived_tasks = set(db.scalars(select(models.GenerationTask.id).where(models.GenerationTask.archived_at.is_not(None))))
    published, content_status, archived_items = {}, {}, set()
    for id, status, slug, at, published_at, *errors, task_id in db.execute(select(*content_columns, cls.task_id).where(item_scope)):
        if task_id in archived_tasks:
            archived_items.add(id)
        published[id] = published_at if status == 'published' else None
        content_status[id] = status
        for source, error in zip(('generation', 'competitors', 'indexing', 'deletion'), errors):
            if error:
                active = status not in {'published', 'deleted'} and id not in archived_items
                add(source, id, 'failed' if active else 'resolved', error, at, active=active,
                    code=source.upper(), context=slug)

    # A failed replacement leaves the original page published; its revision still needs attention.
    completed_revisions = set()
    revision = models.ContentRevision
    for id, item_id, status, error, at in db.execute(select(revision.id, revision.content_item_id,
            revision.status, revision.error_message, revision.updated_at)
            .where(revision.content_item_id.in_(item_ids)).order_by(revision.created_at.desc())):
        active = status == 'failed' and content_status.get(item_id) == 'published' and item_id not in completed_revisions and item_id not in archived_items
        add('generation', id, status, error or 'Повторная генерация: ' + status, at,
            active=active, code='CONTENT_REVISION', context='Текст: ' + item_id)
        if status == 'completed':
            completed_revisions.add(item_id)

    # Failed individual competitor captures remain in history even if the overall brief succeeded.
    page = models.CompetitorPage
    for id, error, code, url, at in db.execute(select(page.id, page.error_message, page.http_status,
            page.url, page.updated_at).where(page.content_item_id.in_(item_ids),
                or_(page.error_message.is_not(None), page.http_status >= 400))):
        add('competitors', id, 'failed', error or f'Получение HTML конкурента: HTTP {code}', at,
            code=f'HTTP_{code}' if code else 'COMPETITOR_CAPTURE', context=url)

    def timestamp(value):
        if not value: return 0
        return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
    for row in db.execute(select(models.PublicationLog.id, models.PublicationLog.content_item_id,
            models.PublicationLog.error_message, models.PublicationLog.response_status,
            models.PublicationLog.created_at, case((or_(models.PublicationLog.error_message.is_not(None),
                models.PublicationLog.response_status >= 400), models.PublicationLog.response_body), else_=None))
            .where(models.PublicationLog.content_item_id.in_(item_ids))):
        id, item_id, error, code, at, response_body = row
        failed = bool(error) or bool(code and code >= 400)
        resolved = item_id in archived_items or timestamp(published.get(item_id)) >= timestamp(at)
        add('publication', id, 'failed' if failed else 'completed', error or f'Публикация: HTTP {code or "—"}',
            at, active=failed and not resolved, code=f'HTTP_{code}' if code else 'PUBLICATION',
            context=str(response_body) if failed and response_body else '')

    # Jobs associated indirectly with a text or project are included without fetching payload bodies.
    job = models.BackgroundJob
    from app.fibery_reglue import KIND as FIBERY_KIND, notice as fibery_notice
    fibery_jobs = db.scalars(select(job).where(job.kind == FIBERY_KIND,
        job.payload['site_id'].as_string() == site.id).order_by(job.created_at.desc())).all()
    for index, row in enumerate(fibery_jobs):
        entry = fibery_notice(row)
        entry['active'] = row.status != 'completed' or index == 0
        entries.append(entry)
    from app.fake_redirect_check import KIND as REDIRECT_KIND, notice as redirect_notice
    for row in db.scalars(select(job).where(job.kind == REDIRECT_KIND,
            job.payload['site_id'].as_string() == site.id).order_by(job.created_at.desc())):
        if (row.result or {}).get('task') or row.error:
            entries.append(redirect_notice(row))
    scope = or_(job.payload['site_id'].as_string() == site.id,
        job.payload['content_id'].as_string().in_(item_ids), job.payload['task_id'].as_string().in_(task_ids),
        job.payload['generation_id'].as_string().in_(select(models.AutoLbGeneration.id).where(models.AutoLbGeneration.site_id == site.id)),
        job.payload['draft_id'].as_string().in_(select(models.ProjectPageDraft.id).where(models.ProjectPageDraft.site_id == site.id)))
    for id, kind, status, error, at, content_id in db.execute(select(job.id, job.kind, job.status, job.error, job.updated_at,
            job.payload['content_id'].as_string()).where(scope, job.kind.not_in([FIBERY_KIND, REDIRECT_KIND]))):
        resolved = kind in {'generation_retry', 'publication'} and (
            content_id in archived_items or bool(published.get(content_id) and timestamp(published[content_id]) >= timestamp(at)))
        add('job', id, status, error or f'{kind}: {status}', at,
            active=status == 'failed' and not resolved and kind not in {'auto_lb', 'project_page_ai', 'article_image'}, code=kind.upper())

    entries.sort(key=lambda row: timestamp(row['created_at']), reverse=True)
    return entries


def feed(db, site, *, offset=0, limit=50, active_only=False, query=''):
    entries = collect(db, site)
    active_count = sum(row['active'] for row in entries)
    active_client_keys = [row['client_key'] for row in entries if row['active'] and row.get('client_key')]
    if active_only:
        entries = [row for row in entries if row['active']]
    if query:
        query = query.casefold()
        entries = [row for row in entries if query in (row['code'] + ' ' + row['message'] + ' ' + row['context']).casefold()]
    return {'site_id': site.id, 'project': site.name, 'active_count': active_count, 'active_client_keys': active_client_keys, 'total': len(entries),
        'offset': offset, 'limit': limit, 'items': entries[offset:offset + limit]}


def record(db, site, username, payload):
    key = f'client:{username}:{payload.key}'[:240]
    # Serialize events for this project, including a failed request followed by its resolution.
    db.scalar(select(models.Site).where(models.Site.id == site.id).with_for_update())
    row = db.scalar(select(models.ProjectNotification).where(
        models.ProjectNotification.site_id == site.id, models.ProjectNotification.event_key == key))
    if row and not row.active and payload.active:
        row.event_key = key[:185] + ':history:' + row.id
        db.flush()
        row = None
    if not row:
        if not payload.active:
            return None
        row = models.ProjectNotification(site_id=site.id, event_key=key, occurrences=0)
        db.add(row)
    if payload.active:
        row.code, row.severity = payload.code, payload.severity
        row.message, row.context = safe_text(payload.message), safe_text(payload.context)
        row.occurrences += 1
    row.active = payload.active
    row.resolved_at = None if payload.active else datetime.now(timezone.utc)
    db.commit()
    return row.id
