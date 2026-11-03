"""One durable allocation for a mass launch: large donors to small recipients."""
from contextlib import ExitStack
from uuid import uuid4
from sqlalchemy import select
from app import models, project_network as network
from app import auto_reglue as auto, cross_reglue as cross
from app.mass_action_scope import constrain, stamp_plan


def key(batch_id):
    return 'cross-batch:' + batch_id


def allocate(targets, donors, states, free):
    """One incoming per recipient; peer cycles never send a domain straight back."""
    groups = {}
    for site in targets:
        groups.setdefault((cross.brand_key(site.brand), cross.geo_key(site.cache_geo)), []).append(site)
    assignments, used = [], {site.id: 0 for site in donors}
    def give(source, target, mode):
        assignments.append((target, source.id, mode))
        used[source.id] += 1
    for group, recipients in sorted(groups.items()):
        sources = [s for s in donors if (cross.brand_key(s.brand), cross.geo_key(s.cache_geo)) == group]
        sources.sort(key=lambda s: (s.name, s.id))
        peers = sorted((s for s in recipients if free.get(s.id)), key=lambda s: (s.name, s.id))
        if len(peers) >= 3:
            # Uniform circulation uses at least three projects, never A <-> B.
            for index, source in enumerate(peers):
                give(source, peers[(index + 1) % len(peers)], 'peer_exchange')
        elif peers:
            external = [s for s in sources if s.id not in {p.id for p in peers}]
            if external:
                external.sort(key=lambda s: (-len(states[s.id]['domains']), s.name, s.id))
                give(external[0], peers[0], 'peer_exchange')
                if len(peers) == 2:
                    give(peers[0], peers[1], 'peer_exchange')
            elif len(peers) == 2:
                larger, smaller = sorted(peers, key=lambda s: (-len(states[s.id]['domains']), s.name, s.id))
                give(larger, smaller, 'peer_exchange')
        # A small network with no free roots receives without having to reciprocate.
        for target in sorted((s for s in recipients if not free.get(s.id)),
                             key=lambda s: (len(states[s.id]['domains']), s.name, s.id)):
            candidates = [s for s in sources if used[s.id] < min(10, len(free[s.id]))
                          and len(states[s.id]['domains']) - used[s.id] > len(states[target.id]['domains'])]
            if candidates:
                candidates.sort(key=lambda s: (-(len(states[s.id]['domains']) - used[s.id]), s.name, s.id))
                give(candidates[0], target, 'redistribute')
    return assignments


def build(db, targets, username, *, persist=True):
    """Capture one live snapshot and allocate unique domains with durable quotas."""
    import httpx
    from app.project_cache import ProjectCacheError
    targets = list({site.id: site for site in targets}.values())
    cfg = auto.config(db)
    if not db.info.get('pilot_mixed') and (cfg.execution_mode != 'cross_network' or cfg.scheme_mode not in {'preserve', 'clean', 'locale_base'}):
        raise ValueError('Выберите перекрёстный режим с сохранением схемы, чистым или базовым альтернейтом по языку и GEO.')
    groups = {(cross.brand_key(s.brand), cross.geo_key(s.cache_geo)) for s in targets}
    allowed = db.info.get('cross_allowed_site_ids')
    filters = db.info.get('mass_action_filter') or (cfg.selection_filter.model_dump() if cfg.selection_filter else None)
    if filters:
        allowed = constrain(db, filters, allowed, targets)
    if db.info.get('mass_participant_ids') is not None:
        participants = db.info['mass_participant_ids']
        allowed = participants if allowed is None else allowed.intersection(participants)
    query = select(models.Site).where(models.Site.is_active.is_(True), models.Site.project_status == 'mass_actions')
    if allowed is not None:
        query = query.where(models.Site.id.in_(allowed))
    states, sites, skipped, reasons = {}, {}, [], {}
    for site in db.scalars(query):
        if (cross.brand_key(site.brand), cross.geo_key(site.cache_geo)) not in groups:
            continue
        try:
            from app.mass_reglue_launch import manual_pilot_allowed
            auto.require_eligible(site, cfg, auto.config(db, site.id), preview_only=bool(db.info.get('auto_pilot_preview')),manual=manual_pilot_allowed(db,site.id))
            brand, geo = cross.brand_key(site.brand), cross.geo_key(site.cache_geo)
            if not brand or len(geo) != 2 or not geo.isalpha():
                raise ValueError('Для переноса должны быть заданы бренд и GEO проекта.')
            if auto.config(db, site.id).scope == 'personal' or auto.active_run(db, site.id):
                raise ValueError('Сетка имеет персональные настройки или незавершённую операцию.')
            if db.info.get('auto_pilot_preview'):
                from app.reglue_history import weekly_reason
                if reason := weekly_reason(site): raise ValueError(reason)
            state = network.read_network(db, site)
            if not state.get('head_verified', state.get('has_head')):
                raise ValueError('Не подтверждены актуальные альтернейты сетки.')
            states[site.id], sites[site.id] = state, site
        except (ValueError, httpx.HTTPError, ProjectCacheError) as error:
            reasons[site.id] = str(error)[:1500]
    free = {}
    for site_id, site in sites.items():
        free[site_id] = []
        # General-keyword sites may receive stock, but are not cross-brand donors.
        if cross.brand_key(site.brand) == cross.brand_key('Общие ключи'):
            continue
        for domain in states[site_id]['domains']:
            if domain in db.info.get('reglue_preview_domains', set()): continue
            if (site.domain_types or {}).get(domain) not in ({'newreg'} if cfg.main_target_mode == 'legacy' else {'newreg','drop'}):
                continue
            try:
                cross.transferable(site, states[site_id], domain)
                cross.require_transfer_allowed(db, site, domain)
                cross.unique_membership(db, domain, {site_id})
            except ValueError:
                continue
            free[site_id].append(domain)
            if cfg.main_target_mode == 'legacy' and not db.info.get('prefer_own_domains') and len(free[site_id]) == 10:
                break
    distribution = None
    if db.info.get('prefer_own_domains') and (cfg.main_target_mode == 'legacy' or db.info.get('pilot_mixed')):
        from app.priority_main_targets import build as build_priority
        plans, priority_reasons = build_priority(db, cfg, [s for s in targets if s.id in sites], sites, states, free)
        reasons.update(priority_reasons)
    elif cfg.main_target_mode != 'legacy':
        from app.mass_main_targets import build as build_targets
        ready_targets = [s for s in targets if s.id in sites]
        plans, policy_reasons, distribution = build_targets(db, cfg, ready_targets, sites, states, free, cross=cross)
        reasons.update(policy_reasons)
    else:
        local_targets = [site for site in targets if site.id in sites and cross.selected_reserve(states[site.id]) and not cross.blocked_reserve(db, site, states[site.id])]
        eligible_targets = [site for site in targets if site.id in sites and not cross.selected_reserve(states[site.id])]
        from app import reglue_reserves as pool
        pool_plans, pool_domains = [], set()
        for target in [s for s in targets if s.id in sites and (not cross.selected_reserve(states[s.id]) or cross.blocked_reserve(db, s, states[s.id]))]:
            blocked = cross.blocked_reserve(db, target, states[target.id])
            entry = pool.candidate(db, target, states[target.id], ['newreg'] if blocked else ['drop', 'newreg'], pool_domains)
            if entry:
                try:
                    pool_plans.append(pool.make_plan(db, cfg, target, states[target.id], entry, pool_plans))
                    pool_domains.add(entry.domain)
                except ValueError as error:
                    reasons[target.id] = 'Не удалось подготовить схему: ' + str(error)
        pool_targets = {p['site_id'] for p in pool_plans}
        eligible_targets = [s for s in eligible_targets if s.id not in pool_targets]
        assigned = allocate(eligible_targets, [s for s in sites.values() if free[s.id]], states, free)
        outgoing = {}
        directions = set()
        for recipient, source_id, _ in assigned:
            outgoing[source_id] = outgoing.get(source_id, 0) + 1
            directions.add((source_id, recipient.id))
        for target in [s for s in targets if s.id in sites and s.id not in pool_targets and cross.blocked_reserve(db, s, states[s.id])]:
            candidates = [s for s in sites.values() if s.id != target.id and outgoing.get(s.id,0) < min(10,len(free[s.id]))
                          and (target.id,s.id) not in directions
                          and (cross.brand_key(s.brand),cross.geo_key(s.cache_geo)) == (cross.brand_key(target.brand),cross.geo_key(target.cache_geo))]
            candidates.sort(key=lambda s:(-len(states[s.id]['domains']),s.name,s.id))
            if candidates:
                source=candidates[0];assigned.append((target,source.id,'banned_reserve_fallback'))
                outgoing[source.id]=outgoing.get(source.id,0)+1;directions.add((source.id,target.id))
            else:reasons[target.id]='Резерв в БАН; нет разрешённого новорега в другой сетке того же бренда и GEO.'
        plans = list(pool_plans)
        for target in local_targets:
            try:
                plan = cross.reserve_plan(cfg, target, states[target.id], db=db, plans=plans)
                cross.require_selected_reserve(db, target, states[target.id], plan['new_main'])
                plans.append(stamp_plan(db, plan, states[target.id], target))
            except ValueError as error:
                reasons[target.id] = str(error)
        used = {site_id: 0 for site_id in free}
        for target, source_id, mode in assigned:
            from app.reglue_reserves import require_unused
            domain = None
            while used[source_id] < len(free[source_id]):
                candidate_domain = free[source_id][used[source_id]]
                used[source_id] += 1
                try: require_unused(target, states[target.id], candidate_domain)
                except ValueError: continue
                domain = candidate_domain; break
            if domain is None:
                reasons[target.id] = 'Доступные домены донора уже были Main в принимающей сетке.'
                continue
            try:
                plans.append(stamp_plan(db, cross.make_plan(cfg, target, states[target.id], sites[source_id], states[source_id], domain, mode=mode, db=db, plans=plans), states[target.id], target))
            except ValueError as error:
                reasons[target.id] = 'Не удалось подготовить схему: ' + str(error)
    received = {plan['site_id'] for plan in plans}
    for site in targets:
        if site.id not in received:
            skipped.append({'site_id': site.id, 'project': site.name, 'error': reasons.get(site.id,
                'Нет свободного домена в сетках того же бренда и GEO с учётом лимита 10 извлечений и одного добавления.')})
            if db.info.get('auto_pilot_preview') and db.info.get('prefer_own_domains'):
                from app.priority_main_targets import retry_snapshot
                state = retry_snapshot(reasons.get(site.id), states.get(site.id))
                if state:
                    skipped[-1]['retry_state'] = state
    if not persist:
        return {'plans': plans, 'skipped': skipped, 'distribution': distribution}
    batch_id = str(uuid4())
    for plan in plans:
        plan.pop('preview_token', None)
        plan['batch_id'] = batch_id
        plan['preview_token'] = auto.digest(plan)
    validate(plans)
    db.add(models.AutoReglueConfig(key=key(batch_id), value={
        'created_by': username, 'plans': plans, 'skipped': skipped, 'run_ids': {}, 'filter': filters, 'distribution': distribution}))
    db.commit()
    return {'batch_id': batch_id, 'plans': plans, 'skipped': skipped, 'distribution': distribution}


def validate(plans):
    from app.pilot_schemes import validate_single_alternate
    outgoing, incoming, domains, exchanges, directions = {}, set(), set(), set(), set()
    for plan in plans:
        validate_single_alternate(plan)
        source, target = plan['source_site_id'], plan['site_id']
        domain = cross.domain_key(plan['new_main'])
        if plan.get('use_selected_reserve') or plan.get('local_target'):
            if source != target or target in incoming or domain in domains:
                raise ValueError('Резерв должен использоваться только в своей сетке один раз.')
            incoming.add(target); domains.add(domain)
            continue
        if source == target or (target, source) in directions:
            raise ValueError('Встречный перенос A → B и B → A в одном массовом запуске запрещён.')
        directions.add((source, target))
        outgoing[source] = outgoing.get(source, 0) + 1
        if outgoing[source] > 10 or target in incoming or domain in domains:
            raise ValueError('Лимит массового переноса: не более 10 доменов из сетки и одного домена в сетку.')
        if plan.get('balance_mode') == 'peer_exchange':
            if source in exchanges:
                raise ValueError('Резервный обмен: не более одного домена из каждой крупной сетки.')
            exchanges.add(source)
        elif plan.get('replace_banned_reserve') and plan.get('balance_mode') == 'banned_reserve_fallback':
            pass
        elif plan['source_count'] <= plan['target_count']:
            raise ValueError('Домен можно переносить только из большей сетки в меньшую.')
        incoming.add(target); domains.add(domain)


def manifest(db, batch_id):
    row = db.get(models.AutoReglueConfig, key(batch_id))
    if row is None:
        raise ValueError('План массового распределения не найден. Подготовьте его заново.')
    validate(row.value['plans'])
    return row


def reserve(db, batch_id, items, username, *, scheduled=None):
    """Reserve the complete group before any worker can extract a domain."""
    with network.network_lock(db, 'reglue-reserve-pool'), network.network_lock(db, key(batch_id)), ExitStack() as locks:
        row = manifest(db, batch_id)
        plans = {plan['site_id']: plan for plan in row.value['plans']}
        if len({item['site_id'] for item in items}) != len(items) or len({str(item['request_id']) for item in items}) != len(items):
            raise ValueError('В группе повторяется проект или идентификатор запуска.')
        selected = []
        for item in items:
            plan = plans.get(item['site_id'])
            if not plan or item['preview_token'] != plan['preview_token']:
                raise network.NetworkConflict('План распределения изменился. Подготовьте группу заново.')
            selected.append((item, plan))
        results = []
        receipts = dict(row.value.get('run_ids', {}))
        staged = []
        for item, plan in selected:
            request_id = str(item['request_id'])
            if plan['site_id'] in receipts and receipts[plan['site_id']] != request_id:
                raise network.NetworkConflict('Принимающая сетка уже включена в этот массовый запуск.')
            existing = db.get(models.AutoReglueRun, request_id)
            if existing:
                if existing.site_id != item['site_id'] or existing.plan.get('batch_id') != batch_id:
                    raise ValueError('Идентификатор запуска уже используется.')
                results.append((existing, False)); continue
            source = db.get(models.Site, plan['source_site_id'])
            target = db.get(models.Site, plan['site_id'])
            if not (plan.get('use_selected_reserve') or plan.get('local_target')):
                cross.require_pair(source, target)
            if any(auto.config(db, s.id).scope == 'personal' for s in (source, target)):
                raise ValueError('Сетка переведена на персональные настройки.')
            run = models.AutoReglueRun(id=request_id, site_id=target.id, initiator=username,
                status='planned' if scheduled else 'queued', phase='prepared', plan=dict(plan))
            # Reads acquire their own participant locks and may commit observations.
            # No run is inserted until every member has passed these checks.
            source_state = network.read_network(db, source)
            target_state = network.read_network(db, target)
            if not cross.source_matches(db, run, source_state) or not cross.target_matches(db, run, target_state):
                raise network.NetworkConflict('Сетки изменились после предпросмотра. Подготовьте группу заново.')
            from app.reglue_reserves import require_unused
            require_unused(target, target_state, plan['new_main'])
            if plan.get('reserve_pool_id'):
                from app.reglue_reserves import validate_plan
                cross.require_import_for_plan(db, target, target_state, plan)
                validate_plan(db, target, target_state, plan)
            elif plan.get('use_selected_reserve') or plan.get('local_target'):
                if plan.get('use_selected_reserve'):
                    cross.require_selected_reserve(db, target, target_state, plan['new_main'])
                from app.mass_main_targets import require_target
                require_target(db, target, target_state, plan)
            else:
                cross.require_import_for_plan(db, target, target_state, plan)
                from app.mass_main_targets import require_target
                require_target(db, source, source_state, plan)
                if plan.get('requires_newreg') and (source.domain_types or {}).get(plan['new_main']) != 'newreg':
                    raise ValueError('Для переклея без резерва требуется новорег.')
                cross.transferable(source, source_state, plan['new_main'])
                cross.require_transfer_allowed(db, source, plan['new_main'])
                cross.unique_membership(db, plan['new_main'], {source.id})
            staged.append(run)
        for site_id in sorted({p[k] for _, p in selected for k in ('site_id', 'source_site_id')}):
            locks.enter_context(network.network_lock(db, site_id))
        from app.fake_path_allocation import group, group_lock, require_available
        groups = {group(db.get(models.Site, run.site_id)): db.get(models.Site, run.site_id) for run in staged}
        for path_group in sorted(groups):
            locks.enter_context(group_lock(db, groups[path_group]))
        for run in staged:
            plan = run.plan
            require_available(db, db.get(models.Site, run.site_id), plan.get('fake_main_path'), [r.plan for r in staged])
            if auto.digest(auto.config(db).model_dump()) != plan['config_hash']:
                raise network.NetworkConflict('Настройки изменились после предпросмотра.')
            if any(auto.blocking_run(db, site_id, run) for site_id in (plan['source_site_id'], run.site_id)):
                raise network.NetworkConflict('Одна из сеток уже участвует в другом запуске.')
            if scheduled:
                schedule, due, now = scheduled[run.site_id]
                run.plan = {**run.plan, 'scheduled': True, 'scheduled_for': due.isoformat()}
                auto.advance_schedule(schedule, due, now)
            db.add(run); db.flush()
            if plan.get('reserve_pool_id'):
                from app.reglue_reserves import claim
                claim(db, run)
            receipts[run.site_id] = run.id
            results.append((run, True))
        row.value = {**row.value, 'run_ids': receipts}
        if scheduled:
            for skip in row.value['skipped']:
                schedule, due, now = scheduled[skip['site_id']]
                request_id = str(auto.uuid5(auto.NAMESPACE_URL, f'auto-reglue:{schedule.site_id}:{due.isoformat()}'))
                if not db.get(models.AutoReglueRun, request_id):
                    db.add(models.AutoReglueRun(id=request_id, site_id=schedule.site_id, initiator='scheduler',
                        status='failed', phase='prepared', plan={'project': skip['project'], 'scheduled': True,
                        'batch_id': batch_id, 'scheduled_for': due.isoformat()}, message=skip['error']))
                auto.advance_schedule(schedule, due, now)
        db.commit()
        if row.value.get('filter'):
            from app.mass_action_reports import save
            save(db, batch_id, row.value['filter'], [{'site_id': run.site_id, 'run_id': run.id} for run, _ in results], username, row.value['skipped'])
    return results


def authorize(db, run):
    """Execution uses only the allocation that was reserved durably."""
    batch_id = run.plan.get('batch_id')
    if not batch_id:
        return  # Legacy single-recipient launch: one outgoing, one incoming.
    row = manifest(db, batch_id)
    if row.value.get('run_ids', {}).get(run.site_id) != run.id:
        raise ValueError('Запуск не зарезервирован в массовом распределении.')
    original = next((p for p in row.value['plans'] if p['site_id'] == run.site_id), None)
    if not original or any(run.plan.get(k) != v for k, v in original.items()):
        raise ValueError('Исходный план распределения изменён.')


def schedule(db, enqueue, now):
    """Reserve all recipients in the due cycle; dispatch in max_projects portions."""
    if not auto.config(db).enabled or not auto.config(db).schedule_enabled:
        return []
    due_rows = db.scalars(select(models.AutoReglueSchedule).where(
        models.AutoReglueSchedule.enabled.is_(True)).order_by(models.AutoReglueSchedule.next_run_at)).all()
    candidates, timing = [], {}
    for row in due_rows:
        site = db.get(models.Site, row.site_id)
        if (not site or auto.config(db, site.id).scope == 'personal' or auto.active_run(db, site.id)
                or row.interval_days == 0 and row.last_scheduled_at
                or auto.utc(row.next_run_at) > now):
            continue
        if auto.schedule_eligible(site, auto.config(db), auto.config(db, site.id)):
            candidates.append(site)
            timing[site.id] = (row, auto.utc(row.next_run_at), now)
    if candidates:
        batch = build(db, candidates, 'scheduler')
        items = [{'site_id': p['site_id'], 'request_id': str(auto.uuid5(auto.NAMESPACE_URL,
            f"auto-reglue:{p['site_id']}:{timing[p['site_id']][1].isoformat()}")),
            'preview_token': p['preview_token']} for p in batch['plans']]
        reserve(db, batch['batch_id'], items, 'scheduler', scheduled=timing)
    ready = db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.status.in_(['planned', 'queued']))
                       .order_by(models.AutoReglueRun.created_at, models.AutoReglueRun.id)).all()
    started = []
    for run in ready:
        if not run.plan.get('scheduled') or run.plan.get('execution_mode') != 'cross_network':
            continue
        if len(started) >= auto.config(db).max_projects:
            break
        run.status = 'queued'; db.commit()
        enqueue(run.id); started.append(run.id)
    return started
