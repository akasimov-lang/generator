"""Auto Pilot/list priority: selected reserve, own roots, stock, then donor."""
from collections import Counter
from app import cross_reglue as cross, reglue_reserves as stock, auto_reglue as auto
from app.mass_main_targets import target_kind, require_target
from app.mass_action_scope import stamp_plan
from app.domain_transfer_policy import domain_key


def build(db, cfg, targets, sites, states, free):
    plans, reasons = [], {}
    used = {domain_key(d) for d in db.info.get('reglue_preview_domains', ())}
    outgoing, directions = Counter(), set()
    def save(plan, target):
        plan.pop('preview_token', None); plan['preview_token'] = auto.digest(plan)
        plans.append(stamp_plan(db, plan, states[target.id], target))
        used.add(domain_key(plan['new_main']))
    ordered = sorted(targets, key=lambda s: (s.name, s.id))
    unresolved = []
    # Claim every recipient's own candidate before any donor allocation.
    for target in ordered:
        state = states[target.id]
        selected = cross.selected_reserve(state)
        blocked = cross.blocked_reserve(db, target, state)
        if selected and not blocked:
            try:
                cross.require_selected_reserve(db, target, state, selected)
                if domain_key(selected) in used: raise ValueError('Резерв уже выбран для другого проекта.')
                save(cross.reserve_plan(cfg, target, state, db=db, plans=plans), target)
            except ValueError as error: reasons[target.id] = str(error)
            continue
        found = None
        if db.info.get('pilot_mixed') and not selected:
            from app.pilot_mixed import target_order
            from app.mass_main_targets import subdomain_candidate
            from app.pilot_variations import parent_alternate
            for kind in target_order(db, plans):
                try:
                    if kind.startswith('sub_'):
                        parent, domain = subdomain_candidate(db, target, state, kind, cfg,
                            excluded_parents=used, allocation_plans=plans)
                        if domain_key(domain) in used: continue
                        plan = cross.make_plan(cfg, target, state, target, state, domain, mode='local_subdomain', db=db, plans=plans)
                        plan.update(local_target=True, parent_domain=parent, create_subdomain=domain,
                            main_target_kind=kind, required_domain_type=kind[4:], domain_type=kind[4:], requires_newreg=False)
                        parent_alternate(plan, parent, (target.cache_language or '').replace('_', '-').split('-')[0])
                        require_target(db, target, state, plan)
                    else:
                        domain = None
                        for candidate in state['domains']:
                            if domain_key(candidate) in used or target_kind(target, state, candidate) != kind: continue
                            try:
                                require_target(db, target, state, {'new_main':candidate, 'main_target_kind':kind})
                                cross.unique_membership(db, candidate, {target.id})
                            except ValueError: continue
                            domain = candidate; break
                        if not domain: continue
                        plan = cross.make_plan(cfg, target, state, target, state, domain, mode='own_unused', db=db, plans=plans)
                        plan.update(local_target=True, main_target_kind=kind, required_domain_type=kind, domain_type=kind, requires_newreg=False)
                    save(plan, target)
                    found = True
                    break
                except ValueError:
                    continue
            if found: continue
        if not selected:
            for kind in ('newreg', 'drop'):
                for domain in state['domains']:
                    if domain_key(domain) in used or target_kind(target, state, domain) != kind: continue
                    try:
                        require_target(db, target, state, {'new_main':domain, 'main_target_kind':kind})
                        cross.unique_membership(db, domain, {target.id})
                    except ValueError: continue
                    found = (domain, kind); break
                if found: break
        if found:
            domain, kind = found
            try:
                plan = cross.make_plan(cfg, target, state, target, state, domain, mode='own_unused', db=db, plans=plans)
                plan.update(local_target=True, main_target_kind=kind, required_domain_type=kind, requires_newreg=False)
                save(plan, target)
            except ValueError as error: reasons[target.id] = 'Не удалось подготовить схему: ' + str(error)
        else: unresolved.append(target)
    for target in unresolved:
        state = states[target.id]
        blocked = cross.blocked_reserve(db, target, state)
        # A banned selected reserve follows the explicit cross-network fallback rule.
        entry = None if blocked else stock.candidate(db, target, state, ['drop'], used)
        if entry:
            try: save(stock.make_plan(db, cfg, target, state, entry, plans), target)
            except ValueError as error: reasons[target.id] = 'Не удалось подготовить схему: ' + str(error)
            continue
        candidates = []
        for source in sites.values():
            if source.id == target.id or outgoing[source.id] >= 10 or (target.id, source.id) in directions: continue
            if not blocked and len(states[source.id]['domains']) - outgoing[source.id] <= len(state['domains']): continue
            try: cross.require_pair(source, target)
            except ValueError: continue
            for domain in free.get(source.id, []):
                if domain_key(domain) in used or target_kind(source, states[source.id], domain) != 'newreg': continue
                try: stock.require_unused(target, state, domain)
                except ValueError: continue
                candidates.append((source, domain)); break
        candidates.sort(key=lambda x: (-len(states[x[0].id]['domains']) + outgoing[x[0].id], x[0].name, x[1]))
        if candidates:
            source, domain = candidates[0]
            try:
                plan = cross.make_plan(cfg, target, state, source, states[source.id], domain,
                    mode='banned_reserve_fallback' if blocked else 'redistribute', db=db, plans=plans)
                save(plan, target); outgoing[source.id] += 1; directions.add((source.id,target.id))
            except ValueError as error: reasons[target.id] = 'Не удалось подготовить схему: ' + str(error)
        else:
            if blocked:
                entry=stock.candidate(db,target,state,['drop'],used)
                if entry:
                    try:save(stock.make_plan(db,cfg,target,state,entry,plans),target)
                    except ValueError as error:reasons[target.id]='Не удалось подготовить схему: '+str(error)
                    continue
            from app.mass_main_targets import subdomain_candidate
            from app.pilot_variations import parent_alternate
            from app.network_stock_warning import mark
            used_main = {domain_key(d) for d in [*(target.main_domain_history or []), state['canon'], state.get('prev')] if d}
            fallback = None
            for kind in ('newreg', 'drop'):
                try:
                    parent, child = subdomain_candidate(db, target, state, 'sub_' + kind, cfg, prefer_geo=True, excluded_parents=used_main | used, allocation_plans=plans)
                    if domain_key(child) in used:
                        continue
                    fallback = cross.make_plan(cfg, target, state, target, state, child, mode='local_subdomain', db=db, plans=plans)
                    fallback.update(local_target=True, parent_domain=parent, create_subdomain=child,
                        main_target_kind='sub_' + kind, required_domain_type=kind, domain_type=kind,
                        requires_newreg=False, emergency_subdomain=True)
                    parent_alternate(fallback, parent, (target.cache_language or '').replace('_', '-').split('-')[0])
                    require_target(db, target, state, fallback)
                    break
                except ValueError:
                    fallback = None
            if fallback:
                save(fallback, target)
                mark(db, target, state)
                continue
            reasons[target.id] = ('Резерв в БАН; нет разрешённого новорега другой сетки или доступного дропа в базе резервов.' if blocked else
                'Нет неиспользованных новорегов и дропов своей сетки, доступного дропа в базе резервов и разрешённого новорега другой сетки того же бренда и GEO.' + (' Дропы из базы исключены для AZ.' if cross.geo_key(target.cache_geo) == 'AZ' else ''))
    return plans, reasons
