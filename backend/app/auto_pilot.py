"""Saved Auto Pilot previews and execution of the exact reviewed allocation."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app import models, auto_reglue as auto, mass_reglue_launch as launch
from app.project_network import NetworkConflict, network_lock
from app.reglue_history import utc
from app.pilot_scope import selection, country_key, PilotScopeError


def describe(db, plan):
    site = db.get(models.Site, plan['site_id'])
    kind = plan.get('domain_type') or plan.get('main_target_kind') or plan.get('required_domain_type')
    source = db.get(models.Site, plan.get('source_site_id', plan['site_id']))
    if not kind and source: kind = (source.domain_types or {}).get(plan.get('new_main'))
    label = {'drop': 'Дроп', 'newreg': 'Новорег', 'drop_subdomain': 'Поддомен дропа', 'newreg_subdomain': 'Поддомен новорега'}.get(kind, 'Домен')
    if plan.get('create_subdomain') and not label.startswith('Поддомен'): label = 'Поддомен ' + {'drop':'дропа','newreg':'новорега'}.get(kind, 'домена')
    origin = 'из базы резервов' if plan.get('reserve_pool_id') else 'из своей сетки' if not source or source.id == plan['site_id'] else 'из другой сетки'
    fake = plan.get('fake_main_path') or plan.get('create_fake_main_path')
    alternates = plan.get('alternateMarkup', plan.get('alternates_after', {}).get('markup', ''))
    enabled = plan.get('enableAlternates', plan.get('alternates_after', {}).get('enabled', True))
    canonical = plan.get('canonicalFakeMainMarkup') or ((site.network_state or {}) if site else {}).get('canonicalFakeMainMarkup') or ''
    parts = [f'{label} {origin}', f'внутряк {fake}' if fake else 'без нового внутряка', 'с альтернейтами' if enabled and alternates else 'без альтернейтов']
    if canonical:
        from app.canonical_allocation import mode
        parts.append('каноникал на внутряк' if mode(canonical, fake) == 'internal' else 'каноникал на себя')
    if plan.get('redirect_old_main'): parts.append('301 со старого Main')
    if plan.get('rewrite_title_h1'):
        from app.pilot_variations import TITLE_REWRITE_LABELS
        parts.append(TITLE_REWRITE_LABELS.get(plan.get('title_rewrite_mode', 'minimal'), 'обновление Title, H1'))
    if plan.get('rewrite_paragraphs'): parts.append('переписывание абзацев главной страницы')
    internal_pages = plan.get('internal_pages') or {}
    if internal_pages.get('enabled'):
        parts.append(f"{internal_pages['count']} внутренних страниц: меню в один уровень, генерация и автопубликация")
    before = plan.get('alternates_before', {}).get('markup', '')
    if not plan.get('alternates_before', {}).get('enabled', True): before = ''
    def resolved(markup, main):
        return (markup or '').replace('{{settings.canon}}', main or '').replace('{{reqPath}}', '/')
    return {'title_rewrite_mode':plan.get('title_rewrite_mode', 'minimal'), 'paragraphs_preview':plan.get('paragraphs_preview'), 'paragraphs_error':plan.get('paragraphs_error'), 'rewrite_paragraphs':bool(plan.get('rewrite_paragraphs')), 'emergency_subdomain':bool(plan.get('emergency_subdomain')), 'title_h1_current':plan.get('title_h1_current'), 'title_h1_preview':plan.get('title_h1_preview'), 'title_h1_error':plan.get('title_h1_error'), 'old_main':plan.get('old_main'), 'new_main':plan.get('new_main'), 'source_project':plan.get('source_project') or (source.name if source else plan.get('project')),
            'title_h1_reused':bool(plan.get('title_h1_reused')), 'combination_id':plan.get('combination_id'), 'combination_settings':deepcopy(plan.get('combination_settings')), 'combination_history':deepcopy(plan.get('combination_history')),
            'scheme':'; '.join(parts), 'fake_path':fake, 'internal_pages':deepcopy(internal_pages) or None,
            'internal_pages_eligibility':deepcopy(plan.get('internal_pages_eligibility')),
            'new_fake_path':fake if plan.get('create_fake_main_path') and fake!=(plan.get('old_fake_main_path') or (plan.get('target_guard',{}).get('fake_main_settings') or {}).get('currentFakeMain')) else None,
            'canonical':canonical, 'alternate':resolved(alternates, plan.get('new_main')) if enabled else '',
            'alternate_before':resolved(before, plan.get('old_main')), 'alternate_markup':alternates if enabled else '', 'alternates_enabled':bool(enabled), 'scheme_mode':plan.get('scheme_mode')}


def deleted(db, job_id):
    marker = db.get(models.AutoReglueConfig, launch.cancel_key(job_id))
    return bool(marker and marker.value.get('deleted'))


def get(db, job_id, user, *, include_deleted=False):
    job = db.get(models.BackgroundJob, str(job_id))
    if not job or job.kind not in (launch.PREVIEW_KIND,launch.KIND) or job.payload.get('actor') != user['username'] or (not include_deleted and deleted(db, job_id)):
        raise ValueError('План Auto Pilot не найден.')
    allowed = user.get('allowed_site_ids')
    ids = set(job.payload.get('original_site_ids', job.payload['site_ids'])) | {p.get('source_site_id',p['site_id']) for g in job.result['groups'] for p in g.get('plans',[])}
    if allowed is not None and not ids.issubset(allowed): raise ValueError('Часть проектов плана больше недоступна.')
    return job


def delete_draft(db, job_id, user):
    # Share the start lock, but let the planner reach its next cancellation checkpoint.
    # Keeping a separate tombstone prevents an in-flight worker from restoring the draft.
    with network_lock(db, 'mass-reglue-list-start'):
        job = get(db, job_id, user, include_deleted=True)
        db.refresh(job)
        if job.kind != launch.PREVIEW_KIND:
            raise NetworkConflict('Можно удалить только черновик. История запусков сохраняется.')
        key = launch.cancel_key(job.id)
        marker = db.get(models.AutoReglueConfig, key)
        if not marker:
            marker = models.AutoReglueConfig(key=key, value={})
            db.add(marker)
        if not marker.value.get('deleted'):
            marker.value = {**marker.value, 'deleted': True, 'deleted_at': datetime.now(timezone.utc).isoformat()}
            job.status = 'cancelled'
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        return {'id': job.id, 'deleted': True}


def draft_name(job):
    if job.payload.get('draft_name'):
        return job.payload['draft_name']
    scope = selection(job.payload.get('planning_filter') or {})
    count = len(job.payload.get('site_ids', []))
    if not scope.brands and not scope.geos:
        return f'Все проекты · {count}'
    created = job.created_at or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    date = created.astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y')
    prefix = 'Исключены: ' if scope.scope_mode == 'exclude' else ''
    return f"{prefix}{', '.join(scope.brands) or 'Все бренды'} · {', '.join(scope.geos) or 'Все ГЕО'} · {count} проектов · {date}"


def tasks(db, user, offset=0, limit=50, *, q='', group='all'):
    """Saved drafts and launches; reading never creates or dispatches work."""
    from app import maintenance_reports, report_ids
    numbers = report_ids.ensure(db)
    from app.report_list_visibility import hidden_ids
    hidden = hidden_ids(db, user['username'])
    visible=[]
    query=select(models.BackgroundJob).where(models.BackgroundJob.kind.in_([launch.PREVIEW_KIND, launch.KIND, maintenance_reports.KIND]),
        models.BackgroundJob.payload['actor'].as_string()==user['username']).order_by(models.BackgroundJob.created_at.desc(),models.BackgroundJob.id.desc())
    for job in db.scalars(query):
        if job.id in hidden: continue
        if job.payload.get('task_type') == 'project_state_report': continue
        try:
            if job.kind == maintenance_reports.KIND: maintenance_reports.get(db, job.id, user)
            else: get(db,job.id,user)
        except ValueError:continue
        visible.append(job)
    from app.pilot_task_search import order_and_filter
    visible = order_and_filter(db, visible, q, numbers)
    from app.pilot_report_groups import partition, group as report_group
    visible, group_counts = partition(visible, group)
    items=[]
    for job in visible[offset:offset+limit if limit is not None else None]:
        if job.kind == maintenance_reports.KIND:
            items.append({**maintenance_reports.summary(job), 'report_id': numbers[job.id], 'group': report_group(job)})
            continue
        snapshot=launch.view(db,job)
        from app.pilot_internal_pages import snapshot as pages_snapshot, merge_row, plan_options
        inner_plans = plan_options(job)
        for row in snapshot['items']:
            if row['site_id'] in inner_plans:
                merge_row(row, pages_snapshot(db, job.id, row['site_id'], inner_plans[row['site_id']]))
        snapshot['counts'] = {status:sum(row['status']==status for row in snapshot['items']) for status in snapshot['counts']}
        from app.pilot_internal_pages import report_metadata
        metadata = report_metadata(db, job)
        visible_status = metadata['status']
        from app.report_status import metadata as status_metadata
        lifecycle = status_metadata(job, status=visible_status, finished_at=metadata['finished_at'])
        items.append({'id':job.id,'group':report_group(job),'report_id':numbers[job.id],'name':draft_name(job),'mode':'preview' if job.kind==launch.PREVIEW_KIND else 'execution','status':visible_status,'created_at':job.created_at,
            'launched_at':job.payload.get('launched_at') or job.started_at or job.created_at,
            'finished_at':metadata['finished_at'],'total':len(snapshot['items']),'counts':snapshot['counts'],**lifecycle})
    return {'items':items,'total':len(visible),'has_more':limit is not None and offset+limit<len(visible),'group_counts':group_counts}


def scope_sites(db, user):
    query = select(models.Site).where(models.Site.is_active.is_(True), models.Site.hidden_from_projects.is_(False), models.Site.project_status == 'mass_actions')
    allowed = user.get('allowed_site_ids')
    if allowed is not None:
        query = query.where(models.Site.id.in_(allowed))
    return list(db.scalars(query))


def scope_brand(site):
    from app.mass_action_scope import brand_key
    return 'Общие ключи' if site.site_type == 'general' or not brand_key(site.brand) else site.brand


def scope_options(db, user):
    from app.domain_transfer_policy import geo_key
    from app.mass_action_scope import brand_key
    sites = scope_sites(db, user)
    brands = {}
    for site in sorted(sites, key=lambda s: (scope_brand(s).casefold(), s.id)):
        brands.setdefault(brand_key(scope_brand(site)), scope_brand(site))
    from collections import Counter
    counts = Counter((brands[brand_key(scope_brand(site))], country_key(site.cache_geo)) for site in sites)
    groups = [{'brand': brand, 'geo': geo, 'count': count} for (brand, geo), count in sorted(counts.items())]
    from app.pilot_variations import percentages
    return {'scope_mode':'include', 'title_rewrite_mode':'mixed', 'percentages': percentages(db), 'brands': sorted(brands.values()), 'geos': sorted({country_key(site.cache_geo) for site in sites if country_key(site.cache_geo)}), 'groups': groups}


def selected_scope_sites(sites, scope):
    included = [site for site in sites if scope.includes(scope_brand(site), site.cache_geo)]
    if scope.scope_mode == 'exclude':
        remaining_geos = {country_key(site.cache_geo) for site in included}
        empty_geos = [geo for geo in scope.geos if geo not in remaining_geos]
        if empty_geos:
            raise PilotScopeError('Нельзя исключить все проекты GEO ' + ', '.join(empty_geos) + '. Оставьте хотя бы один бренд с доступными проектами в каждом выбранном GEO.')
    return included


def create(db, request_id, user, brand='', geo='', percentages=None, *, brands=None, geos=None, title_rewrite_mode='mixed', scope_mode='include', planning_mode='percentages', allow_stock_drops=True):
    allowed = user.get('allowed_site_ids')
    scope = selection(brand=brand, geo=geo, brands=brands, geos=geos, scope_mode=scope_mode)
    # Retrying the same HTTP request uses its original scope, even if projects changed.
    old = db.get(models.BackgroundJob,str(request_id))
    if old: return get(db,request_id,user)
    from app.pilot_mixed import parameters
    settings = parameters(db, percentages, title_rewrite_mode, planning_mode)
    ids = [site.id for site in selected_scope_sites(scope_sites(db, user), scope)]
    if not ids:
        raise ValueError('Нет проектов для выбранного бренда и GEO.')
    with network_lock(db,'pilot-create:'+user['username']):
        job=launch.enqueue(db,request_id,ids,user['username'],None if allowed is None else set(allowed),preview_only=True)
        job.payload = {**job.payload, 'planning_filter': scope.model_dump(), 'allow_stock_drops':bool(allow_stock_drops), **settings}
        if planning_mode == 'mixed': job.payload = {**job.payload, 'execution_mode':'cross_network'}
        job.payload = {**job.payload, 'draft_name': draft_name(job)}
        db.commit()
        return job


def paragraphs_ready(db, plan):
    if not plan.get('rewrite_paragraphs'):
        return True
    preview = plan.get('paragraphs_preview') or {}
    draft = db.get(models.ProjectPageDraft, preview.get('draft_id')) if preview.get('draft_id') else None
    return bool(not plan.get('paragraphs_error') and draft and draft.site_id == plan['site_id'] and draft.status == 'ready' and (draft.result_metadata or {}).get('meaning_reviewed'))


def heading_mode_ready(db, plan, expected_mode='minimal'):
    """Full modes must reference a reviewed draft for precisely this mode and site."""
    if not plan.get('rewrite_title_h1'):
        return True
    from app.pilot_variations import TITLE_REWRITE_LABELS
    from app.title_brand_prefix import title_prefix_valid
    mode = plan.get('title_rewrite_mode', 'minimal')
    preview = plan.get('title_h1_preview') or {}
    from app.pilot_saved_headings import reused
    if reused(plan):
        expected_mode = mode
    if mode not in TITLE_REWRITE_LABELS or (expected_mode != 'mixed' and mode != expected_mode) or plan.get('title_h1_error') or not title_prefix_valid(preview.get('title_after'),db.get(models.Site,plan['site_id'])):
        return False
    if 'short_h1' in plan:
        from app.reglue_title_h1 import heading_words
        draft = db.get(models.ProjectPageDraft, preview.get('draft_id')) if preview.get('draft_id') else None
        if (preview.get('short_h1') is not plan['short_h1'] or not draft or draft.status!='ready'
                or draft.site_id!=plan['site_id'] or (draft.input_metadata or {}).get('short_h1') is not plan['short_h1']
                or (draft.result_metadata or {}).get('short_h1') is not plan['short_h1']
                or plan['short_h1'] and (not (draft.result_metadata or {}).get('short_h1_reviewed')
                    or not 2<=len(heading_words(preview.get('h1_after','')))<=4)):
            return False
    if mode == 'minimal':
        return bool(preview and preview.get('mode', 'minimal') == mode)
    draft = db.get(models.ProjectPageDraft, preview.get('draft_id')) if preview.get('draft_id') else None
    return bool(preview.get('mode') == mode and draft and draft.site_id == plan['site_id'] and draft.status == 'ready'
                and (draft.input_metadata or {}).get('title_rewrite_mode') == mode
                and (draft.result_metadata or {}).get('title_rewrite_mode') == mode
                and (draft.result_metadata or {}).get('meaning_reviewed'))


def pending_participants(db, job):
    """Historical scope is retained for reporting; only pending work blocks a launch."""
    plans={p['site_id']:p for g in job.result.get('groups',[]) for p in g.get('plans',[])}
    pending=set()
    for sid,row in job.result.get('items',{}).items():
        if row.get('completed_elsewhere'):continue
        run=db.get(models.AutoReglueRun,row['run_id']) if row.get('run_id') else None
        if run:
            if run.status not in auto.ACTIVE:continue
            plan=run.plan
        else:
            if row.get('status') in launch.TERMINAL|{'skipped'}:continue
            plan=plans.get(sid,{})
        pending.update({sid,plan.get('source_site_id',sid)})
    return pending


def start(db, job_id, user):
    with network_lock(db,'mass-reglue-list-start'), network_lock(db,'mass-reglue-list:'+str(job_id)):
        job=get(db,job_id,user)
        if job.kind==launch.KIND: return job
        from app.pilot_replanning import pending
        if pending(db, job.id): raise NetworkConflict('Дождитесь обновления плана.')
        if job.payload.get('planner_version') != launch.PLANNER_VERSION:
            raise NetworkConflict('Порядок подбора доменов обновлён. Обновите план Auto Pilot перед запуском.')
        from app.pilot_text_jobs import independent_start
        streaming = independent_start(job)
        if job.status!='completed' and not streaming: raise NetworkConflict('Дождитесь расчёта доменов и схем переклея.')
        if auto.digest(auto.config(db).model_dump())!=job.payload['config_hash']:
            raise NetworkConflict('Настройки изменились. Обновите предпросмотр Auto Pilot.')
        scope = selection(job.payload.get('planning_filter') or {})
        if scope.scope_mode == 'exclude':
            try: selected_scope_sites(scope_sites(db, user), scope)
            except PilotScopeError as error: raise NetworkConflict(str(error) + ' Обновите план.') from error
        result=deepcopy(job.result)
        from app.pilot_weekly import exclude
        if exclude(db, result, job=job):
            job.result = deepcopy(result); db.commit()
        plans=[p for g in result['groups'] for p in g.get('plans',[])]
        from app.reglue_title_h1 import preview_needs_shortening
        if any(preview_needs_shortening(p) for p in plans):
            raise NetworkConflict('Правило H1 обновлено: обновите длинные H1 в плане перед запуском.')
        if not streaming and any(not heading_mode_ready(db,p,job.payload.get('title_rewrite_mode','minimal')) for p in plans):
            raise NetworkConflict('Не все изменения Title/H1 и заголовков подготовлены для выбранного режима. Исправьте ошибки или обновите план до запуска.')
        if not streaming and any(not paragraphs_ready(db, p) for p in plans):
            raise NetworkConflict('Не все абзацы подготовлены. Исправьте ошибки в строках до запуска.')
        if any(p['site_id'] not in job.payload['site_ids'] or p.get('source_site_id',p['site_id']) in job.payload.get('excluded_site_ids',[]) for p in plans):
            raise NetworkConflict('В плане остался исключённый проект. Обновите план.')
        if job.payload.get('preserved_target_plans') and any(p['new_main'] != job.payload['preserved_target_plans'].get(p['site_id'],{}).get('new_main') for p in plans):
            raise NetworkConflict('Целевой домен отличается от сохранённого выбора. Обновите план.')
        if not job.payload.get('allow_stock_drops',True) and any(p.get('reserve_pool_id') and p.get('domain_type')=='drop' for p in plans):
            raise NetworkConflict('Дропы из хранилища выключены. Пересчитайте план без них.')
        if not plans: raise ValueError('В плане нет проектов, готовых к переклею.')
        from app.pilot_schemes import validate_single_alternate
        for plan in plans:
            try: validate_single_alternate(plan)
            except ValueError as error: raise NetworkConflict(str(error)) from error
        # Multi-selection never makes a shared donor pool across brands or GEOs.
        from app.cross_reglue import require_pair
        from app.mass_action_scope import MassActionFilter, matches
        for group in result['groups']:
            filters = MassActionFilter.model_validate(group['filter'])
            for plan in group.get('plans', []):
                target = db.get(models.Site, plan['site_id'])
                source = db.get(models.Site, plan.get('source_site_id', plan['site_id']))
                from app.pilot_donors import authorized
                for site in (target, source):
                    if site:
                        db.refresh(site)
                    if not site or not matches(site, filters, donor_only=authorized(db, plan, site.id)) or not scope.includes(scope_brand(site), site.cache_geo):
                        raise NetworkConflict('Бренд или GEO проекта изменились. Обновите план.')
                if source.id != target.id:
                    require_pair(source, target)

        domains=[p['new_main'].lower().removeprefix('www.') for p in plans]
        if len(set(domains))!=len(domains): raise NetworkConflict('Домен повторяется в плане. Обновите предпросмотр.')
        participants={sid for plan in plans for sid in (plan['site_id'],plan.get('source_site_id',plan['site_id']))}
        for other in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind==launch.KIND,models.BackgroundJob.status=='queued')):
            if participants.intersection(pending_participants(db,other)): raise NetworkConflict('Часть сеток ещё занята незавершённым переклеем из другого плана.')
        for group in result['groups']:
            if group['status']=='previewed': group['status']='prepared'
        for row in result['items'].values():
            if row['status']=='ready': row['status']='pending'
        job.result=result;job.kind=launch.KIND;job.status='queued';job.started_at=None;job.finished_at=None;job.dispatched_at=None
        job.payload={**job.payload,'allowed':user.get('allowed_site_ids'),'launched_at':datetime.now(timezone.utc).isoformat(),'manual_start':True, **({'streaming_start':True} if streaming else {})}
        from app.pilot_internal_pages import enqueue as enqueue_internal_pages
        enqueue_internal_pages(db, job, user)
        db.commit();return job


PHASE_PROGRESS={'prepared':5,'delete_domain':15,'create_domains':30,'create_subdomains':35,'subdomain_ready':40,'create_fake_main':45,'fake_main_ready':55,'reserve':60,'reglue':75,'alternates':90,'title_h1':95,'paragraphs':97,'completed':100}


def archive_resolved_notes(db, job, user):
    """Close existing notes for completed rows, retaining their full audit trail."""
    job = get(db, job.id, user)
    if job.kind != launch.KIND:
        raise ValueError('Примечания можно закрыть только в отчёте выполнения.')
    closed = []
    at = datetime.now(timezone.utc).isoformat()
    run_ids = {r['run_id'] for r in launch.view(db, job)['items'] if r.get('run_id')}
    for run_id in sorted(run_ids):
        with network_lock(db, 'auto-run:' + run_id):
            run = db.get(models.AutoReglueRun, run_id)
            db.refresh(run)
            if run.status != 'completed':
                continue
            notes = list(run.plan.get('dns_warnings') or [])
            if run.plan.get('backup_note'):
                notes.append({'domain': 'Бэкап', 'message': run.plan['backup_note'], 'checked_at': run.updated_at.isoformat()})
            if not notes:
                continue
            plan = deepcopy(run.plan)
            plan['archived_notes'] = [*plan.get('archived_notes', []),
                *[{**note, 'archived_at': at, 'archived_by': user['username']} for note in notes]]
            plan['dns_warnings'] = []
            plan.pop('backup_note', None)
            run.plan = plan
            db.commit()
            closed.append({'run_id': run.id, 'site_id': run.site_id, 'notes': len(notes)})
    return closed


def confirmed_updates(db, run, alternates_saved=False):
    checks = {c['code']: c['ok'] for c in (run.plan.get('verification') or {}).get('checks', [])}
    preview = run.plan.get('title_h1_preview') or {}
    edit = db.get(models.ProjectPageEdit, str(uuid5(UUID(run.id), 'title-h1-save'))) if run.plan.get('rewrite_title_h1') else None
    headings_saved = bool(edit and edit.status == 'confirmed' and checks.get('TITLE_H1', True))
    paragraphs_edit = db.get(models.ProjectPageEdit, run.plan['paragraphs_edit_id']) if run.plan.get('paragraphs_edit_id') else None
    return {
        'paragraphs': bool(paragraphs_edit and paragraphs_edit.status == 'confirmed' and checks.get('PARAGRAPHS', True)),
        'title': headings_saved and preview.get('title_before') != preview.get('title_after'),
        'h1': headings_saved and preview.get('h1_before') != preview.get('h1_after'),
        'alternates': bool(checks.get('ALTERNATES', alternates_saved or bool(run.plan.get('alternates_after')))),
    }


def view(db,job):
    from app import report_ids
    snapshot=launch.view(db,job)
    snapshot['report_id'] = report_ids.get(db, job)
    snapshot['generation_id'] = job.payload.get('generation_id', job.id)
    snapshot['name'] = draft_name(job)
    from app.pilot_variations import percentages
    snapshot['percentages'] = percentages(db, job)
    snapshot['title_rewrite_mode'] = job.payload.get('title_rewrite_mode', 'minimal')
    snapshot['planning_mode'] = job.payload.get('planning_mode', 'percentages')
    snapshot['planning_filter'] = selection(job.payload.get('planning_filter') or {}).model_dump()
    preparing=job.kind==launch.PREVIEW_KIND
    from app.pilot_replanning import pending
    snapshot['replanning_requested'] = preparing and bool(pending(db, job.id))
    run_ids={r['run_id'] for r in snapshot['items'] if r.get('run_id')}
    events=[];performed={};alternates_saved=set()
    if run_ids:
        site_ids=set(job.payload['site_ids']) | {p.get('source_site_id',p['site_id']) for g in job.result['groups'] for p in g.get('plans',[])}
        for op in db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id.in_(site_ids)).order_by(models.NetworkOperation.created_at)):
            if op.request_payload.get('auto_run_id') not in run_ids: continue
            if op.action=='reglue' and op.status=='confirmed':
                performed[op.request_payload['auto_run_id']]=op.request_payload.get('confirmed_at') or op.updated_at
            if op.action=='alternates' and op.status=='confirmed':
                alternates_saved.add(op.request_payload['auto_run_id'])
            events.append({'id':op.id,'site_id':op.site_id,'run_id':op.request_payload['auto_run_id'],'action':op.action,'status':op.status,'message':op.message,'at':op.updated_at})
    plans = {p['site_id']: p for g in job.result['groups'] for p in g.get('plans', [])}
    for saved in job.result.get('items', {}).values():
        if saved.get('completed_elsewhere_plan'):
            plans.setdefault(saved['site_id'], saved['completed_elsewhere_plan'])
    from app.pilot_weekly import exclusions
    recent = exclusions(db, list(plans.values())) if preparing else {}
    sites = {site.id: site for site in db.scalars(select(models.Site).where(models.Site.id.in_([row['site_id'] for row in snapshot['items']])))}
    for row in snapshot['items']:
        site = sites.get(row['site_id'])
        from app.pilot_versions import summary as version_summary
        row.update(version_summary(job.result, row['site_id']))
        if row['site_id'] in recent:
            row.update(status='skipped', reason=recent[row['site_id']])
        row['brand'] = scope_brand(site) if site else plans.get(row['site_id'], {}).get('brand') or 'Общие ключи'
        row['geo'] = country_key(row.get('geo'))
        row['current_main'] = (site.cache_canon or '') if site else ''
        row['fibery_name'] = site.fibery_name if site else None
        if row['site_id'] in plans:
            row.update(describe(db, plans[row['site_id']]))
        elif preparing and not row.get('completed_elsewhere'):
            # Skipped rows can retain a prior version's display snapshot. It is
            # not an allocation and must not look like a second assignment.
            for field in ('new_main','old_main','source_project','scheme','alternate','alternate_before','canonical','alternates_enabled','new_fake_path','title_h1_preview','paragraphs_preview'):
                row.pop(field,None)
        from app.pilot_internal_pages import snapshot as internal_pages_snapshot
        internal_plan = plans.get(row['site_id'], {}).get('internal_pages')
        internal_pages = internal_pages_snapshot(db, job.id, row['site_id'], internal_plan) if internal_plan and internal_plan.get('enabled') is True else None
        if internal_pages:
            row['internal_pages'] = internal_pages
        if preparing:
            from app.homepage_headings import audited_metadata
            site=db.get(models.Site,row['site_id'])
            if site:row['title_h1_current']=audited_metadata(db,site,row.get('old_main') or site.cache_canon,row.get('title_h1_current'))
        run=db.get(models.AutoReglueRun,row['run_id']) if row.get('run_id') else None
        phase=run.phase.removeprefix('cross_') if run else row.get('phase','')
        row['phase']=phase
        row['performed_at']=performed.get(run.id) if run else None
        if run:
            from app.transfer_confirmation import view as confirmation_view
            row['confirmation']=confirmation_view(run)
            row['verification']=run.plan.get('verification')
            row['monitor']=run.plan.get('post_reglue_monitor')
            if not preparing:
                row['updated_fields']=confirmed_updates(db, run, run.id in alternates_saved)
            row['notes']=run.plan.get('dns_warnings') or []
            if run.plan.get('backup_note'):
                row['notes']=[*row['notes'],{'domain':'Бэкап','message':run.plan['backup_note'],'checked_at':run.updated_at.isoformat()}]
            for index, note in enumerate(run.plan.get('archived_notes', [])):
                events.append({'id':f'{run.id}:archived-note:{index}', 'site_id':run.site_id, 'run_id':run.id,
                    'action':'Примечание закрыто', 'status':'confirmed', 'at':note['archived_at'],
                    'message':f"{note.get('domain', '')} — {note['message']} · Закрыл: {note['archived_by']}"})
        row['progress']=100 if row['status'] in launch.TERMINAL | {'skipped','ready'} else PHASE_PROGRESS.get(phase,0)
        if not preparing:
            from app.pilot_internal_pages import merge_row
            merge_row(row, row.get('internal_pages'))
        from app.pilot_content_publication import merge_row as merge_content_jobs
        merge_content_jobs(db, job, row)
        if row.get('completed_elsewhere'):
            from app.pilot_observed_reglues import apply
            apply(row, row['completed_elsewhere'])
        if not preparing and not row.get('completed_elsewhere'):
            from app.pilot_row_replan import eligible
            try:
                eligible(db,job,row['site_id'])
                row['can_replan']=True
            except (ValueError,NetworkConflict):
                row['can_replan']=False
            alternative=(job.result.get('items',{}).get(row['site_id'],{}).get('alternative') or {})
            if alternative:
                row['alternative']=deepcopy(alternative)
                child=db.get(models.BackgroundJob,alternative.get('id'))
                if child and child.status=='queued':row['alternative']['phase']=(child.result or {}).get('phase','network')
                if child and alternative.get('status')=='ready':
                    row.update(describe(db,child.result['plan']))
    snapshot['items'].sort(key=lambda row: (row['brand'].casefold(), row.get('geo', ''), row['project'].casefold(), row['site_id']))
    total=len(snapshot['items']);done=sum(r['status'] in launch.TERMINAL|{'skipped'} for r in snapshot['items'])
    snapshot['counts'] = {status:sum(row['status']==status for row in snapshot['items']) for status in snapshot['counts']}
    fulfilled = {r['site_id'] for r in snapshot['items'] if r.get('completed_elsewhere')}
    plans = {site_id:p for site_id,p in plans.items() if site_id not in recent and site_id not in fulfilled}
    snapshot['variation_summary']=job.result.get('variation_summary')
    if (recent or fulfilled) and snapshot['variation_summary']:
        current = deepcopy(job.result)
        for group in current['groups']:
            group['plans'] = [p for p in group.get('plans', []) if p['site_id'] not in recent and p['site_id'] not in fulfilled]
        from app.pilot_variations import update_summary
        update_summary(current)
        snapshot['variation_summary'] = current['variation_summary']
    from app.pilot_distribution import summarize
    snapshot['distribution'] = summarize(list(plans.values()))
    snapshot['plan_outdated']=preparing and job.payload.get('planner_version') != launch.PLANNER_VERSION
    from app.reglue_title_h1 import preview_needs_shortening
    snapshot['title_h1_outdated']=preparing and any(preview_needs_shortening(p) for p in plans.values())
    from app.pilot_text_jobs import independent_start
    snapshot['parallel_texts']=bool(job.result.get('parallel_texts'))
    snapshot['can_launch_while_generating']=bool(preparing and job.status=='queued' and independent_start(job))
    snapshot['launch_enabled']=bool(plans) and not snapshot['replanning_requested'] and not snapshot['plan_outdated'] and not snapshot['title_h1_outdated'] and (independent_start(job) or all(paragraphs_ready(db,p) and heading_mode_ready(db,p,snapshot['title_rewrite_mode']) for p in plans.values()))
    domain_counts={'reserve_drops':0,'newregs':0,'drops':0,'other':0}
    for p in plans.values():
        kind=p.get('domain_type') or p.get('required_domain_type') or p.get('main_target_kind')
        if p.get('reserve_pool_id'):domain_counts['reserve_drops']+=1;kind='drop'
        domain_counts['newregs' if kind in ('newreg','sub_newreg','newreg_subdomain') else 'drops' if kind in ('drop','sub_drop','drop_subdomain') else 'other']+=1
    snapshot['domain_summary']=domain_counts
    from app.pilot_domain_filters import domain_projects
    snapshot['domain_projects'] = domain_projects(plans, snapshot['items'], confirmed=not preparing)
    snapshot.update(mode='preview' if preparing else 'execution',ready=sum(r['status']=='ready' for r in snapshot['items']),events=events,
                    progress={'percent':round(sum(r['progress'] for r in snapshot['items'])/total) if total else 100,'done':done,'total':total},
                    updated_at=job.updated_at,launched_at=job.payload.get('launched_at'),finished_at=job.finished_at)
    if not preparing:
        from app.pilot_internal_pages import report_metadata
        snapshot.update(report_metadata(db, job))
    snapshot['title_h1_progress']=job.result.get('title_h1_progress')
    snapshot['paragraphs_progress']=job.result.get('paragraphs_progress')
    if preparing and job.status!='completed':
        headings=job.result.get('title_h1_progress')
        paragraphs=job.result.get('paragraphs_progress')
        text_progress=[value for value in (headings,paragraphs) if value]
        snapshot['planning_phase']=('Подготовка Title/H1 и абзацев' if headings and headings['total'] else 'Подготовка абзацев') if paragraphs and paragraphs['total'] else 'Подготовка Title/H1' if headings else 'Подбор доменов и схем'
        snapshot['title_h1_progress']=headings
        snapshot['paragraphs_progress']=paragraphs
        snapshot['progress']['percent']=min(99,70+round(30*sum(p['done'] for p in text_progress)/max(1,sum(p['total'] for p in text_progress)))) if text_progress else min(70,round(snapshot['progress']['percent']*.7))
    from app.report_membership import can_exclude
    for row in snapshot['items']:
        pinned = job.payload.get('preserved_target_plans', {}).get(row['site_id'])
        if pinned and not row.get('new_main'):
            row['new_main'] = pinned['new_main']
            row['source_project'] = pinned.get('source_project')
    snapshot['targets_preserved'] = bool(job.payload.get('preserved_target_plans'))
    snapshot['maintenance_archive_url'] = f'/auto-reglue/pilot/report?maintenance={job.id}&archive=1' if job.payload.get('maintenance_archive_key') else None
    snapshot['allow_stock_drops'] = job.payload.get('allow_stock_drops', True)
    snapshot['can_exclude'] = can_exclude(job)
    snapshot['excluded_projects'] = [{k:v for k,v in e.items() if k not in {'entry','previous_result'}} for e in job.payload.get('excluded_projects',[])]
    from app.report_status import metadata as status_metadata
    snapshot.update(status_metadata(job, status=snapshot['status'], finished_at=snapshot.get('finished_at')))
    return snapshot


def refresh_row(db, job_id, site_id, request_id, user):
    """Replace one reviewed scheme atomically; never enqueue or modify Webdev."""
    with network_lock(db, 'mass-reglue-list:' + str(job_id)):
        job = get(db, job_id, user)
        if job.kind != launch.PREVIEW_KIND or job.status != 'completed':
            raise NetworkConflict('Обновление доступно только в подготовленном, ещё не запущенном плане.')
        if job.payload.get('planner_version') != launch.PLANNER_VERSION:
            raise NetworkConflict('Обновите весь план: правила планировщика изменились.')
        if auto.digest(auto.config(db).model_dump()) != job.payload['config_hash']:
            raise NetworkConflict('Настройки изменились. Обновите весь план.')
        from app.pilot_replanning import pending
        if pending(db, job.id): raise NetworkConflict('Дождитесь обновления плана.')
        result = deepcopy(job.result)
        from app.pilot_versions import ensure_current, append_version
        ensure_current(job, result)
        row = result['items'].get(str(site_id))
        if row is None: raise ValueError('Проект не входит в этот план.')
        requests = dict(result.get('row_refresh_requests', {}))
        if str(request_id) in requests:
            if requests[str(request_id)] != str(site_id): raise ValueError('Идентификатор запроса уже занят.')
            return job
        site = db.get(models.Site, str(site_id))
        scope = selection(job.payload.get('planning_filter') or {})
        if site and not scope.includes(scope_brand(site), site.cache_geo):
            raise NetworkConflict('Проект больше не соответствует сохранённому отбору брендов и GEO. Обновите план.')
        if reason := launch.skip_reason(db, site): raise NetworkConflict(reason)
        all_plans = [p for g in result['groups'] for p in g.get('plans', [])]
        current = next((p for p in all_plans if p['site_id'] == str(site_id)), None)
        if current is None:
            if job.payload.get('planning_mode') == 'mixed':
                raise NetworkConflict('Обновите весь смешанный план, чтобы включить проект и заново распределить способы переклея.')
            # Retry this skipped recipient without reallocating its neighbours' domains.
            from app.mass_action_scope import constrain
            group = next((g for g in result['groups'] if str(site_id) in g['site_ids']), None)
            if group is None: raise NetworkConflict('Обновите весь план, чтобы включить ранее исключённый проект.')
            info = dict(db.info)
            try:
                constrain(db, group['filter'], set(job.payload['allowed']) if job.payload['allowed'] is not None else None, [site])
                db.info.update(pilot_job_id=job.id, auto_pilot_preview=True, prefer_own_domains=True, pilot_allow_stock_drops=job.payload.get('allow_stock_drops',True), pilot_mixed=job.payload.get('planning_mode') == 'mixed',
                    canonical_allocation_plans=all_plans, reglue_preview_domains={p['new_main'] for p in all_plans})
                db.info.pop('mass_participant_ids', None)
                if job.payload['execution_mode'] == 'cross_network':
                    from app.cross_reglue_batch import build
                    if job.payload.get('preserved_target_plans'):
                        from app.pilot_report_conversion import build_preserved
                        preview = build_preserved(db, job, [site])
                    else:
                        preview = build(db, [site], user['username'])
                    if not preview['plans']: raise ValueError(preview['skipped'][0]['error'])
                    current = preview['plans'][0]
                    # Keep the new receipt separate from the already reviewed group manifest.
                    group['site_ids'].remove(str(site_id))
                    result['groups'].append({**group, 'site_ids':[str(site_id)], 'plans':[current], 'batch_id':preview['batch_id'], 'status':'previewed'})
                else:
                    current = auto.preview(db, site, 'mass'); group.setdefault('plans', []).append(current)
                current.update(pilot_variation_version=1, redirect_old_main=False, rewrite_title_h1=False, rewrite_paragraphs=False, title_rewrite_mode=job.payload.get('title_rewrite_mode','minimal'))
            finally:
                db.info.clear(); db.info.update(info)
        from app.pilot_schemes import assign
        before = deepcopy(current)
        assign(db, [current], fixed=[p for p in all_plans if p['site_id'] != str(site_id)],
               exclude={str(site_id):current.get('scheme_variant')})
        if current.get('without_alternates') and current.get('fake_main_path'):
            from app.fake_path_allocation import next_path
            previous=current['fake_main_path']
            state={**(site.network_state or {}),'fake_main_history':[*((site.network_state or {}).get('fake_main_history') or []),previous]}
            from types import SimpleNamespace
            path=next_path(db,site,state,SimpleNamespace(language=current.get('language') or site.cache_language or ''),all_plans)
            current.update(fake_main_path=path,create_fake_main_path=path,new_fake_main_path=path)
            current['required_page_urls']=['https://'+current['new_main']+'/', 'https://'+current['new_main']+path]
        if all(current.get(k)==before.get(k) for k in ('alternateMarkup','enableAlternates','fake_main_path','canonicalFakeMainMarkup','new_main')):
            raise NetworkConflict('Для текущих настроек нет другой совместимой схемы. Измените настройки и обновите план.')
        # Read the live Webdev source, without read_network's pending-operation
        # reconciliation. Both detection and any selected rewrite use one snapshot.
        from app.project_network import Remote
        from app.domain_transfer_policy import domain_key
        from app.reglue_title_h1 import page_metadata, prepare_for_plan
        with Remote(db,site) as remote: project=remote.project()
        actual_main=(project.get('settings') or {}).get('canon')
        if not actual_main or domain_key(actual_main)!=domain_key(current.get('old_main')):
            raise NetworkConflict('Текущий Main изменился. Обновите весь план перед выбором новой схемы.')
        from app.project_pages import pages, is_home
        if len([p for p in pages(project) if is_home(p)])!=1:
            raise NetworkConflict('Webdev не вернул единственную главную страницу. Повторите обновление строки.')
        if (current.get('internal_pages') or {}).get('enabled'):
            from app.pilot_internal_pages_policy import require_eligible
            checked = require_eligible(db, site, project)
            current['internal_pages_eligibility'] = checked
            current['internal_pages'] = {**current['internal_pages'], 'eligibility':checked}
        current['title_h1_current']=page_metadata(project)
        current.pop('title_h1_reused', None)
        current['title_rewrite_mode'] = job.payload.get('title_rewrite_mode', 'minimal') if job.payload.get('title_rewrite_mode') != 'mixed' else current.get('title_rewrite_mode', 'minimal')
        prepare_for_plan(db,current,str(request_id),project=project,force=True)
        from app.reglue_paragraphs import prepare_for_plan as prepare_paragraphs
        prepare_paragraphs(db,current,str(request_id),project=project,force=True)
        current.pop('preview_token', None); current['preview_token'] = auto.digest(current)
        from app.cross_reglue_batch import key, validate
        for group in result['groups']:
            if any(p['site_id'] == str(site_id) for p in group.get('plans', [])):
                if group.get('batch_id'):
                    validate(group['plans'])
                    ledger = db.get(models.AutoReglueConfig, key(group['batch_id']))
                    if ledger.value.get('run_ids'): raise NetworkConflict('Группа уже была запущена.')
                    ledger.value = {**ledger.value, 'plans':deepcopy(group['plans'])}
                group['status'] = 'previewed'
        if job.payload['execution_mode']=='cross_network':validate([p for g in result['groups'] for p in g.get('plans',[])])
        row.update(status='ready', reason=None, **describe(db, current))
        append_version(job, result, current, request_id)
        requests[str(request_id)] = str(site_id)
        result['row_refresh_requests'] = requests
        from app.pilot_variations import update_summary
        update_summary(result)
        job.result = result; db.commit()
        return job
