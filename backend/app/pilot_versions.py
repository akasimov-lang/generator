"""Up to five coherent, reviewed variants per project in one Auto Pilot job."""
from copy import deepcopy
from datetime import datetime, timezone
from app import models, auto_reglue as auto, mass_reglue_launch as launch
from app.project_network import NetworkConflict, network_lock


def append_version(job, result, plan, generation_id):
    histories = result.setdefault('row_versions', {})
    history = histories.setdefault(plan['site_id'], {'selected': 0, 'versions': []})
    if any(item['generation_id'] == str(generation_id) for item in history['versions']):
        return
    if len(history['versions']) >= 5:
        history['versions'] = []
    number = len(history['versions']) + 1
    history['versions'].append({'number': number, 'generation_id': str(generation_id),
        'created_at': datetime.now(timezone.utc).isoformat(), 'config_hash': job.payload['config_hash'], 'plan': deepcopy(plan)})
    history['selected'] = number


def ensure_current(job, result):
    for group in result['groups']:
        for plan in group.get('plans', []):
            if not result.get('row_versions', {}).get(plan['site_id']):
                append_version(job, result, plan, job.payload.get('generation_id', job.id))


def capture_all(job, result):
    for group in result['groups']:
        for plan in group.get('plans', []):
            append_version(job, result, plan, job.payload.get('generation_id', job.id))


def summary(result, site_id):
    history = result.get('row_versions', {}).get(site_id)
    if not history:
        return {'selected_version': 1, 'versions': [{'number': 1}]} if any(
            p['site_id'] == site_id for g in result.get('groups', []) for p in g.get('plans', [])) else {}
    return {'selected_version': history['selected'], 'versions': [
        {'number': item['number'], 'created_at': item['created_at']} for item in history['versions']]}


def persist_groups(db, result):
    from app.cross_reglue_batch import key, validate
    for group in result['groups']:
        if group.get('batch_id'):
            validate(group.get('plans', []))
            ledger = db.get(models.AutoReglueConfig, key(group['batch_id']))
            if not ledger or ledger.value.get('run_ids'):
                raise NetworkConflict('Группа уже запущена или её план недоступен.')
            ledger.value = {**ledger.value, 'plans': deepcopy(group.get('plans', []))}


def validate_live(db, job, plan, user, plans):
    """Fresh reads only: selecting a tab never generates content or writes Webdev."""
    from app.auto_pilot import scope_brand, heading_mode_ready, paragraphs_ready
    from app.pilot_scope import selection
    from app.mass_action_scope import MassActionFilter, matches
    from app.cross_reglue import source_guard, require_pair
    from app.network_state import observe_network, state_revision
    from types import SimpleNamespace
    from app.project_network import Remote
    from app.domain_transfer_policy import domain_key, banned_domains
    from app.pilot_schemes import validate_single_alternate
    from app.fake_path_allocation import require_available
    from app.reglue_reserves import require_unused
    validate_single_alternate(plan)
    domains = [domain_key(p['new_main']) for p in plans]
    if len(domains) != len(set(domains)):
        raise NetworkConflict('Домен этой версии уже выбран для другого проекта. Выберите другой вариант.')
    if not heading_mode_ready(db, plan, job.payload.get('title_rewrite_mode', 'minimal')) or not paragraphs_ready(db, plan):
        raise NetworkConflict('Текст этой версии не готов или не соответствует режиму. Перегенерируйте проект.')
    scope = selection(job.payload.get('planning_filter') or {})
    group = next(g for g in job.result['groups'] if plan['site_id'] in g['site_ids'])
    filters = MassActionFilter.model_validate(group['filter'])
    allowed = user.get('allowed_site_ids')
    source_id, target_id = plan.get('source_site_id', plan['site_id']), plan['site_id']
    sites, projects, states = {}, {}, {}
    for site_id in dict.fromkeys((target_id, source_id)):
        site = db.get(models.Site, site_id)
        if site: db.refresh(site)
        if not site or allowed is not None and site_id not in allowed or not matches(site, filters) or not scope.includes(scope_brand(site), site.cache_geo):
            raise NetworkConflict('Проект или донор версии больше не входит в доступный бренд и GEO.')
        if reason := launch.skip_reason(db, site): raise NetworkConflict(reason)
        with Remote(db, site) as remote: project = remote.project()
        # Native project reads do not reconcile or continue pending operations.
        detached = SimpleNamespace(**{column.key: deepcopy(getattr(site, column.key)) for column in models.Site.__table__.columns})
        state = observe_network(detached, project)
        guard = plan.get('target_guard' if site_id == target_id else 'source_guard')
        domains_before = plan.get('target_domains' if site_id == target_id else 'source_domains')
        if guard is not None:
            if source_guard(state) != guard or set(state['domains']) != set(domains_before or []):
                raise NetworkConflict('Сетка изменилась после этой версии. Перегенерируйте проект.')
        elif state_revision(state) != plan.get('revision'):
            raise NetworkConflict('Сетка изменилась после этой версии. Перегенерируйте проект.')
        sites[site_id], projects[site_id], states[site_id] = site, project, state
    if (plan.get('internal_pages') or {}).get('enabled'):
        from app.pilot_internal_pages_policy import require_eligible
        require_eligible(db, sites[target_id], projects[target_id])
    if source_id != target_id: require_pair(sites[source_id], sites[target_id])
    if any(any(banned_domains(db, site, [plan['new_main'], *([plan['parent_domain']] if plan.get('parent_domain') else [])]).values()) for site in sites.values()):
        raise NetworkConflict('Домен или родительский домен этой версии в БАН. Выберите другой вариант.')
    require_unused(sites[target_id], states[target_id], plan['new_main'])
    require_available(db, sites[target_id], plan.get('fake_main_path'), plans)
    if plan.get('reserve_pool_id'):
        from app.reglue_reserves import validate_plan
        validate_plan(db, sites[target_id], states[target_id], plan)
    from app.project_pages import find_page, digest
    for field in ('title_h1', 'paragraphs'):
        if not plan.get('rewrite_' + field): continue
        draft = db.get(models.ProjectPageDraft, plan.get(field + '_preview', {}).get('draft_id'))
        if not draft or draft.site_id != target_id or draft.status != 'ready':
            raise NetworkConflict('Черновик текста этой версии недоступен.')
        page = find_page(projects[target_id], draft.page_key)
        if digest(page) != (draft.input_metadata or {}).get('revision'):
            raise NetworkConflict('Контент изменился после этой версии. Перегенерируйте проект.')


def select_version(db, job_id, site_id, number, user):
    from app.auto_pilot import get, describe
    from app.pilot_replanning import pending
    with network_lock(db, 'mass-reglue-list:' + str(job_id)):
        job = get(db, job_id, user)
        if job.kind != launch.PREVIEW_KIND or job.status != 'completed' or pending(db, job.id):
            raise NetworkConflict('Версии можно выбирать только в подготовленном черновике.')
        if job.payload.get('planner_version') != launch.PLANNER_VERSION or auto.digest(auto.config(db).model_dump()) != job.payload['config_hash']:
            raise NetworkConflict('Правила изменились. Обновите план.')
        result = deepcopy(job.result)
        ensure_current(job, result)
        history = result.get('row_versions', {}).get(str(site_id))
        chosen = next((v for v in (history or {}).get('versions', []) if v['number'] == number), None)
        if not chosen: raise ValueError('Версия проекта не найдена.')
        if history['selected'] == number: return job
        if chosen['config_hash'] != job.payload['config_hash']:
            raise NetworkConflict('Версия создана с другими общими настройками. Перегенерируйте проект.')
        candidate = deepcopy(chosen['plan'])
        found = False
        for group in result['groups']:
            for index, plan in enumerate(group.get('plans', [])):
                if plan['site_id'] == str(site_id):
                    if group.get('batch_id'): candidate['batch_id'] = group['batch_id']
                    candidate.pop('preview_token', None); candidate['preview_token'] = auto.digest(candidate)
                    group['plans'][index] = candidate
                    found = True
        if not found: raise ValueError('Проект не входит в текущую подготовку.')
        plans = [p for g in result['groups'] for p in g.get('plans', [])]
        if job.payload['execution_mode'] == 'cross_network':
            from app.cross_reglue_batch import validate
            validate(plans)
        validate_live(db, job, candidate, user, plans)
        persist_groups(db, result)
        history['selected'] = number
        result['items'][str(site_id)].update(status='ready', reason=None, **describe(db, candidate))
        from app.pilot_variations import update_summary
        update_summary(result)
        job.result = result; db.commit()
        return job
