"""Typed Main allocation for a mass cycle; previews never provision domains."""
from collections import Counter
from types import SimpleNamespace
from app.domain_classification import classify_domains
from app.domain_transfer_policy import banned_domains, domain_key, geo_key
from app.subdomain_naming import next_subdomain

KINDS = ('newreg', 'drop', 'sub_newreg', 'sub_drop')
LABELS = {'newreg': 'Новорег', 'drop': 'Дроп', 'sub_newreg': 'Поддомен новорега', 'sub_drop': 'Поддомен дропа'}


def quotas(count, cfg):
    # Integer arithmetic implements conventional half-up rounding, not bankers' rounding.
    newreg = (count + 1) // 2 if cfg.main_target_mode == 'mixed' else count if cfg.main_target_mode == 'newreg' else 0
    drop = count - newreg
    sub_newreg = min(newreg, (count + 5) // 10) if cfg.newreg_subdomain_share else 0
    sub_drop = min(drop, (count + 5) // 10) if cfg.drop_subdomain_share else 0
    return dict(newreg=newreg-sub_newreg, drop=drop-sub_drop, sub_newreg=sub_newreg, sub_drop=sub_drop)


def target_kind(site, state, domain):
    role = classify_domains([*state['domains'], domain], site.domain_types or {}).get(domain, {})
    parent = role.get('parent_domain') if role.get('is_subdomain') else domain
    kind = (site.domain_types or {}).get(parent) or (site.domain_types or {}).get(domain_key(parent))
    return ('sub_' if role.get('is_subdomain') else '') + kind if kind in {'newreg', 'drop'} else None


def require_target(db, site, state, plan, *, allow_created=False):
    """Recheck the exact type and exclusions before any irreversible stage."""
    if not plan.get('main_target_kind'):
        return
    domain = plan['new_main']
    expected = plan['main_target_kind']
    parent = plan.get('parent_domain') or domain
    if target_kind(site, state, domain) != expected:
        raise ValueError('Тип домена/родителя изменился после предпросмотра. Подготовьте планы заново.')
    if parent not in state['domains'] or (domain not in state['domains'] and not (plan.get('create_subdomain') and not allow_created)):
        raise ValueError('Домен или родитель поддомена отсутствует в сетке.')
    bans = banned_domains(db, site, [domain, parent])
    if bans.get(parent) and plan.get('maintenance_repeat_id'):
        from app.maintenance_repeat import parent_allowed
        if parent_allowed(db, site, state, plan):
            bans[parent] = False
    if any(bans.values()) or any(d in state.get('amp_domains', []) for d in (domain, parent)):
        raise ValueError('Домен или родитель поддомена отмечен БАН или AMP.')
    used = {domain_key(d) for d in [*(site.main_domain_history or []), state['canon'], state.get('prev')] if d}
    if plan.get('emergency_subdomain') and domain_key(parent) in used:
        raise ValueError('Родитель аварийного поддомена уже использовался как Main.')
    from app.reglue_reserves import authorized_own_drop_reuse
    from app.pilot_domain_reuse import allows, validate as validate_reuse
    reuse = allows(site,state,domain,plan) and validate_reuse(db,plan)
    if domain_key(domain) in used and not (authorized_own_drop_reuse(site, state, domain, plan) or reuse):
        raise ValueError('Выбранный домен уже использовался как Main.')
    if plan.get('create_subdomain') and domain in state['domains'] and not allow_created:
        raise ValueError('Имя поддомена занято после подготовки плана.')


def subdomain_candidate(db, site, state, kind, cfg, *, prefer_geo=False, excluded_parents=(), allocation_plans=()):
    parent_kind = kind.removeprefix('sub_')
    roles = classify_domains(state['domains'], site.domain_types or {})
    from app import auto_reglue as auto
    project_options = auto.effective_project_config(cfg, auto.config(db, site.id))
    options = SimpleNamespace(parent_kind=parent_kind, language=(site.cache_language or '').lower().replace('_', '-').split('-')[0],
        subdomain_add_casino=project_options.subdomain_add_casino, subdomain_name_style=project_options.subdomain_name_style)
    # Both inputs come from the same freshly verified live network snapshot.
    naming_site = SimpleNamespace(id=site.id, name=site.name, brand=site.brand, cache_geo=geo_key(site.cache_geo).lower(),
        cache_language=site.cache_language or '', cache_domains=state['domains'], domain_types=site.domain_types or {},
        main_domain_history=site.main_domain_history or [], alternate_domain_history=site.alternate_domain_history or [],
        x_default_history=getattr(site, 'x_default_history', None) or [])
    from app.naming_variants import allocation_index
    index = allocation_index([*db.info.get('canonical_allocation_plans', []), *allocation_plans], site.id, subdomains=True)
    for parent in state['domains']:
        if domain_key(parent) in excluded_parents:
            continue
        if roles[parent]['is_subdomain'] or target_kind(site, state, parent) != parent_kind:
            continue
        if parent in state.get('amp_domains', []) or banned_domains(db, site, [parent])[parent]:
            continue
        try:
            child = next_subdomain(naming_site, state, options, parent, allocation_index=index)
            from app.cross_reglue import unique_membership
            unique_membership(db, child, {site.id})
            return parent, child
        except ValueError:
            continue
    raise ValueError('Нет доступного родителя/имени для доли «' + LABELS[kind] + '».')


def build(db, cfg, targets, sites, states, free, *, cross):
    """Allocate each quota once; shortages use a newreg from a strictly larger donor."""
    requested = quotas(len(targets), cfg)
    remaining = dict(requested)
    plans, reasons, done = [], {}, set()
    used_domains, directions, exchanges = {domain_key(d) for d in db.info.get('reglue_preview_domains', ())}, set(), set()
    outgoing = Counter()
    grouped = sorted(targets, key=lambda s: (-len(states[s.id]['domains']), s.name, s.id))
    blocked = {s.id for s in targets if cross.blocked_reserve(db, s, states[s.id])}
    def reserved(site):return cross.selected_reserve(states[site.id]) and site.id not in blocked

    def add(target, source, domain, slot, *, local=False, parent=None, create=False, fallback=False, mode='redistribute'):
        if domain_key(domain) in used_domains:raise ValueError('Домен уже назначен другому проекту в этом плане.')
        state, source_state = states[target.id], states[source.id]
        plan = (cross.reserve_plan(cfg, target, state, db=db, plans=plans) if local and cross.selected_reserve(state) == domain
                else cross.make_plan(cfg, target, state, source, source_state, domain, mode=mode, db=db, plans=plans))
        actual = ('sub_' + ((target.domain_types or {}).get(parent) or (target.domain_types or {}).get(domain_key(parent)))) if parent else target_kind(source, source_state, domain)
        plan.update(main_target_kind=actual, requested_target_kind=slot, target_fallback=fallback,
                    requires_newreg=False, required_domain_type=actual.removeprefix('sub_'),
                    domain_type=actual.removeprefix('sub_'))
        if local:
            plan.update(local_target=True, balance_mode='selected_reserve' if plan.get('use_selected_reserve') else 'local_subdomain')
        if parent:
            plan['parent_domain'] = parent
        if create:
            plan['create_subdomain'] = domain
        if fallback:
            plan['fallback_reason'] = plan.get('fallback_reason') or 'Нет подходящего домена для «' + LABELS[slot] + '»; выбран новорег из большей сетки.'
        plan.pop('preview_token', None)
        from app.auto_reglue import digest
        plan['preview_token'] = digest(plan)
        from app.mass_action_scope import stamp_plan
        plans.append(stamp_plan(db, plan, state, target));done.add(target.id);used_domains.add(domain)
        if parent:used_domains.add(parent)
        remaining[slot] -= 1
        if not local:
            outgoing[source.id] += 1; directions.add((source.id, target.id))
            if mode == 'peer_exchange':exchanges.add(source.id)

    # A selected reserve is never silently replaced by an import.
    for target in grouped:
        state = states[target.id];domain = cross.selected_reserve(state)
        if not domain or target.id in blocked:continue
        slot = target_kind(target, state, domain)
        if slot not in remaining or remaining[slot] <= 0:
            reasons[target.id] = 'Выбранный резерв не соответствует типу/доле цикла. Измените или снимите резерв.';continue
        try:
            cross.require_selected_reserve(db, target, state, domain)
            role = classify_domains(state['domains'], target.domain_types or {})[domain]
            probe={'new_main':domain,'main_target_kind':slot,'parent_domain':role.get('parent_domain')}
            require_target(db,target,state,probe)
            add(target,target,domain,slot,local=True,parent=role.get('parent_domain'))
        except ValueError as error:reasons[target.id]=str(error)

    # Scarce subdomain slots go to projects that already own a suitable parent.
    for slot in ('sub_newreg','sub_drop'):
        for target in grouped:
            if remaining[slot] <= 0:break
            if target.id in done or reserved(target) or target.id in blocked:continue
            try:
                parent, child = subdomain_candidate(db,target,states[target.id],slot,cfg,allocation_plans=plans)
                add(target,target,child,slot,local=True,parent=parent,create=True)
            except ValueError as error:reasons[target.id]=str(error)

    def donor_for(target, kind, *, fallback):
        options=[]
        for source in sites.values():
            if source.id == target.id or (target.id, source.id) in directions :
                continue
            try:cross.require_pair(source,target)
            except ValueError:continue
            allowed_kinds = {'newreg','drop'} if cfg.main_target_mode == 'mixed' else {cfg.main_target_mode}
            target_has_free = any(d not in used_domains and target_kind(target,states[target.id],d) in allowed_kinds for d in free.get(target.id,[]))
            if fallback or not target_has_free:
                mode='banned_reserve_fallback' if target.id in blocked else 'brand_geo_capacity'
            else:
                mode='brand_geo_capacity'
            from app.reglue_reserves import require_unused
            domain = None
            for d in free.get(source.id, []):
                if d in used_domains or target_kind(source, states[source.id], d) != kind: continue
                try: require_unused(target, states[target.id], d)
                except ValueError: continue
                domain = d; break
            if domain:options.append((source,domain,mode))
        options.sort(key=lambda row:(-len(states[row[0].id]['domains'])+outgoing[row[0].id],row[0].name,row[0].id))
        return options[0] if options else None

    # Fresh inventory is consumed before moving domains out of existing networks.
    from app import reglue_reserves as pool
    for slot in ('newreg', 'drop'):
        for target in grouped:
            if remaining[slot] <= 0: break
            if target.id in done or reserved(target): continue
            if target.id in blocked and slot != 'newreg': continue
            entry = pool.candidate(db, target, states[target.id], [slot], used_domains)
            if entry:
                plans.append(pool.make_plan(db, cfg, target, states[target.id], entry, plans, slot))
                done.add(target.id); used_domains.add(entry.domain); remaining[slot] -= 1

    # Interleave the two root types; keep exclusions and unique domain allocation.
    while remaining['newreg'] or remaining['drop']:
        progressed=False
        for slot in ('newreg','drop'):
            if remaining[slot] <= 0:continue
            for target in grouped:
                if target.id in done or reserved(target) or target.id in blocked:continue
                candidate=donor_for(target,slot,fallback=False)
                if not candidate:continue
                source,domain,mode=candidate
                add(target,source,domain,slot,mode=mode);progressed=True;break
        if not progressed:break

    # Explicit fallback requested by the user, including an unavailable subdomain slot.
    for slot in KINDS:
        for target in grouped:
            if remaining[slot] <= 0:break
            if target.id in done or reserved(target):continue
            entry = pool.candidate(db, target, states[target.id], ['newreg'], used_domains)
            if entry:
                plans.append(pool.make_plan(db, cfg, target, states[target.id], entry, plans, slot))
                done.add(target.id); used_domains.add(entry.domain); remaining[slot] -= 1
                continue
            candidate=donor_for(target,'newreg',fallback=True)
            if candidate:
                source,domain,mode=candidate
                add(target,source,domain,slot,fallback=True,mode=mode)
            else:
                reasons[target.id]='Нет подходящего домена для цикла и свободного новорега в большей сетке того же бренда и GEO.'
    actual=dict(Counter(p['main_target_kind'] for p in plans))
    return plans,reasons,{'projects':len(targets),'requested':requested,'planned':{k:actual.get(k,0) for k in KINDS},
        'fallbacks':sum(p['target_fallback'] for p in plans),'skipped':len(targets)-len(plans)}
