"""Durable maintenance reports; only explicit repeat requests enqueue work."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from uuid import UUID

from sqlalchemy import select

from app import models

KIND = 'maintenance_report'
STATUSES = {'pending', 'running', 'waiting', 'completed', 'partial', 'failed', 'skipped'}


def upsert(db, report_id, name, actor, site_ids, entries=(), status='running'):
    """Merge confirmed outcomes by project; omitted rows retain their prior state."""
    report_id = str(UUID(str(report_id)))
    ids = list(dict.fromkeys(str(site_id) for site_id in site_ids))
    if not ids or not name.strip() or status not in {'running', 'completed', 'partial', 'failed'}:
        raise ValueError('Укажите проекты, название и корректное состояние отчёта.')
    job = db.get(models.BackgroundJob, report_id)
    if job and (job.kind != KIND or job.payload.get('actor') != actor or set(job.payload.get('site_ids', [])) != set(ids)):
        raise ValueError('Идентификатор отчёта уже занят другой задачей.')
    rows = {row['site_id']: deepcopy(row) for row in (job.result or {}).get('entries', [])} if job else {}
    for site_id in ids:
        if site_id not in rows:
            site = db.get(models.Site, site_id)
            if not site:
                raise ValueError('Проект отчёта не найден.')
            from app.report_evidence import observations
            observed = observations(db, [site_id]).get(site_id)
            rows[site_id] = {'site_id': site_id, 'project': site.name, 'status': 'pending'}
            if observed:
                rows[site_id].update(before=deepcopy(observed['values']), before_observation=observed)
    changed_ids = set()
    for entry in entries:
        site_id = str(entry.get('site_id', ''))
        if site_id not in ids or entry.get('status', rows[site_id]['status']) not in STATUSES:
            raise ValueError('Некорректная строка отчёта.')
        rows[site_id] = {**rows[site_id], **deepcopy(entry), 'site_id': site_id}
        changed_ids.add(site_id)
    if status == 'completed' and any(row['status'] not in {'completed', 'skipped'} for row in rows.values()):
        raise ValueError('В отчёте остались незавершённые проекты.')
    now = datetime.now(timezone.utc)
    if not job:
        job = models.BackgroundJob(id=report_id, kind=KIND, started_at=now,
                                   payload={'actor': actor, 'site_ids': ids})
        db.add(job)
    job.payload = {**job.payload, 'name': name.strip()}
    job.result = {'entries': [rows[site_id] for site_id in job.payload['site_ids']]}
    from app.showcase_history import remember_report
    for site_id in changed_ids:
        remember_report(db, job, rows[site_id])
    job.status = status
    job.finished_at = None if status == 'running' else now
    db.commit()
    return job


def visible(job, user):
    allowed = user.get('allowed_site_ids')
    return bool(job and job.kind == KIND and job.payload.get('actor') == user['username'] and
                (allowed is None or set(job.payload.get('original_site_ids',job.payload.get('site_ids', []))).issubset(allowed)))


def get(db, report_id, user):
    job = db.get(models.BackgroundJob, str(report_id))
    if not visible(job, user):
        raise ValueError('Отчёт не найден.')
    return job


def summary(job, report_id=None, *, entries=None):
    entries = (job.result or {}).get('entries', []) if entries is None else entries
    repeat = bool(job.payload.get('repeat'))
    from app.maintenance_worklist import is_work_report
    work_list = is_work_report(job)
    factual = work_list or job.payload.get('task_type') in {'sitemap_repair', 'brand_health_audit', 'system_recovery', 'toc_repair', 'showcase_audit', 'showcase_inventory', 'showcase_standardization', 'article_image_localization'}
    done = sum(row['status'] in {'completed', 'partial', 'failed', 'skipped'} for row in entries)
    active = any(row['status'] in {'pending','running','waiting'} for row in entries)
    progress = [entry_progress(row, content_only=bool(job.payload.get('text_revision_20261027')),
                              group_program=job.payload.get('task_type') == 'brand_content_network_program')
                for row in entries]
    if factual:
        progress = [{'done': int(row['status'] in {'completed', 'skipped', 'partial', 'failed'}), 'total': 1} for row in entries]
    steps_done, steps_total = sum(p['done'] for p in progress), sum(p['total'] for p in progress)
    percent = round(100 * steps_done / steps_total) if steps_total else 0
    if active: percent = min(percent, 99)
    if job.payload.get('planning_only'):
        steps_done = sum(bool(row.get('plan') or row.get('proposed_plan')) for row in entries)
        steps_total = len(entries)
        percent = round(100 * steps_done / steps_total) if steps_total else 100
    from app.report_status import metadata
    from app.report_membership import can_exclude
    return {**metadata(job, finished_at=job.finished_at), 'can_exclude':can_exclude(job),
            'excluded_projects':[{k:v for k,v in e.items() if k not in {'entry','previous_result'}} for e in job.payload.get('excluded_projects',[])],
            'id': job.id, 'report_id': report_id, 'name': job.payload['name'], 'mode': 'maintenance', 'status': job.status,
            'created_at': job.created_at, 'launched_at': job.started_at or job.created_at,
            'finished_at': metadata(job, finished_at=None if active else job.finished_at)['finished_at'], 'total': len(entries),
            'counts': dict(Counter(row['status'] for row in entries)),
            'report_url': f'/auto-reglue/pilot/report?maintenance={job.id}',
            'repeat': repeat, 'parent_report_id': job.payload.get('parent_report_id'),
            'task_type': job.payload.get('task_type'), 'presentation': 'work_list' if work_list else None,
            'source_reports': [
                {'id': str(source_id), 'report_id': number}
                for source_id, number in zip(job.payload.get('source_report_ids', []),
                                             job.payload.get('source_report_numbers', []))
            ],
            'allow_reserve': bool(job.payload.get('allow_reserve')),
            'progress': {'done': steps_done, 'total': steps_total, 'percent': percent,
                         'projects_done': done, 'projects_total': len(entries), 'unit': 'projects' if factual else 'steps'}}


def page_values(page):
    """Comparable values from a saved page, never from the current live website."""
    from app.homepage_headings import extract
    from app.page_word_count import page_word_count
    if not isinstance(page, dict):
        return {}
    values = {key: page[key] for key in ('title', 'description') if key in page}
    words = page_word_count(page)
    if words is not None:
        values['words'] = words
    if isinstance(page.get('content'), dict):
        detected = extract({'data': {'pages': [{**page, 'slug': '/'}]}})
        # Missing template definitions are unknown, not an empty H1.
        if detected['h1_status'] == 'found':
            values['h1'] = '\n'.join(item['text'] for item in detected['headings'])
    return values


def timestamp(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()
    return value


def paragraph_metrics(page):
    """Count EditorJS paragraphs and real HTML <p>, excluding inert markup."""
    identities = []
    class Paragraphs(HTMLParser):
        def __init__(self, block_id):
            super().__init__()
            self.block_id = block_id
            self.blocked = 0
        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag in {'script', 'style', 'template'}:
                self.blocked += 1
            elif tag == 'p' and not self.blocked:
                identity = dict(attrs).get('id')
                identities.append('html:' + str(self.block_id) + ':' + identity if identity else None)
        def handle_endtag(self, tag):
            if tag.lower() in {'script', 'style', 'template'}:
                self.blocked = max(0, self.blocked - 1)
    document = page.get('content')
    for block in document.get('blocks', []) if isinstance(document, dict) else []:
        if not isinstance(block, dict):
            continue
        if block.get('type') == 'paragraph':
            identity = block.get('id')
            identities.append('editor:' + identity if isinstance(identity, str) and identity else None)
        elif block.get('type') in {'code', 'raw', 'html'}:
            data = block.get('data') or {}
            markup = data.get('code') or data.get('html')
            if isinstance(markup, str):
                parser = Paragraphs(block.get('id')); parser.feed(markup); parser.close()
    stable = all(identities) and len(set(identities)) == len(identities)
    return {'count': len(identities), 'ids': identities if stable else None}


def view(job, db=None):
    entries = deepcopy((job.result or {}).get('entries', []))
    if job.payload.get('task_type') == 'sitemap_repair':
        from app import report_ids
        compact = []
        for row in entries:
            item = {key: row[key] for key in ('site_id','project','status','main','geo','brand','fibery_name','fibery_url','error','plan','finished_at','fibery_task','fibery_error') if key in row}
            evidence = row.get('sitemap') or {}
            item['sitemap'] = {key: evidence[key] for key in ('action','sitemap_url','expected_count','internal_pages','operation_status','webdev_verified','updated_urls') if key in evidence}
            for phase in ('before','after'):
                value = evidence.get(phase) or {}
                if phase == 'before':
                    value = {**value, **value.get('public',{})}
                item['sitemap'][phase] = {key: value[key] for key in ('status','valid','count','missing','extra','duplicates','error','location','checked_at') if key in value}
            compact.append(item)
        return {**summary(job, report_ids.get(db,job) if db is not None else None, entries=compact),
            'updated_at':job.updated_at,'entries':compact,'scope':job.payload.get('scope'),'parameters':job.payload.get('parameters')}
    if job.payload.get('task_type') == 'brand_health_audit':
        from app import report_ids
        keys = ('site_id', 'project', 'status', 'brand', 'geo', 'main', 'main_url', 'inner_url',
                'fibery_name', 'fibery_url', 'fibery_verified', 'domains_count', 'health', 'error', 'plan')
        compact = [{k: row[k] for k in keys if k in row} for row in entries]
        return {**summary(job, report_ids.get(db, job) if db is not None else None, entries=compact),
                'updated_at': job.updated_at, 'entries': compact, 'audit_only': True, 'can_exclude': False,
                'scope': job.payload.get('scope'), 'parameters': job.payload.get('parameters')}
    from app.maintenance_worklist import is_work_report
    work_list = is_work_report(job)
    factual = work_list or job.payload.get('task_type') in {'sitemap_repair', 'system_recovery', 'toc_repair', 'showcase_audit', 'showcase_inventory', 'showcase_standardization', 'article_image_localization'}
    if work_list:
        from app import maintenance_worklist, report_ids
        compact = maintenance_worklist.enrich(job, entries, db)
        return {**summary(job, report_ids.get(db, job) if db is not None else None, entries=compact),
                'updated_at': job.updated_at, 'entries': compact}
    if job.payload.get('task_type') == 'system_recovery':
        from app import report_ids
        compact = [{key: row[key] for key in ('site_id','project','status','facts','error','finished_at') if key in row} for row in entries]
        return {**summary(job, report_ids.get(db, job) if db is not None else None, entries=compact),
                'updated_at': job.updated_at, 'entries': compact}
    if job.payload.get('task_type') == 'article_image_localization':
        from app import report_ids
        keys = ('site_id','project','status','main','brand','fibery_name','geo','webdev_url','error','image_localization')
        compact = [{key: row[key] for key in keys if key in row} for row in entries]
        for row in compact:
            data = row.get('image_localization')
            if isinstance(data, dict):
                row['image_localization'] = {k:v for k,v in data.items() if k not in {'before','after','pages','receipts'}}
        return {**summary(job, report_ids.get(db, job) if db is not None else None, entries=compact),
                'updated_at': job.updated_at, 'entries': compact}
    if job.payload.get('task_type') in {'showcase_inventory', 'showcase_standardization'}:
        from app import report_ids
        compact = [{key: row[key] for key in ('site_id','project','fibery_name','status','main','geo','inventory','portfolio','error','migration','completeness') if key in row} for row in entries]
        for row in compact:
            if isinstance(row.get('migration'),dict):
                row['migration']={key:value for key,value in row['migration'].items() if key!='plan'}
            if isinstance(row.get('completeness'), dict):
                row['completeness'] = {key: value for key, value in row['completeness'].items() if key != 'cards'}
        return {**summary(job, report_ids.get(db, job) if db is not None else None, entries=compact),
                'updated_at': job.updated_at, 'entries': compact,
                'inventory_excluded': job.payload.get('scope', {}).get('excluded_today', []),
                'inventory_monobrands': job.payload.get('audit_refresh', {}).get('confirmed_monobrands', []),
                'inventory_view': job.payload.get('inventory_view'),
                'audit_only': bool(job.payload.get('audit_only'))}
    if factual:
        from app.maintenance_evidence import enrich
        entries = enrich(job, entries, db)
    if db is not None and not factual:
        from app.content_metrics import counts as content_counts, comparison, brand_term
        brands = dict(db.execute(select(models.Site.id, models.Site.brand).where(
            models.Site.id.in_([row['site_id'] for row in entries]))).all())
        ids = {str(edit_id) for row in entries for edit_id in row.get('edit_ids', [])}
        edits = list(db.scalars(select(models.ProjectPageEdit).where(
            models.ProjectPageEdit.id.in_(ids),
            models.ProjectPageEdit.status == 'confirmed',
            models.ProjectPageEdit.requested_by == job.payload['actor'],
        ))) if ids else []
        for row in entries:
            own = sorted((edit for edit in edits if edit.site_id == row['site_id']
                          and edit.id in row.get('edit_ids', [])),
                         key=lambda edit: (edit.created_at, edit.id))
            if not own:
                continue
            revision = [edit for edit in own if edit.id in row.get('content_revision_edit_ids', [])] or own
            first = revision[0]
            row['before'] = {**row.get('before', {}), **page_values(first.before_page)}
            row['after'] = {**row.get('after', {}), **page_values(own[-1].after_page)}
            brand = brands.get(row['site_id'], '')
            row['before'].update(content_counts(first.before_page, brand))
            row['after'].update(content_counts(own[-1].after_page, brand))
            row.update(comparison(first.before_page, own[-1].after_page))
            row['brand_count_term'] = brand_term(brand)
            old_paragraphs, new_paragraphs = paragraph_metrics(first.before_page), paragraph_metrics(own[-1].after_page)
            row.update(paragraphs_before=old_paragraphs['count'], paragraphs_after=new_paragraphs['count'])
            if row.get('paragraph_changes'):
                change = row['paragraph_changes']
                if isinstance(change.get('added_ids'), list) and isinstance(change.get('removed_ids'), list):
                    row.update(paragraphs_added=len(change['added_ids']), paragraphs_removed=len(change['removed_ids']))
            elif old_paragraphs['ids'] is not None and new_paragraphs['ids'] is not None:
                row.setdefault('paragraphs_added', len(set(new_paragraphs['ids']) - set(old_paragraphs['ids'])))
                row.setdefault('paragraphs_removed', len(set(old_paragraphs['ids']) - set(new_paragraphs['ids'])))
            # Counts without stable identities are unknown; retain any explicit
            # confirmed action audit instead of replacing it with a net delta.
            row['content_started_at'] = timestamp(first.created_at)
            row['content_finished_at'] = timestamp(own[-1].updated_at)
            row['operations'] = [*row.get('network_operations', []), *[{
                'id': edit.id, 'kind': 'page_edit', 'status': edit.status,
                'started_at': timestamp(edit.created_at), 'finished_at': timestamp(edit.updated_at),
                'before': page_values(edit.before_page), 'after': page_values(edit.after_page),
            } for edit in own]]
    if db is not None:
        from app.report_evidence import enrich as enrich_report_evidence
        entries = enrich_report_evidence(db, entries)
    for row in entries:
        if factual:
            row.pop('progress', None)
            continue
        row['progress'] = entry_progress(row, content_only=bool(job.payload.get('text_revision_20261027')),
                                         group_program=job.payload.get('task_type') == 'brand_content_network_program')
    from app import report_ids
    return {**summary(job, report_ids.get(db, job) if db is not None else None, entries=entries), 'updated_at': job.updated_at, 'entries': entries,
            'words_scope': 'content_blocks'}


def entry_progress(row, *, content_only=False, group_program=False):
    """Completed workflow steps from saved evidence, not elapsed-time estimates."""
    if not content_only and (group_program or row.get('program_progress') == 1):
        return group_entry_progress(row)
    phase=row.get('phase','')
    if row.get('kind') == 'structured_data':
        schema = row.get('structured_data') or {}
        planned, saved = schema.get('planned') or {}, schema.get('after') or {}
        prepared = bool(planned.get('enabled') is True and planned.get('markup'))
        confirmed = bool(prepared and saved.get('enabled') is True and
                         saved.get('markup') == planned['markup'])
        verified = bool(confirmed and schema.get('public_verified') is True)
        done = sum((prepared, confirmed, verified))
        label = {
            'structured_data_prepare': 'Подготавливаем микроразметку',
            'structured_data_publish': 'Включаем микроразметку в Webdev',
            'structured_data_verify': 'Проверяем код на сайте',
            'completed': 'Микроразметка включена и проверена на сайте',
        }.get(phase, 'Подготавливаем микроразметку')
        if row.get('status') in {'partial', 'failed', 'waiting'}:
            label = row.get('message') or ('Микроразметка сохранена; проверка сайта не завершена' if confirmed
                                         else 'Ожидаем подтверждение; подробности ниже')
        elif phase == 'completed' and not verified:
            label = 'Проверка микроразметки не завершена'
        percent = round(100 * done / 3)
        if row.get('status') in {'pending', 'running', 'waiting'}: percent = min(percent, 99)
        return {'done': done, 'total': 3, 'percent': percent, 'label': label}
    edits=[op for op in row.get('operations',[]) if op.get('kind')=='page_edit' and op.get('status')=='confirmed']
    if row.get('revision_number'):
        edits=[op for op in edits if op.get('id') in row.get('content_revision_edit_ids',[])]
    content_saved=bool(edits or row.get('content_confirmed') and not row.get('revision_number'))
    operations=row.get('network_operations',[])
    confirmed={op.get('action') or op.get('kind') for op in operations if op.get('status')=='confirmed'}
    prepared=bool(row.get('plan') or row.get('planned') or phase not in {'','pending','snapshot','preparing_text_revision','preparing_content','generate'})
    text_ready=content_saved or row.get('paragraphs',{}).get('status')=='ready' or phase=='save_content'
    steps=[prepared,text_ready,content_saved]
    if not content_only:
        attempts=row.get('attempts') or row.get('network_attempts') or []
        domain_ready=bool(attempts and attempts[-1].get('status')=='confirmed')
        steps += [domain_ready or 'reglue' in confirmed,'reglue' in confirmed,'alternates' in confirmed]
    if row.get('status')=='completed':steps=[True]*len(steps)
    labels={'preparing_text_revision':'Переписываем тексты по новым правилам','preparing_content':'Подготавливаем тексты',
        'generate':'Переписываем контент и мета','save_content':'Сохраняем страницу','plan':'Подготавливаем схему переклея',
        'second_subdomain_attempt':'Создаём другой поддомен: попытка 2 из 2','execute':'Выполняем переклей',
        'completed':'Изменения подтверждены','content_complete':'Тексты опубликованы'}
    label=labels.get(phase) or row.get('message') or 'Подготовка проекта'
    if row.get('status') in {'partial','failed'}:
        failed_dns=any(a.get('status')=='failed' for a in (row.get('attempts') or row.get('network_attempts') or []))
        label=('Текст опубликован. Ошибка создания поддомена.' if content_saved else 'Ошибка создания поддомена.') if failed_dns else ('Часть работ выполнена; подробности ниже' if content_saved else 'Ошибка выполнения; подробности ниже')
    done=sum(steps)
    if row.get('content_error'):
        label = 'Ошибка сохранения текста; подробности ниже' if phase == 'save_content' else 'Ошибка подготовки текста; подробности ниже'
    percent = round(100 * done / len(steps))
    if row.get('status') in {'pending', 'running', 'waiting'}: percent = min(percent, 99)
    return {'done':done,'total':len(steps),'percent':percent,'label':label}


def group_entry_progress(row):
    """Independent content/network stages; a ready subdomain is useful progress."""
    plan = row.get('planned') or row.get('plan') or {}
    phase = row.get('phase', '')
    provisioning = row.get('provisioning') or {}
    readiness = row.get('readiness_observed') or {}
    indexing = row.get('indexing_settings') or {}
    public_indexing = row.get('public_indexability') or {}
    operations = row.get('network_operations') or []
    confirmed = {op.get('action') or op.get('kind') for op in operations if op.get('status') == 'confirmed'}
    edits = [op for op in row.get('operations', []) if op.get('kind') == 'page_edit' and op.get('status') == 'confirmed']
    if row.get('revision_number'):
        edits = [op for op in edits if op.get('id') in row.get('content_revision_edit_ids', [])]
    saved = bool(edits or row.get('content_confirmed') and not row.get('revision_number'))
    prepared = bool(saved or row.get('content_prepared_at') and row.get('prepared_content')
                    or (row.get('paragraphs') or {}).get('status') == 'ready')
    domain_ready = bool(provisioning.get('ready') and provisioning.get('public_verified')
                        or readiness.get('membership_confirmed') and readiness.get('https_status') == 200)
    index_ready = indexing.get('status') == 'confirmed' and public_indexing.get('indexing_allowed') is True
    main_ready = 'reglue' in confirmed
    verification = row.get('public_network_verification') or {}
    root, fake = verification.get('root') or {}, verification.get('fake') or {}
    verified = bool(plan.get('main') and root.get('https_status') == fake.get('https_status') == 200
                    and root.get('url') == 'https://' + plan['main'] + '/'
                    and fake.get('url') == 'https://' + plan['main'] + plan.get('fake_path', '')
                    and (row.get('after') or {}).get('main') == plan['main'])
    main_ready = bool(main_ready or verified)
    completed = [bool(plan), domain_ready or main_ready, index_ready, prepared, saved, main_ready, verified]
    stages = [{'key': key, 'label': label, 'state': 'completed' if done else 'pending'}
              for (key, label), done in zip([
                  ('plan', 'План'), ('subdomain', 'Поддомен'), ('indexing', 'Индексация'),
                  ('content_prepare', 'Подготовка текста'), ('content_save', 'Сохранение текста'),
                  ('reglue', 'Переклей'), ('verification', 'Альтернейты и проверка сайта')], completed)]
    running = {'generate': 'content_prepare', 'preparing_content': 'content_prepare', 'save_content': 'content_save',
               'reglue': 'reglue', 'alternates': 'verification', 'provisioning': 'subdomain'}
    current_stages = {running.get(phase), running.get(row.get('network_phase'))}
    for stage in stages:
        if stage['key'] in current_stages and stage['state'] != 'completed': stage['state'] = 'running'
    if row.get('content_error'):
        key = 'content_save' if phase == 'save_content' and prepared else 'content_prepare'
        next(stage for stage in stages if stage['key'] == key)['state'] = 'failed'
    if provisioning.get('status') == 'failed' and not domain_ready:
        stages[1]['state'] = 'failed'
    if indexing.get('status') in {'failed', 'changed'}:
        stages[2]['state'] = 'failed'
    if row.get('network_error'):
        stages[6 if main_ready else 5 if domain_ready else 1]['state'] = 'failed'
    label = row.get('message') or {
        'content_planned': 'Подготовлена новая текстовая схема; ожидает генерации целой страницы',
        'generate': 'Переписываем целую страницу', 'save_content': 'Сохраняем подготовленный текст',
        'content_complete': 'Текст сохранён; подготовка сетки продолжается',
        'completed': 'Изменения подтверждены',
    }.get(phase, 'Подготавливаем проект')
    if row.get('content_error'):
        label = 'Ошибка сохранения текста; подробности ниже' if phase == 'save_content' and prepared else 'Ошибка подготовки текста; подробности ниже'
    elif row.get('network_error'):
        label = 'Текст сохранён; проверяем подготовку сетки' if saved else 'Проверяем подготовку сетки; текст обрабатывается отдельно'
    done, total = sum(completed), len(completed)
    percent = round(100 * done / total)
    if row.get('status') in {'pending', 'running', 'waiting'}: percent = min(percent, 99)
    return {'done': done, 'total': total, 'percent': percent, 'label': label, 'stages': stages}
