"""Explicit, resumable maintenance of the exact projects in a saved report."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select

from app import models, maintenance_reports as reports, project_pages as pages
from app import auto_reglue as auto, cross_reglue as cross, project_network as network
from app.domain_classification import classify_domains
from app.domain_transfer_policy import banned_domains, domain_key, geo_key, policy_key, blocked_transfer_zone
from app.network_state import alternate_links, is_project_identity, state_revision

TERMINAL = {'completed', 'partial', 'failed', 'skipped'}
MAX_NETWORK_ATTEMPTS = 2


def now():
    return datetime.now(timezone.utc)


def operation_id(job_id, site_id, action):
    return str(uuid5(UUID(str(job_id)), str(site_id) + ':maintenance-repeat:' + action))


def network_run_id(job_id, site_id, attempt=1):
    if type(attempt) is not int or not 1 <= attempt <= MAX_NETWORK_ATTEMPTS:
        raise ValueError('Допускаются не более двух попыток создания поддомена.')
    return operation_id(job_id, site_id, 'network' if attempt == 1 else 'network:' + str(attempt))


def terminal_provisioning(operation):
    saved = (operation.request_payload or {}).get('provisioning_result') or {}
    return bool(saved.get('job_id') and saved.get('job_id') == operation.request_payload.get('job_id')
        and saved.get('action') == operation.action and (saved.get('job') or {}).get('state') in {'completed', 'failed'})


def is_repeat(job):
    return bool(job and job.kind == reports.KIND and job.payload.get('repeat') is True)


def create(db, report_id, request_id, user, allow_reserve=False):
    parent = reports.get(db, report_id, user)
    if parent.payload.get('task_type') == 'brand_health_audit':
        raise ValueError('Это отчёт проверки доступности. Переклей и рерайт из него не запускаются.')
    request_id = str(UUID(str(request_id)))
    with network.network_lock(db, 'maintenance-repeat:' + request_id):
        existing = db.get(models.BackgroundJob, request_id)
        if existing:
            if (not is_repeat(existing) or existing.payload.get('actor') != user['username']
                    or existing.payload.get('parent_report_id') != parent.id
                    or existing.payload.get('allow_reserve') != allow_reserve
                    or existing.payload.get('site_ids') != parent.payload['site_ids']):
                raise network.NetworkConflict('Идентификатор повторения уже использован для другой задачи.')
            return existing
        ids = list(parent.payload['site_ids'])
        if not ids:
            raise ValueError('В отчёте нет проектов для повторения.')
        rows = (parent.result or {}).get('entries', [])
        if {row.get('site_id') for row in rows} != set(ids) or any(row.get('status') not in TERMINAL for row in rows):
            raise network.NetworkConflict('Дождитесь завершения всех проектов исходного отчёта перед повторением.')
        if db.scalar(select(models.AutoReglueRun.id).where(models.AutoReglueRun.site_id.in_(ids), models.AutoReglueRun.status.in_(auto.ACTIVE)).limit(1)):
            raise network.NetworkConflict('В группе ещё выполняется переклей. Дождитесь завершения операций.')
        if any(not terminal_provisioning(op) for op in db.scalars(select(models.NetworkOperation).where(
                models.NetworkOperation.site_id.in_(ids), models.NetworkOperation.status.in_(['pending', 'unknown'])))):
            raise network.NetworkConflict('В группе есть неподтверждённая операция Webdev. Дождитесь её результата.')
        from app.short_h1 import allocate
        job = models.BackgroundJob(id=request_id, kind=reports.KIND, status='queued', payload={
            'repeat': True, 'parent_report_id': parent.id, 'actor': user['username'],
            'site_ids': ids, 'allowed_site_ids': user.get('allowed_site_ids'), 'allow_reserve': allow_reserve,
            'short_h1_site_ids': allocate(ids, request_id),
            'name': 'Повтор · ' + parent.payload['name'] + ' · ' + now().strftime('%d.%m.%Y %H:%M UTC'),
        }, result={'entries': [{'site_id': site_id,
            'project': (db.get(models.Site, site_id).name if db.get(models.Site, site_id) else site_id),
            'status': 'pending', 'phase': 'snapshot', 'message': 'Ожидает обработки.'} for site_id in ids], 'cursor': 0})
        db.add(job); db.commit()
        return job


def entry_for(job, site_id):
    return next((row for row in (job.result or {}).get('entries', []) if row['site_id'] == site_id), None)


def manual_allowed(db, site_id, run=None):
    if not run or not run.plan.get('maintenance_repeat_id'):
        return False
    job = db.get(models.BackgroundJob, run.plan['maintenance_repeat_id'])
    row = entry_for(job, site_id) if is_repeat(job) else None
    saved = (row or {}).get('plan') or {}
    try: expected_id = network_run_id(job.id, site_id, (row or {}).get('network_attempt', 1)) if job else None
    except ValueError: return False
    if row and row.get('network_attempt', 1) == 2:
        attempts = row.get('network_attempts', [])
        previous = db.get(models.AutoReglueRun, network_run_id(job.id, site_id))
        if (len(attempts) != 1 or attempts[0].get('run_id') != getattr(previous, 'id', None)
                or not dns_failure_receipt(db, previous) or run.plan.get('new_main') == previous.plan.get('new_main')
                or run.plan.get('parent_domain') != previous.plan.get('parent_domain')):
            return False
    return bool(is_repeat(job) and job.status == 'queued' and site_id in job.payload.get('site_ids', [])
        and run.site_id == site_id and run.initiator == job.payload['actor']
        and run.id == expected_id
        and row and row.get('run_id') == run.id and saved
        and row.get('status') not in TERMINAL
        and all(run.plan.get(key) == value for key, value in saved.items())
        and run.plan.get('source_site_id') == site_id)


def parent_allowed(db, site, state, plan):
    """The explicit repeat permits the current parent, never another GEO ban."""
    parent = plan.get('parent_domain')
    if not parent or not plan.get('repeat_parent_reason'):
        return False
    job_id = plan.get('maintenance_repeat_id')
    if not job_id:
        return False
    job = db.get(models.BackgroundJob, job_id)
    entry = entry_for(job, site.id) if is_repeat(job) else None
    run = db.get(models.AutoReglueRun, entry['run_id']) if entry and entry.get('run_id') else None
    if not manual_allowed(db, site.id, run) or run.plan.get('parent_domain') != parent:
        return False
    old = plan.get('old_main')
    expected = classify_domains([*state['domains'], old], site.domain_types or {}).get(old, {})
    expected_parent = expected.get('parent_domain') if expected.get('is_subdomain') else old
    if domain_key(parent) != domain_key(expected_parent) or blocked_transfer_zone(parent):
        return False
    policy = db.get(models.AutoReglueConfig, policy_key(parent))
    return not (policy and geo_key(site.cache_geo) in policy.value.get('banned_geos', []))


def check_site(db, site, job, row):
    if not site or not site.is_active or site.hidden_from_projects or site.reglue_participation is False:
        raise ValueError('Проект исключён из обработки или недоступен.')
    allowed = job.payload.get('allowed_site_ids')
    if allowed is not None and site.id not in allowed:
        raise ValueError('Проект больше не входит в разрешённую группу.')
    if site.project_status != 'mass_actions' or auto.config(db, site.id).scope == 'personal':
        raise ValueError('Проект исключён из массовых действий.')
    active = auto.active_run(db, site.id)
    if active and active.id != row.get('run_id'):
        raise network.NetworkConflict('В проекте ещё выполняется другой переклей.')


def live(db, site):
    with network.Remote(db, site) as remote:
        project = remote.project()
    state = network.observe(db, site, project)
    state['revision'] = state_revision(state)
    home = [page for page in pages.pages(project) if pages.is_home(page)]
    if len(home) != 1:
        raise ValueError('Webdev не вернул единственную главную страницу.')
    db.commit()
    return state, home[0]


def snapshot_values(state, page):
    return {**reports.page_values(page), 'main': state['canon'],
            'alternates': state.get('alternateMarkup') or '',
            'canonical': state.get('canonicalFakeMainMarkup') or '',
            'fake_main_path': state.get('fake_main_current')}


def snapshot(db, site, job, row):
    state, page = live(db, site)
    row.update(before=snapshot_values(state, page), phase='generate',
        status='running', started_at=now().isoformat(), message='Переписываем контент и метаданные.')
    # Save the concrete network proposal before the slow AI work. This is a
    # preview only: no AutoReglueRun, reserve claim or Webdev write is created.
    row['network_plan_version'] = 1
    try:
        row.update(plan=build_network_plan(db, site, job, row, state),
                   network_plan_status='ready', network_planned_at=now().isoformat(), network_error=None)
    except (ValueError, network.NetworkConflict) as error:
        row.update(network_plan_status='failed', network_error=str(error)[:2000])
    provider = db.scalar(select(models.AiProvider).where(models.AiProvider.is_active.is_(True),
        models.AiProvider.provider_type == 'gemini').order_by(models.AiProvider.created_at, models.AiProvider.id))
    if not provider or not provider.api_key:
        raise ValueError('Не настроен активный провайдер Gemini для переписывания страницы.')
    draft_id = operation_id(job.id, site.id, 'full-content')
    draft = db.get(models.ProjectPageDraft, draft_id)
    if draft is None:
        from app.full_content_document import group_briefs
        editorial = group_briefs(job.payload['site_ids'], job.id)[site.id]
        draft = models.ProjectPageDraft(id=draft_id, site_id=site.id, page_key=pages.page_key(page),
            requested_by=job.payload['actor'], provider_id=provider.id, action='full_content', status='generating',
            input_content=deepcopy(page['content']), input_metadata={'title': page.get('title') or '',
                'description': page.get('description') or '', 'revision': pages.digest(page),
                **editorial,
                **({'short_h1': site.id in job.payload['short_h1_site_ids']} if 'short_h1_site_ids' in job.payload else {})})
        db.add(draft)
    row['draft_id'] = draft.id


def generate(db, site, row):
    draft = db.get(models.ProjectPageDraft, row['draft_id'])
    if not draft or draft.site_id != site.id:
        raise ValueError('Черновик повторения не найден.')
    if draft.status != 'ready':
        if draft.status == 'failed':
            raise ValueError(draft.error or 'Переписывание не завершено.')
        provider = db.get(models.AiProvider, draft.provider_id)
        if not provider or not provider.is_active or provider.provider_type != 'gemini' or not provider.api_key:
            raise ValueError('Провайдер генерации недоступен.')
        from app.full_content_rewrite import generate as rewrite
        try:
            asyncio.run(rewrite(db, draft, site, provider))
        except Exception as error:
            draft.status, draft.error = 'failed', str(error)[:1500]; db.commit()
            raise
    if not (draft.result_metadata or {}).get('meaning_reviewed') or not draft.result_content:
        raise ValueError('Не подтверждено сохранение смысла переписанной страницы.')
    row.update(phase='save_content', status='running', message='Сохраняем переписанную страницу.')


def save_content(db, site, job, row):
    draft = db.get(models.ProjectPageDraft, row['draft_id'])
    edit_id = operation_id(job.id, site.id, 'save-content')
    row['edit_ids'] = [edit_id]
    edit = db.get(models.ProjectPageEdit, edit_id)
    user = {'username': job.payload['actor'], 'allowed_site_ids': job.payload.get('allowed_site_ids')}
    if edit:
        if edit.site_id != site.id or edit.requested_by != user['username'] or edit.page_key != draft.page_key:
            raise ValueError('Операция сохранения принадлежит другой задаче.')
        result = pages.check_edit(site.id, draft.page_key, UUID(edit_id), user, db)
    else:
        metadata = draft.result_metadata or {}
        result = pages.save_page(site.id, draft.page_key, pages.PageEdit(request_id=UUID(edit_id),
            revision=draft.input_metadata['revision'], title=metadata['title'], description=metadata['description'],
            content=draft.result_content), user, db)
    if result['status'] == 'failed':
        raise ValueError(result.get('error') or 'Webdev отклонил обновление страницы.')
    if result['status'] != 'confirmed':
        row.update(status='waiting', message='Ждём подтверждения страницы; повторная запись не отправляется.')
        return
    edit = db.get(models.ProjectPageEdit, edit_id)
    row.update(phase='plan', status='running', content_confirmed=True,
        after={**row.get('after', {}), **reports.page_values(edit.after_page)},
        message='Текст сохранён. Проверяем ранее подготовленный план сетки.')
    changes = (draft.result_metadata or {}).get('paragraph_changes')
    if (isinstance(changes, dict) and isinstance(changes.get('added_ids'), list)
            and isinstance(changes.get('removed_ids'), list)):
        row.update(paragraph_changes=deepcopy(changes), paragraphs_added=len(changes['added_ids']),
                   paragraphs_removed=len(changes['removed_ids']))


def parent_available(db, site, parent):
    if blocked_transfer_zone(parent):
        return False
    policy = db.get(models.AutoReglueConfig, policy_key(parent))
    if policy and geo_key(site.cache_geo) in policy.value.get('banned_geos', []):
        return False
    # Current Main may be the Webdev project identity. This exception concerns
    # its new child only, never promotion/deletion of the protected root itself.
    return not banned_domains(db, site, [parent])[parent] or is_project_identity(site, parent)


def new_child(db, site, state, parent, cfg, *, excluded=(), allocation_plans=()):
    from app.subdomain_naming import next_subdomain
    kind = (site.domain_types or {}).get(parent)
    if kind not in {'newreg', 'drop'} or parent not in state['domains'] or parent in state.get('amp_domains', []) or not parent_available(db, site, parent):
        raise ValueError('Родитель недоступен для создания нового поддомена.')
    occupied = {domain for other in db.scalars(select(models.Site)) for domain in (other.cache_domains or [])}
    occupied.update(excluded)
    occupied.update(plan.get('new_main') for plan in allocation_plans)
    occupied.update(run.plan.get('new_main') for run in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.status.in_(auto.ACTIVE))))
    naming = SimpleNamespace(id=site.id, name=site.name, brand=site.brand, cache_geo=geo_key(site.cache_geo),
        cache_language=site.cache_language, cache_domains=[*state['domains'], *filter(None, occupied)],
        domain_types=site.domain_types or {}, main_domain_history=site.main_domain_history or [],
        alternate_domain_history=site.alternate_domain_history or [])
    options = SimpleNamespace(parent_kind=kind, language=site.cache_language or '',
        subdomain_add_casino=cfg.domain_settings.subdomain_add_casino,
        subdomain_name_style=cfg.domain_settings.subdomain_name_style)
    from app.naming_variants import allocation_index
    child = next_subdomain(naming, state, options, parent,
                          allocation_index=allocation_index(allocation_plans, site.id, subdomains=True))
    cross.unique_membership(db, child, {site.id})
    return {'domain': child, 'kind': kind, 'parent': parent}


def choose_target(db, site, state, cfg, allow_reserve, *, allocation_plans=()):
    from app import reglue_reserves as stock
    from app.mass_main_targets import require_target, target_kind
    roles = classify_domains(state['domains'], site.domain_types or {})
    current = roles.get(state['canon'], {})
    if current.get('is_subdomain'):
        return {**new_child(db, site, state, current['parent_domain'], cfg, allocation_plans=allocation_plans), 'reason': 'same_parent'}
    for domain in state['domains']:
        if target_kind(site, state, domain) != 'newreg':
            continue
        try:
            require_target(db, site, state, {'new_main': domain, 'main_target_kind': 'newreg'})
            cross.unique_membership(db, domain, {site.id})
        except ValueError:
            continue
        return {'domain': domain, 'kind': 'newreg'}
    if allow_reserve:
        used = {plan.get('new_main') for plan in allocation_plans}
        row = stock.candidate(db, site, state, ['newreg'], used=used) or stock.candidate(db, site, state, ['drop'], used=used)
        if row:
            try:
                cross.require_import_for_plan(db, site, state, {})
            except ValueError:
                pass
            else:
                return {'domain': row.domain, 'kind': row.domain_type, 'reserve_pool_id': row.id}
    return {**new_child(db, site, state, state['canon'], cfg, allocation_plans=allocation_plans), 'reason': 'current_main'}


def signature(markup, main, path):
    result = []
    for link in alternate_links(markup or ''):
        href = link['href'].replace('{{settings.canon}}', main).replace('{{reqPath}}', path or '/')
        target = 'internal' if path and href == 'https://' + main + path else 'root' if href.rstrip('/') == 'https://' + main else 'other-root'
        result.append((link['hreflang'].lower(), target))
    return sorted(result)


def build_network_plan(db, site, job, row, state):
    """Prepare a reproducible proposal without claiming or executing anything."""
    from app import pilot_schemes
    from app.fake_path_allocation import group_lock, require_available
    attempt = row.get('network_attempt', 1)
    cfg = auto.config(db)
    fixed = [entry['plan'] for entry in (job.result or {}).get('entries', [])
             if entry.get('plan') and entry.get('site_id') != site.id]
    with network.network_lock(db, 'reglue-reserve-pool'), network.network_lock(db, site.id), group_lock(db, site):
        if attempt > 1:
            previous = row.get('network_attempts', [])
            if len(previous) != 1 or previous[0].get('run_id') != network_run_id(job.id, site.id):
                raise ValueError('Не найдена подтверждённая первая попытка создания поддомена.')
            failed = db.get(models.AutoReglueRun, previous[0]['run_id'])
            if not dns_failure_receipt(db, failed) or state['canon'] != failed.plan['old_main']:
                raise ValueError('Условия повторной попытки изменились. Новый переклей не запущен.')
            target = {**new_child(db, site, state, failed.plan['parent_domain'], cfg,
                                 excluded=[failed.plan['new_main']], allocation_plans=fixed), 'reason': failed.plan['repeat_parent_reason']}
        else:
            target = choose_target(db, site, state, cfg, job.payload['allow_reserve'], allocation_plans=fixed)
        before_info = dict(db.info)
        try:
            db.info.update(auto_pilot_preview=True, canonical_allocation_plans=fixed)
            plan = cross.make_plan(cfg.model_copy(update={'scheme_mode': 'locale_base'}), site, state, site, state,
                target['domain'], mode='maintenance_repeat', db=db, plans=fixed)
        finally:
            db.info.clear(); db.info.update(before_info)
        kind = target['kind']; parent = target.get('parent')
        plan.update(local_target=True, requires_newreg=False, domain_type=kind, required_domain_type=kind,
            main_target_kind=('sub_' if parent else '') + kind, maintenance_repeat_id=job.id,
            maintenance_attempt=attempt,
            config_hash=auto.digest(cfg.model_dump()), rewrite_title_h1=False, rewrite_paragraphs=False,
            redirect_old_main=False, without_alternates=False, pilot_variation_version=1)
        if parent:
            plan.update(parent_domain=parent, create_subdomain=target['domain'], repeat_parent_reason=target['reason'])
        if target.get('reserve_pool_id'):
            plan.update(reserve_pool_id=target['reserve_pool_id'], source_project='База резервов')
        pilot_schemes.assign(db, [plan], fixed=fixed)
        if signature(plan['alternateMarkup'], plan['new_main'], plan['fake_main_path']) == signature(state['alternateMarkup'], state['canon'], state.get('fake_main_current')):
            pilot_schemes.assign(db, [plan], fixed=fixed, exclude={site.id: plan['scheme_variant']})
        if signature(plan['alternateMarkup'], plan['new_main'], plan['fake_main_path']) == signature(state['alternateMarkup'], state['canon'], state.get('fake_main_current')):
            raise ValueError('Не удалось подобрать отличающуюся схему альтернейтов.')
        require_available(db, site, plan['fake_main_path'], fixed)
        plan.pop('preview_token', None); plan['preview_token'] = auto.digest(plan)
        return plan


def plan_network(db, site, job, row):
    from app import reglue_reserves as stock
    from app.fake_path_allocation import group_lock, require_available
    state, current = live(db, site)
    edit = db.get(models.ProjectPageEdit, row['edit_ids'][0])
    if (not edit or edit.site_id != site.id or edit.requested_by != job.payload['actor']
            or edit.status != 'confirmed' or pages.editable(current) != pages.editable(edit.after_page)):
        raise ValueError('Страница изменилась после сохранения. Новый переклей не запущен.')
    attempt = row.get('network_attempt', 1)
    run_id = network_run_id(job.id, site.id, attempt)
    existing = db.get(models.AutoReglueRun, run_id)
    if existing:
        if existing.plan.get('maintenance_repeat_id') != job.id or existing.initiator != job.payload['actor']:
            raise ValueError('Идентификатор переклея занят другой задачей.')
        row.update(run_id=run_id, plan=deepcopy(existing.plan), phase='execute', status='running')
        return
    fixed = [entry['plan'] for entry in (job.result or {}).get('entries', [])
             if entry.get('plan') and entry.get('site_id') != site.id]
    with network.network_lock(db, 'reglue-reserve-pool'), network.network_lock(db, site.id), group_lock(db, site):
        if row.get('network_plan_version') and attempt == 1:
            plan = deepcopy(row.get('plan') or {})
            if not plan:
                raise ValueError(row.get('network_error') or 'План сетки не подготовлен. Текст сохранён; требуется новое планирование.')
            token = plan.pop('preview_token', None)
            if (token != auto.digest(plan) or plan.get('site_id') != site.id
                    or plan.get('maintenance_repeat_id') != job.id):
                raise ValueError('Сохранённый план сетки изменён или принадлежит другой задаче.')
            plan['preview_token'] = token
            if plan['revision'] != state['revision'] or plan['config_hash'] != auto.digest(auto.config(db).model_dump()):
                raise ValueError('Сетка или настройки изменились после планирования. Текст сохранён; новый домен автоматически не подбирается.')
            require_available(db, site, plan.get('fake_main_path'), fixed)
            if plan.get('reserve_pool_id'):
                stock.validate_plan(db, site, state, plan)
            elif plan.get('create_subdomain'):
                parent = plan.get('parent_domain')
                if (parent not in state['domains'] or parent in state.get('amp_domains', [])
                        or not parent_available(db, site, parent)
                        or (site.domain_types or {}).get(parent) != plan['required_domain_type']):
                    raise ValueError('Родитель запланированного поддомена больше не доступен.')
                cross.unique_membership(db, plan['new_main'], {site.id})
            else:
                from app.mass_main_targets import require_target
                require_target(db, site, state, plan)
                cross.unique_membership(db, plan['new_main'], {site.id})
        else:
            # Existing reports and the explicitly bounded second attempt keep
            # their established path. A new first attempt always uses its preview.
            plan = build_network_plan(db, site, job, row, state)
        run = models.AutoReglueRun(id=run_id, site_id=site.id, initiator=job.payload['actor'],
            plan=deepcopy(plan), status='queued', phase='prepared')
        db.add(run); db.flush()
        if plan.get('reserve_pool_id'):
            stock.claim(db, run)
        row.update(run_id=run_id, plan=deepcopy(plan), phase='execute', status='running',
            message='Страница сохранена. Выполняем переклей на ' + plan['new_main'] + '.',
            fake_path_note='Замена внутренней страницы на уникальную.')


def execute_network(db, site, job, row):
    run = db.get(models.AutoReglueRun, row['run_id'])
    if not run or not manual_allowed(db, site.id, run):
        raise ValueError('Переклей не связан с этой задачей повторения.')
    if run.phase == 'prepared':
        _, page = live(db, site)
        edit = db.get(models.ProjectPageEdit, row['edit_ids'][0])
        if not edit or pages.editable(page) != pages.editable(edit.after_page):
            raise ValueError('Страница изменилась после подготовки переклея. Сторонние правки сохранены; переклей не запущен.')
    if run.status not in {'completed', 'partial', 'failed', 'cancelled'}:
        auto.execute(db, run.id)
    row['network_status'] = run.status
    run_ids = {run.id, *[attempt['run_id'] for attempt in row.get('network_attempts', [])]}
    row['network_operations'] = [{'id': op.id, 'kind': op.action, 'status': op.status,
        'run_id': op.request_payload.get('auto_run_id'),
        'started_at': reports.timestamp(op.created_at), 'finished_at': reports.timestamp(op.updated_at)}
        for op in db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id))
        if (op.request_payload or {}).get('auto_run_id') in run_ids]
    if run.status == 'completed':
        state, page = live(db, site)
        edit = db.get(models.ProjectPageEdit, row['edit_ids'][0])
        if state['canon'] != run.plan['new_main'] or pages.editable(page) != pages.editable(edit.after_page):
            raise ValueError('Итоговые Main или контент не совпали с подтверждённой задачей.')
        record_attempt(db, row, run)
        row.update(status='completed', phase='completed', after=snapshot_values(state, page),
            finished_at=now().isoformat(), message='Контент, метаданные, новый Main и альтернейты подтверждены.'
                + (' Поддомен создан со второй попытки; первая завершилась ошибкой DNS.' if row.get('network_attempt', 1) == 2 else ''), error=None)
    elif run.status in {'partial', 'failed', 'cancelled'}:
        receipt = dns_failure_receipt(db, run)
        record_attempt(db, row, run, dns_receipt=receipt)
        if receipt:
            state, page = live(db, site)
            edit = db.get(models.ProjectPageEdit, row['edit_ids'][0])
            if state['canon'] == run.plan['old_main'] and edit and pages.editable(page) == pages.editable(edit.after_page):
                # Close this failed provisioning attempt, freeing the project's
                # active-run lock. Its remote receipt and observed errors stay intact.
                run.status = 'failed'
                retry = row.get('network_attempt', 1) < MAX_NETWORK_ATTEMPTS
                run.plan = {**run.plan, 'maintenance_retry': {
                    'next_run_id': network_run_id(job.id, site.id, 2) if retry else None,
                    'reason': 'terminal_dns_failure', 'attempts_exhausted': not retry,
                    'main_verified': state['canon'], 'checked_at': now().isoformat()}}
                record_attempt(db, row, run, dns_receipt=receipt)
                db.commit()
                if retry:
                    row.update(network_attempt=2, phase='plan', status='running',
                        message='Первая попытка завершилась ошибкой DNS. Подготавливаем другой поддомен: попытка 2 из 2.')
                    return
        raise ValueError(run.message or 'Переклей не завершён.')
    else:
        row.update(status='waiting', message=run.message or 'Ждём подтверждения переклея.')


def dns_failure_receipt(db, run):
    """Only an observed, terminal DNS-only provisioning failure permits a retry."""
    if (not run or run.status not in {'partial', 'failed'} or run.phase != 'cross_create_subdomains'
            or not run.plan.get('create_subdomain') or run.plan['create_subdomain'] != run.plan.get('new_main')):
        return None
    operation = db.get(models.NetworkOperation, cross.receipt_id(run, 'create_subdomains'))
    if not operation or operation.site_id != run.site_id or operation.action != 'create_subdomains': return None
    payload = operation.request_payload or {}
    saved = payload.get('provisioning_result') or {}
    job = saved.get('job') or {}; result = job.get('result') or {}
    domains = result.get('domains') or job.get('domains') or []
    if (not terminal_provisioning(operation) or payload.get('auto_run_id') != run.id
            or job.get('state') != 'completed' or job.get('error')
            or result.get('successCount') != 0 or result.get('errorCount') != 1
            or len(domains) != 1 or domains[0].get('domain') != run.plan['new_main']
            or domains[0].get('status') != 'error' or domains[0].get('failedStage') != 'dns'
            or {item.get('domain') for item in payload.get('domains', []) if isinstance(item, dict)} != {run.plan['new_main']}):
        return None
    # Never repeat a provisioning request after any downstream mutation began,
    # even if its receipt is uncertain and the observed Main happens to match.
    if any(db.get(models.NetworkOperation, cross.receipt_id(run, action))
           for action in ('create_fake_main', 'reserve', 'reglue', 'alternates')):
        return None
    return operation


def record_attempt(db, row, run, *, dns_receipt=None):
    attempts = [attempt for attempt in row.get('network_attempts', []) if attempt['run_id'] != run.id]
    attempts.append({'attempt': run.plan.get('maintenance_attempt', row.get('network_attempt', 1)),
        'run_id': run.id, 'new_main': run.plan.get('new_main'), 'parent_domain': run.plan.get('parent_domain'),
        'status': run.status, 'message': run.message, 'finished_at': reports.timestamp(run.updated_at),
        **({'failure_stage': 'dns', 'operation_id': dns_receipt.id,
            'provisioning_result': deepcopy(dns_receipt.request_payload['provisioning_result'])} if dns_receipt else {})})
    row['network_attempts'] = attempts


def persist(db, job, entries, cursor):
    job.result = {'entries': entries, 'cursor': cursor}
    if all(row['status'] in TERMINAL for row in entries):
        job.status = ('completed' if all(row['status'] in {'completed', 'skipped'} for row in entries)
                      else 'partial' if any(row['status'] in {'completed', 'partial'} for row in entries) else 'failed')
        job.finished_at = now()
    elif any(row['status'] in {'pending', 'running'} for row in entries):
        job.dispatched_at = None
    db.commit()


def execute_step(db, job_id):
    try:
        with network.network_lock(db, 'maintenance-repeat:' + str(job_id)):
            job = db.get(models.BackgroundJob, str(job_id))
            if not is_repeat(job) or job.status != 'queued':
                return {'status': 'skipped'}
            if not job.started_at:
                job.started_at = now(); db.commit()
            entries = deepcopy(job.result['entries']); size = len(entries)
            start = job.result.get('cursor', 0) % size
            index = next((i % size for i in range(start, start + size) if entries[i % size]['status'] not in TERMINAL), None)
            if index is None:
                persist(db, job, entries, start)
                return {'status': job.status}
            row = entries[index]; site = db.get(models.Site, row['site_id'])
            try:
                check_site(db, site, job, row)
                phase = row.get('phase', 'snapshot')
                if phase == 'snapshot': snapshot(db, site, job, row)
                elif phase == 'generate': generate(db, site, row)
                elif phase == 'save_content': save_content(db, site, job, row)
                elif phase == 'plan': plan_network(db, site, job, row)
                elif phase == 'execute': execute_network(db, site, job, row)
                else: raise ValueError('Неизвестный этап повторения.')
            except network.NetworkConflict as error:
                row.update(status='waiting', message=str(error))
            except Exception as error:
                db.rollback(); db.refresh(job)
                edit = db.get(models.ProjectPageEdit, operation_id(job.id, row['site_id'], 'save-content'))
                confirmed = bool(edit and edit.status == 'confirmed')
                row.update(status='partial' if confirmed else 'failed', error=str(getattr(error, 'detail', error))[:2000],
                    message='Обработка остановлена; подтверждённые изменения сохранены.' if confirmed else 'Обработка не завершена.',
                    finished_at=now().isoformat())
                if edit:
                    row['edit_ids'] = [edit.id]
                run = db.get(models.AutoReglueRun, row.get('run_id') or network_run_id(job.id, row['site_id'], row.get('network_attempt', 1)))
                if run and run.plan.get('maintenance_repeat_id') == job.id and run.status not in {'completed', 'partial', 'failed', 'cancelled'}:
                    operations = [op for op in db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == row['site_id']))
                                  if (op.request_payload or {}).get('auto_run_id') == run.id]
                    run.status = 'partial' if operations else 'failed'
                    run.message = row['error']
                    if run.plan.get('reserve_pool_id'):
                        from app.reglue_reserves import sync_result
                        sync_result(db, run)
            persist(db, job, entries, (index + 1) % size)
            return {'status': job.status}
    except network.NetworkConflict:
        db.rollback()
        return {'status': 'busy'}
