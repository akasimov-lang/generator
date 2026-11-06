"""Receipt-driven transfer between networks, followed by promotion to Main."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import re
import httpx
from uuid import UUID, uuid5
from sqlalchemy import select
from app import models, project_network as network
from app.mass_action_reports import refresh_run
from app.domain_transfer_policy import banned_domains, domain_key, geo_key, policy_key, require_transfer_allowed
from app.network_state import alternate_links
from app.domain_classification import classify_domains
from app.network_reserve import reserved_domains, selected_reserve, require_import_target


def brand_key(value):
    return re.sub(r'[^\w]', '', (value or '').casefold())


def require_pair(source, target):
    if not source or not target or source.id == target.id:
        raise ValueError('Для переноса нужны две разные сетки.')
    if not all(s.is_active and s.project_status == 'mass_actions' for s in (source, target)):
        raise ValueError('Обе сетки должны участвовать в массовых действиях.')
    brand = brand_key(source.brand)
    geo = geo_key(source.cache_geo)
    if not brand or brand == brand_key('Общие ключи') or brand != brand_key(target.brand):
        raise ValueError('Перенос разрешён только между сетками одного бренда.')
    if len(geo) != 2 or geo != geo_key(target.cache_geo):
        raise ValueError('Перенос разрешён только между сетками одного GEO.')


@contextmanager
def participant_locks(db, site_id, plan):
    with ExitStack() as stack:
        for key in sorted({site_id, plan.get('source_site_id', site_id)}):
            stack.enter_context(network.network_lock(db, key))
        yield


def transferable(source, state, domain, *, plan=None):
    from app.domain_redirects import require_transfer_free
    require_transfer_free(state, [domain])
    if not state.get('head_verified', state.get('has_head')):
        raise ValueError('Не подтверждены актуальные альтернейты исходной сетки.')
    key = domain_key(domain)
    from app.pilot_domain_reuse import allows
    history = [] if allows(source,state,domain,plan) else [*(source.main_domain_history or []), *(source.alternate_domain_history or []), *(source.x_default_history or [])]
    protected = [source.name, state['canon'], *reserved_domains(state), *state.get('amp_domains', []), *history]
    markup = state['alternateMarkup'].replace('{{settings.canon}}', state['canon'])
    protected += [link['domain'] for link in alternate_links(markup)]
    if domain not in state['domains'] or key in {domain_key(d) for d in protected}:
        raise ValueError('Домен занят текущими настройками или отмечен в истории использования.')
    if (source.domain_types or {}).get(domain) == 'amp':
        raise ValueError('AMP-домены не переносятся.')
    if classify_domains(state['domains'], source.domain_types or {})[domain]['is_subdomain']:
        raise ValueError('Для переноса выберите корневой домен.')
    if sum(domain_key(d) == key for d in state['domains']) > 1:
        raise ValueError('В исходной сетке есть несколько вариантов адреса этого домена.')
    if any(domain_key(d).endswith('.' + key) for d in state['domains'] if domain_key(d) != key):
        raise ValueError('У домена есть поддомены в исходной сетке.')


def unique_membership(db, domain, permitted):
    sites = models.Site.__table__.c
    for site_id, domains in db.execute(select(sites.id, sites.cache_domains).where(sites.is_active.is_(True))):
        if site_id not in permitted and any(domain_key(d) == domain_key(domain) for d in domains or []):
            raise ValueError('Домен присутствует ещё в одной сетке.')


def blocked_reserve(db, site, state):
    reserve = selected_reserve(state)
    return reserve if reserve and banned_domains(db, site, [reserve])[reserve] else None


def require_import_for_plan(db, target, state, plan):
    blocked = plan.get('replace_banned_reserve')
    if not blocked:
        return require_import_target(state)
    if selected_reserve(state) != blocked or blocked_reserve(db, target, state) != blocked:
        raise ValueError('Резерв или его БАН изменился после предпросмотра. Подготовьте план заново.')


def preview(db, target, state):
    from app import auto_reglue as auto
    cfg = auto.config(db)
    from app.mass_reglue_launch import manual_pilot_allowed
    auto.require_eligible(target, cfg, auto.config(db, target.id),manual=manual_pilot_allowed(db,target.id))
    if auto.active_run(db, target.id):
        raise ValueError('Принимающая сетка уже участвует в незавершённом запуске.')
    if cfg.scheme_mode not in {'preserve', 'clean', 'locale_base'}:
        raise ValueError('Для перекрёстного режима выберите сохранение схемы, чистый или базовый альтернейт по языку и GEO.')
    query = select(models.Site).where(models.Site.is_active.is_(True),
        models.Site.project_status == 'mass_actions', models.Site.id != target.id)
    allowed = db.info.get('cross_allowed_site_ids')
    if allowed is not None:
        query = query.where(models.Site.id.in_(allowed))
    if cfg.main_target_mode != 'legacy':
        from app.cross_reglue_batch import build
        result = build(db, [target], 'preview', persist=False)
        if not result['plans']:
            raise ValueError(result['skipped'][0]['error'])
        return result['plans'][0]
    banned_reserve = blocked_reserve(db, target, state)
    if selected_reserve(state) and not banned_reserve:
        return reserve_plan(cfg, target, state, db=db)
    from app import reglue_reserves as pool
    entry = pool.candidate(db, target, state, ['newreg'] if banned_reserve else ['drop', 'newreg'])
    if entry:
        return pool.make_plan(db, cfg, target, state, entry)
    candidates, reasons = [], []
    for source in db.scalars(query):
        try:
            require_pair(source, target)
        except ValueError:
            continue
        if auto.config(db, source.id).scope == 'personal' or auto.active_run(db, source.id):
            continue
        source_state = network.read_network(db, source)
        if banned_reserve or len(source_state['domains']) > len(state['domains']):
            candidates.append((source, source_state))
    candidates.sort(key=lambda item: (-len(item[1]['domains']), item[0].name, item[0].id))
    for source, source_state in candidates:
        for domain in source_state['domains']:
            try:
                if (source.domain_types or {}).get(domain) != 'newreg':
                    continue
                from app.reglue_reserves import require_unused
                require_unused(target, state, domain)
                transferable(source, source_state, domain)
                require_transfer_allowed(db, source, domain)
                unique_membership(db, domain, {source.id})
            except ValueError as error:
                reasons.append(str(error)); continue
            return make_plan(cfg, target, state, source, source_state, domain, mode='banned_reserve_fallback' if banned_reserve else 'redistribute', db=db)
    details = '; '.join(dict.fromkeys(reasons))[:1200]
    raise ValueError('Нет подходящего домена в более крупной сетке этого бренда и GEO.' + (' ' + details if details else ''))


def make_plan(cfg, target, state, source, source_state, domain, *, mode='redistribute', source_count=None, target_count=None, db=None, plans=()):
    from app import auto_reglue as auto
    if not state.get('head_verified', state.get('has_head')):
        raise ValueError('Не получены данные head принимающей сетки.')
    scheme_mode = 'locale_base' if db is not None and db.info.get('pilot_mixed') else cfg.scheme_mode
    before = state['alternateMarkup']
    after = re.sub(r'(?<=://)' + re.escape(state['canon']) + r'(?=[/:\"\s]|$)', domain, before)
    if scheme_mode == 'clean':
        after = ''
    fake_path = None
    pilot_preview=bool(db is not None and db.info.get('auto_pilot_preview'))
    if scheme_mode == 'locale_base' or scheme_mode == 'preserve' and (state.get('fake_main_enabled') or pilot_preview):
        from app.alternate_templates import base_alternate_markup, next_base_fake_path
        from app.network_state import validate_markup
        language = (target.cache_language or next((x['hreflang'].split('-')[0] for x in alternate_links(before) if x['hreflang']!='x-default'), '')).strip().lower().replace('_', '-').split('-')[0]
        if db is not None:
            from app.fake_path_allocation import next_path
            from types import SimpleNamespace
            fake_path = next_path(db, target, state, SimpleNamespace(language=language), plans)
        else:
            fake_path = next_base_fake_path(target, state, language, geo_key(target.cache_geo))
        if scheme_mode == 'locale_base' or pilot_preview:
            after = base_alternate_markup(domain, language, geo_key(target.cache_geo), fake_path)
        elif state.get('fake_main_current'):
            after = after.replace('://' + domain + state['fake_main_current'], '://' + domain + fake_path)
            after = after.replace('://{{settings.canon}}' + state['fake_main_current'], '://{{settings.canon}}' + fake_path)
        alternate_domain=(state.get('fake_main_settings') or {}).get('alternateDomain')
        if alternate_domain:after=after.replace('{{settings.alternate.alternateDomain}}',alternate_domain)
        validate_markup(after)
    plan = {'execution_mode': 'cross_network', 'scope': 'mass', 'site_id': target.id,
            'project': target.name, 'source_site_id': source.id, 'source_project': source.name,
            'brand': target.brand, 'geo': geo_key(target.cache_geo), 'old_main': state['canon'], 'new_main': domain,
            'old_fake_main_path': state.get('fake_main_current') or None, 'new_fake_main_path': fake_path or state.get('fake_main_current') or None,
            'source_revision': source_state['revision'], 'revision': state['revision'],
            'source_guard': source_guard(source_state), 'source_domains': source_state['domains'],
            'target_guard': source_guard(state), 'target_domains': state['domains'],
            'source_count': len(source_state['domains']) if source_count is None else source_count,
            'target_count': len(state['domains']) if target_count is None else target_count,
            'balance_mode': mode, 'requires_newreg': True,
            'alternateMarkup': after, 'alternates_before': {'markup': before, 'enabled': state['enableAlternates']},
            'scheme_mode': scheme_mode, 'enableAlternates': True if fake_path else False if scheme_mode == 'clean' else state['enableAlternates'],
            'required_page_urls': ['https://' + domain + '/'], 'domain_type': (source.domain_types or {}).get(domain),
            'config_hash': auto.digest(cfg.model_dump())}
    if db is not None and blocked_reserve(db, target, state):
        plan.update(replace_banned_reserve=blocked_reserve(db, target, state),
                    fallback_reason='Выбранный резерв в БАН; выбран разрешённый новорег из другой сетки того же бренда и GEO.')
    if fake_path:
        from app.fake_main import fake_canonical_markup
        plan.update(language=language, create_fake_main_path=fake_path, fake_main_path=fake_path,
                    canonicalFakeMainMarkup=fake_canonical_markup(fake_path),
                    required_page_urls=['https://' + domain + '/', 'https://' + domain + fake_path])
    if db is not None:
        if not db.info.get('canonical_replay_plan'):
            plan['planning_options'] = auto.effective_project_config(cfg, auto.config(db, target.id)).model_dump()
        from app.canonical_allocation import apply
        apply(db, target, plan, plans)
    plan['preview_token'] = auto.digest(plan)
    return plan


def require_selected_reserve(db, target, state, domain, *, plan=None):
    from app.reglue_reserves import require_unused
    require_unused(target, state, domain, plan=plan)
    if selected_reserve(state) != domain or domain not in state['domains']:
        raise ValueError('Выбранный резерв изменился или отсутствует в сетке. Подготовьте новый план.')
    if domain in state.get('amp_domains', []) or (target.domain_types or {}).get(domain) == 'amp':
        raise ValueError('AMP-домен не может стать Main.')
    if banned_domains(db, target, [domain])[domain]:
        raise ValueError('Выбранный резерв отмечен БАН.')


def reserve_plan(cfg, target, state, *, db=None, plans=()):
    domain = selected_reserve(state)
    if not domain or domain not in state['domains']:
        raise ValueError('Выбранный резерв отсутствует в сетке. Исправьте резерв перед переклеем.')
    plan = make_plan(cfg, target, state, target, state, domain, db=db, plans=plans)
    plan.update(use_selected_reserve=True, balance_mode='selected_reserve', requires_newreg=False)
    plan.pop('preview_token')
    from app.auto_reglue import digest
    return {**plan, 'preview_token': digest(plan)}


def source_guard(state):
    keys = ('canon', 'prev', 'reserve', 'amp', 'prev_amp', 'amp_domains', 'alternateMarkup',
            'enableAlternates', 'enableCanonical', 'canonicalDefaultMarkup', 'canonicalFakeMainMarkup',
            'fake_main_settings', 'content_page_paths', 'has_head')
    return {key: state.get(key) for key in keys}


def membership_matches(db, run, state, site_id, guard, domains):
    removed = set()
    added = set()
    for peer in db.scalars(select(models.AutoReglueRun)):
        if peer.id == run.id or peer.plan.get('batch_id') != run.plan['batch_id']:
            continue
        if peer.site_id == site_id:
            addition = db.get(models.NetworkOperation, receipt_id(peer, 'create_domains'))
            if addition and addition.status == 'confirmed':added.add(peer.plan['new_main'])
            child = db.get(models.NetworkOperation, receipt_id(peer, 'create_subdomains'))
            if child and child.status == 'confirmed':added.add(peer.plan['new_main'])
        if peer.plan.get('source_site_id') != site_id:continue
        receipt = db.get(models.NetworkOperation, receipt_id(peer, 'delete_domain'))
        if receipt:
            if not peer.plan.get('source_released'):
                raise SourceBusy('Ждём подтверждения предыдущего извлечения из этой сетки.')
            removed.add(peer.plan['new_main'])
    actual_guard = source_guard(state)
    guard_matches = actual_guard == guard
    if not guard_matches:
        from app.pilot_internal_pages import matches_owned_page_additions
        guard_matches = matches_owned_page_additions(db,
            run.plan.get('list_launch_id') or db.info.get('manual_pilot_job_id'), site_id, guard, actual_guard)
    return guard_matches and set(state['domains']) == (set(domains) - removed) | added


def source_matches(db, run, state):
    plan = run.plan
    if not plan.get('batch_id'):
        return state['revision'] == plan['source_revision']
    return membership_matches(db, run, state, plan['source_site_id'], plan['source_guard'], plan['source_domains'])


def target_matches(db, run, state):
    plan = run.plan
    if not plan.get('batch_id'):
        return state['revision'] == plan['revision']
    return membership_matches(db, run, state, run.site_id, plan['target_guard'], plan['target_domains'])


def cross_group(plan):
    return brand_key(plan.get('brand')), geo_key(plan.get('geo'))


def extractions_ready(db, run):
    if not run.plan.get('batch_id'):
        return True
    for peer in db.scalars(select(models.AutoReglueRun)):
        if (peer.plan.get('batch_id') != run.plan['batch_id'] or peer.plan.get('execution_mode') != 'cross_network'
                or cross_group(peer.plan) != cross_group(run.plan)):
            continue
        if peer.plan.get('source_released') or peer.plan.get('use_selected_reserve') or peer.plan.get('local_target'):
            continue
        if peer.status in {'failed', 'cancelled'} and not db.get(models.NetworkOperation, receipt_id(peer, 'delete_domain')):
            continue
        return False
    return True


class SourceBusy(ValueError):
    pass


def receipt_id(run, action):
    return str(uuid5(UUID(run.id), 'cross:' + action))


def recovered_dns_job(db, site, operation, job):
    """Reconcile a DNS-only result with fresh Webdev membership."""
    if operation.action not in {'create_domains', 'create_subdomains'}:
        return False
    result = job.get('result') or {}
    domains = result.get('domains') or job.get('domains') or []
    errors = [d for d in domains if d.get('status') == 'error']
    expected = {d['domain'] for d in operation.request_payload.get('domains', [])}
    if (job.get('state') != 'completed' or job.get('error') or not expected or not errors
            or {d.get('domain') for d in domains} != expected
            or result.get('errorCount') != len(errors)
            or any(d.get('failedStage') != 'dns' for d in errors)):
        return False
    state = network.read_network(db, site)
    if not network.operation_matches(operation, state):
        return False
    from app.reglue_dns import allowed, note
    run = db.get(models.AutoReglueRun, operation.request_payload.get('auto_run_id'))
    advisory = allowed(run)
    if not advisory:
        from app.auto_reglue import verify_pages
        try:
            verify_pages(['https://' + domain + '/' for domain in sorted(expected)])
        except (httpx.HTTPError, ValueError):
            return False
    else:
        for domain in expected:
            note(db, run, domain, 'Webdev подтвердил добавление домена; DNS — примечание. ' + str(errors[0].get('errorMessage') or 'Ошибка DNS.'))
    operation.status = 'confirmed'
    operation.request_payload = {**operation.request_payload, 'dns_recovery': {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'job_id': operation.request_payload.get('job_id'), 'domains': sorted(expected),
        'original_errors': errors, 'membership_confirmed': True, 'https_status': None if advisory else 200,
        'dns_advisory': advisory,
    }}
    db.commit()
    return True


def completed_domain_results(job, operation):
    """A completed task must not hide unfinished per-domain work.

    Older Webdev replies omit both domain lists and successCount. Preserve that
    contract, but never ignore explicit pending domains or contradictory counts.
    """
    result = job.get('result') or {}
    requested = operation.request_payload.get('domains') or []
    expected = {item.get('domain') if isinstance(item, dict) else item for item in requested}
    expected.discard(None)
    terminal = {'success', 'completed'}
    if operation.action == 'delete_domain': terminal.add('deleted')
    domain_count = None
    for owner in (job, result):
        if 'domains' not in owner: continue
        domains = owner['domains']
        if not isinstance(domains, list): return False
        if not domains:
            if operation.action in {'create_domains', 'create_subdomains'}: return False
            continue
        if any(not isinstance(item, dict) or item.get('status') not in terminal
               or item.get('failedStage') or item.get('errorMessage') for item in domains): return False
        names = [item.get('domain') for item in domains]
        if len(set(names)) != len(names) or (expected and set(names) != expected): return False
        domain_count = len(domains)
    for key in ('successCount', 'errorCount'):
        if key in result and (type(result[key]) is not int or result[key] < 0): return False
    if result.get('errorCount', 0) != 0: return False
    if 'successCount' in result:
        count = len(expected) if expected else domain_count
        if count is not None and result['successCount'] != count: return False
        if count is None and result['successCount'] == 0: return False
    return True


def incomplete_domain_results(job):
    """Explicit unfinished details must also block DNS-error recovery."""
    for owner in (job, job.get('result') or {}):
        if 'domains' not in owner: continue
        domains = owner['domains']
        if not isinstance(domains, list): return True
        if any(not isinstance(item, dict) or item.get('status') not in
               {'success', 'completed', 'deleted', 'error', 'failed'} for item in domains): return True
    return False


def completed_job(db, site, operation):
    job_id = operation.request_payload.get('job_id')
    # Membership alone is insufficient: nginx/DNS provisioning may still be running.
    if not job_id:
        raise ValueError('Webdev не вернул идентификатор задачи. Нужна ручная проверка результата.')
    with network.Remote(db, site) as remote:
        job = remote.job_state(job_id)
    if not job:
        return False
    if job.get('state') == 'not_found':
        saved = operation.request_payload.get('provisioning_result') or {}
        if saved.get('job_id') != job_id or saved.get('action') != operation.action:
            raise ValueError('Webdev удалил задачу ' + str(job_id) + ' из журнала. Нужна проверка результата; повторная отправка заблокирована.')
        job = saved['job']
    elif job.get('state') in {'completed', 'failed'}:
        # Webdev expires its task journal. Keep the observed terminal response so
        # a later phase/restart never waits forever for an already finished job.
        operation.request_payload = {**operation.request_payload, 'provisioning_result': {
            'job_id': job_id, 'action': operation.action, 'job': job,
            'observed_at': datetime.now(timezone.utc).isoformat(),
        }}
        db.commit()
    result = job.get('result') or {}
    if job.get('state') == 'completed' and not job.get('error') and incomplete_domain_results(job):
        from app.provisioning_readiness import observe
        return observe(db, site, operation, job)
    if job.get('state') == 'failed' or job.get('error') or result.get('errorCount', 0) or any(d.get('status') == 'error' for d in job.get('domains', [])):
        if recovered_dns_job(db, site, operation, job):
            return True
        raise ValueError('Задача Webdev завершилась ошибкой: ' + str(job.get('error') or result)[:500])
    if operation.status == 'failed':
        raise ValueError(operation.message or 'Ошибка операции Webdev.')
    return (job.get('state') == 'completed' and operation.status == 'confirmed'
            and completed_domain_results(job, operation))


def change(db, run, site, action, state, **values):
    receipt = receipt_id(run, action)
    existing = db.get(models.NetworkOperation, receipt)
    if existing is None:
        run.phase = 'cross_' + action; run.status = 'running'; db.commit()
        network.change_network(db, site, network.NetworkChange(request_id=receipt, action=action, revision=state['revision'], **values), run.initiator, auto_run_id=run.id)
        existing = db.get(models.NetworkOperation, receipt)
    db.refresh(existing)
    if existing.status == 'failed' and action in {'create_fake_main', 'reglue', 'alternates'}:
        from app.reglue_dns import allowed, note
        message = existing.message or ''
        if allowed(run):
            saved = (all(state.get('fake_main_settings', {}).get(k) == v for k, v in existing.request_payload.get('alternate', {}).items()) and bool(existing.request_payload.get('alternate'))
                     if action == 'create_fake_main' else state.get('canon') == existing.request_payload.get('reserve') if action == 'reglue' else network.operation_matches(existing, state))
            if saved:
                existing.status = 'unknown'
                existing.request_payload = {**existing.request_payload, 'dns_health_warning': message}
                db.commit()
                code = f'HTTP {existing.response_status}. ' if existing.response_status else ''
                note(db, run, run.plan['new_main'], 'Настройки подтверждены чтением Webdev. Ответ при сохранении: ' + code + message)
                network.read_network(db, site)
                db.refresh(existing)
    if existing.status == 'failed' and action not in {'create_domains', 'create_subdomains', 'delete_domain'}:
        raise ValueError(existing.message or 'Ошибка Webdev.')
    ready = completed_job(db, site, existing) if action in {'delete_domain', 'create_domains', 'create_subdomains'} else existing.status == 'confirmed'
    if not ready:
        run.status = 'waiting'; run.message = 'Ждём подтверждения Webdev: ' + action + '. Повторная отправка не выполняется.'; db.commit()
    return ready


def execute(db, run):
    from app import auto_reglue as auto
    plan = run.plan
    target = db.get(models.Site, run.site_id)
    source = db.get(models.Site, plan['source_site_id'])
    domain = plan['new_main']
    try:
        from app.pilot_schemes import validate_single_alternate
        validate_single_alternate(plan)
        # Same lock as ban edits; another run cannot transfer the domain concurrently.
        with network.network_lock(db, 'cross-source:' + source.id), network.network_lock(db, policy_key(domain)):
            from app.mass_reglue_launch import manual_pilot_allowed
            manual=manual_pilot_allowed(db,target.id,run)
            repeat = bool(plan.get('maintenance_repeat_id'))
            if repeat and not manual:
                raise ValueError('Повторная обработка не подтверждена отдельным отчётом этой группы.')
            if plan.get('use_selected_reserve') or plan.get('local_target'):
                if source.id != target.id: raise ValueError('Резерв должен принадлежать своей сетке.')
                auto.require_eligible(target, auto.config(db), auto.config(db, target.id),manual=manual)
            else:
                require_pair(source, target)
            from app.cross_reglue_batch import authorize
            authorize(db, run)
            cfg = auto.config(db)
            from app.pilot_mixed import manual_allowed as mixed_manual_allowed
            if (cfg.execution_mode != 'cross_network' and not (repeat and manual) and not mixed_manual_allowed(db, run)) or not (cfg.enabled or manual):
                raise ValueError('Перекрёстный режим выключен.')
            if run.plan.get('scheduled') and not cfg.schedule_enabled:
                raise ValueError('Расписание выключено.')
            if any(auto.config(db, s.id).scope == 'personal' for s in (source, target)):
                raise ValueError('Сетка переведена на персональные настройки.')
            if banned_domains(db, target, [domain])[domain]:
                raise ValueError('Домен отмечен БАН в GEO проекта.')
            source_state = network.read_network(db, source)
            target_state = network.read_network(db, target)
            from app.subdomain_naming import validate_unstarted_plan
            validate_unstarted_plan(db, run, target_state, cross=True)
            if any(plan.get(key) for key in ('rewrite_title_h1', 'rewrite_paragraphs')):
                if not run.plan.get('started_at'):
                    if (auto.digest(cfg.model_dump()) != plan['config_hash']
                            or not target_matches(db, run, target_state)
                            or source.id != target.id and not source_matches(db, run, source_state)):
                        raise ValueError('Сетки или настройки изменились до сохранения контента. Подготовьте план снова.')
                from app.reglue_content import before_network
                if not before_network(db, run, target_state): return
            deletion = db.get(models.NetworkOperation, receipt_id(run, 'delete_domain'))
            addition = db.get(models.NetworkOperation, receipt_id(run, 'create_domains'))
            if plan.get('reserve_pool_id'):
                from app import reglue_reserves as pool
                row = db.get(models.ReglueReserveDomain, plan['reserve_pool_id'])
                if row is None or row.run_id != run.id:
                    raise ValueError('Резервный домен не выделен этому запуску.')
                if addition is None:
                    pool.validate_plan(db, target, target_state, plan, run=run)
                    require_import_for_plan(db, target, target_state, plan)
                    if auto.digest(cfg.model_dump()) != plan['config_hash'] or not target_matches(db, run, target_state):
                        raise ValueError('Сетка или настройки изменились после предпросмотра.')
                    run.plan = {**run.plan, 'started_at': datetime.now(timezone.utc).isoformat()}; db.commit()
                if not change(db, run, target, 'create_domains', target_state, domains=[domain]):
                    return
                target_state = network.read_network(db, target)
                if domain not in target_state['domains']:
                    raise ValueError('Домен из базы резервов не появился в принимающей сетке.')
                if 'added_at' not in run.plan:
                    added_at = target_state.get('domain_added_at', {}).get(domain) or datetime.now(timezone.utc).isoformat()
                    target.domain_types = {**(target.domain_types or {}), domain: plan['domain_type']}
                    target.network_state = {**target.network_state, 'domain_added_at': {**target.network_state.get('domain_added_at', {}), domain: added_at}}
                    run.plan = {**run.plan, 'added_at': added_at}; db.commit()
                pool.mark_added(db, run, run.plan['added_at'])
            if plan.get('use_selected_reserve') or plan.get('local_target'):
                if not db.get(models.NetworkOperation, receipt_id(run, 'reglue')):
                    if plan.get('use_selected_reserve'):
                        require_selected_reserve(db, target, target_state, domain, plan=plan)
                    if not run.plan.get('started_at'):
                        if auto.digest(cfg.model_dump()) != plan['config_hash'] or not target_matches(db, run, target_state):
                            raise ValueError('Сетка изменилась после предпросмотра. Подготовьте план снова.')
                        from app.mass_main_targets import require_target
                        require_target(db, target, target_state, plan)
                        run.plan = {**run.plan, 'started_at': datetime.now(timezone.utc).isoformat()}; db.commit()
                if 'added_at' not in run.plan:
                    run.plan = {**run.plan, 'added_at': target_state.get('domain_added_at', {}).get(domain) or datetime.now(timezone.utc).isoformat()}; db.commit()
            else:
                if deletion is None:
                    require_import_for_plan(db, target, target_state, plan)
                    from app.mass_main_targets import require_target
                    require_target(db, source, source_state, plan)
                    if plan.get('requires_newreg') and (source.domain_types or {}).get(domain) != 'newreg':
                        raise ValueError('Для переклея без резерва требуется новорег. Тип домена изменился после подготовки плана.')
                    from app.domain_redirects import require_transfer_free
                    require_transfer_free(source_state, [domain])
                    if auto.digest(cfg.model_dump()) != plan['config_hash']:
                        raise ValueError('Настройки изменились после предпросмотра.')
                    if not source_matches(db, run, source_state) or not target_matches(db, run, target_state):
                        raise ValueError('Сетки изменились после предпросмотра. Подготовьте план снова.')
                    transferable(source, source_state, domain, plan=plan)
                    require_transfer_allowed(db, source, domain, plan=plan)
                    unique_membership(db, domain, {source.id})
                    run.plan = {**run.plan, 'started_at': datetime.now(timezone.utc).isoformat()}; db.commit()
                if not change(db, run, source, 'delete_domain', source_state, domain=domain):
                    return
                source_state = network.read_network(db, source)
                if any(domain_key(d) == domain_key(domain) for d in source_state['domains']):
                    raise ValueError('Извлечение домена из исходной сетки не подтверждено.')
                if not run.plan.get('source_released'):
                    run.plan = {**run.plan, 'source_released': True}; db.commit()
                if addition is None:
                    require_transfer_allowed(db, target, domain, plan=plan)
                    unique_membership(db, domain, set())
                    if target_state['canon'] != plan['old_main']:
                        raise ValueError('Main принимающей сетки изменился.')
                if not change(db, run, target, 'create_domains', target_state, domains=[domain]):
                    return
                target_state = network.read_network(db, target)
                if domain not in target_state['domains']:
                    raise ValueError('Домен не появился в принимающей сетке.')
                if 'added_at' not in run.plan:
                    added_at = target_state.get('domain_added_at', {}).get(domain) or datetime.now(timezone.utc).isoformat()
                    target.network_state = {**target.network_state, 'domain_added_at': {**target.network_state.get('domain_added_at', {}), domain: added_at}}
                    if plan.get('domain_type'):
                        target.domain_types = {**(target.domain_types or {}), domain: plan['domain_type']}
                    run.plan = {**run.plan, 'added_at': added_at}; db.commit()
            if plan.get('create_subdomain'):
                if not db.get(models.NetworkOperation, receipt_id(run, 'create_subdomains')):
                    from app.mass_main_targets import require_target
                    require_target(db, target, target_state, plan)
                if not change(db, run, target, 'create_subdomains', target_state, domains=[domain]):
                    return
                target_state = network.read_network(db, target)
                if domain not in target_state['domains']:
                    raise ValueError('Создание поддомена не подтверждено Webdev.')
            if not extractions_ready(db, run):
                raise SourceBusy('Домен добавлен из очереди. Ждём остальные извлечения группы перед сменой Main.')
            from app.reglue_settle import ready as provisioning_settled
            created = db.get(models.NetworkOperation, receipt_id(run, 'create_subdomains' if plan.get('create_subdomain') else 'create_domains'))
            if not provisioning_settled(db, run, created, target_state):
                return
            if plan.get('create_fake_main_path'):
                fake_path = plan['create_fake_main_path']
                if not db.get(models.NetworkOperation, receipt_id(run, 'create_fake_main')):
                    if target_state['canon'] != plan['old_main']:
                        raise ValueError('Main изменился до создания фейковой страницы.')
                    if fake_path in target_state.get('fake_main_paths', []) or fake_path in target_state.get('fake_main_history', []):
                        raise ValueError('Путь новой фейковой страницы уже занят. Подготовьте новый план.')
                if not change(db, run, target, 'create_fake_main', target_state,
                              fake_main_path=fake_path, activate_fake_main=True):
                    return
                target_state = network.read_network(db, target)
                if (target_state.get('fake_main_current') != fake_path or not target_state.get('fake_main_enabled')
                        or fake_path not in target_state.get('fake_main_paths', [])):
                    raise ValueError('Новый действующий фейковый внутряк изменился вне запуска.')
            try:
                from app.reglue_dns import verify_pages
                verify_pages(db, target, run, target_state)
            except (httpx.HTTPError, ValueError) as error:
                address = ', '.join(plan['required_page_urls'])
                run.status = 'waiting'
                run.message = 'Новый Main ещё недоступен: ' + address + ' — ' + str(error)[:700]
                db.commit(); return
            for action in ('reserve', 'reglue', 'alternates'):
                target_state = network.read_network(db, target)
                receipt = db.get(models.NetworkOperation, receipt_id(run, action))
                if plan.get('fake_main_path') and (target_state.get('fake_main_current') != plan['fake_main_path']
                        or not target_state.get('fake_main_enabled') or plan['fake_main_path'] not in target_state.get('fake_main_paths', [])):
                    raise ValueError('Действующий фейковый внутряк изменился вне запуска.')
                if receipt is None:
                    if action == 'reglue':
                        from app.reglue_reserves import require_unused
                        require_unused(target, target_state, domain, plan=plan)
                    if action == 'reglue' and plan.get('main_target_kind'):
                        from app.mass_main_targets import require_target
                        require_target(db, target, target_state, plan, allow_created=True)
                    expected = domain if action == 'alternates' else plan['old_main']
                    if target_state['canon'] != expected:
                        raise ValueError('Main изменился вне этого запуска.')
                    # Creating the new fake route also retargets its links in head.
                    # Intermediate alternates are not the reviewed final result:
                    # the alternates step below writes the saved plan and verifies it.
                if not change(db, run, target, action, target_state, domain=domain, alternate_markup=plan['alternateMarkup'], enable_alternates=plan['enableAlternates'],
                              fake_main_path=(plan.get('fake_main_path') or '') if action == 'alternates' else '',
                              canonical_fake_main_markup=plan.get('canonicalFakeMainMarkup') if action == 'alternates' else None):
                    return
                if action == 'reglue' and not run.plan.get('reglued_at'):
                    from app.domain_transfer_policy import record_transfer_cooldown
                    at = datetime.now(timezone.utc).isoformat()
                    deadline = record_transfer_cooldown(db, domain, run.plan['added_at'], at)
                    run.plan = {**run.plan, 'reglued_at': at, 'transfer_not_before': deadline}; db.commit()
            target_state = network.read_network(db, target)
            from app.network_indexing import queue_indexing, verified
            if plan.get('fake_main_path') and (not target_state.get('enableCanonical')
                    or target_state.get('canonicalFakeMainMarkup') != plan['canonicalFakeMainMarkup']
                    or not target_state.get('fake_main_enabled') or target_state.get('fake_main_current') != plan['fake_main_path']
                    or plan['fake_main_path'] not in target_state.get('fake_main_paths', [])):
                run.status = 'waiting'; run.message = 'Ждём подтверждения canonical нового фейкового внутряка.'; db.commit(); return
            if not verified(target_state, {'canon': domain, 'alternateMarkup': plan['alternateMarkup'], 'enableAlternates': plan['enableAlternates']}):
                run.status = 'waiting'; run.message = 'Ждём подтверждения итогового Main и альтернейтов чтением Webdev.'; db.commit(); return
            from app.network_sitemap import queue as queue_sitemap
            queue_sitemap(db, target, run.id, run.initiator); db.commit()
            queue_indexing(db, target, target_state, run.id, run.initiator)
            now = datetime.now(timezone.utc)
            run.plan = {**run.plan, 'alternates_after': {'markup': target_state['alternateMarkup'], 'enabled': target_state['enableAlternates']},
                        'applied_result': {'new_main': target_state['canon'], 'fake_main_path': target_state.get('fake_main_current') or None, 'confirmed_at': now.isoformat()},
                        'completed_at': now.isoformat(), 'elapsed_seconds': (now - datetime.fromisoformat(run.plan['started_at'])).total_seconds()}
            run.status = 'completed'; run.phase = 'completed'; run.message = ('Домен из базы резервов добавлен и стал Main. ' if plan.get('reserve_pool_id') else 'Выбранный резерв стал Main. ' if plan.get('use_selected_reserve') else 'Поддомен создан и стал Main. ' if plan.get('create_subdomain') else 'Домен своей сетки стал Main. ' if plan.get('local_target') else 'Домен перенесён и стал Main. ') + 'Альтернейты подтверждены; история сохранена.'; refresh_run(db, run); db.commit()
    except (SourceBusy, network.NetworkConflict) as error:
        db.rollback(); db.refresh(run)
        run.status = 'waiting'; run.message = str(error)[:2000]; refresh_run(db, run); db.commit()
    except Exception as error:
        db.rollback(); db.refresh(run)
        from app.reglue_content import failure_status
        from app.webdev_read_retry import retryable
        run.plan = {**run.plan, 'read_retryable': retryable(error)}
        run.status = 'partial' if any(db.get(models.NetworkOperation, receipt_id(run, a)) for a in ('delete_domain','create_domains','create_subdomains','reglue')) else failure_status(db, run, True)
        run.message = str(error)[:2000]; refresh_run(db, run); db.commit()

    finally:
        if plan.get('reserve_pool_id'):
            from app.reglue_reserves import sync_result
            sync_result(db, run)
