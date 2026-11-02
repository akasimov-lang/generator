"""One explicit, scoped click moves exactly two free NewReg roots, with durable rotation."""
from sqlalchemy import select

from app import models, auto_reglue as auto, project_network as network
from app import domain_redistribution as move, cross_reglue as cross, mass_action_reports
from app.mass_action_scope import MassActionFilter, constrain, stamp_plan
from app.site_statistics import network_domain_counts


def intent_key(run_id):
    return 'move-plus2:' + str(run_id)


def size_bands(sites, states):
    expanded = any(len(states[s.id]['domains']) >= 20 for s in sites)
    def tier(site):
        size = len(states[site.id]['domains'])
        return (2 if size >= 20 else 1 if size >= 10 else 0) if expanded else (2 if size > 10 else 1 if size > 5 else 0)
    return {s.id: tier(s) for s in sites}, expanded


def choose(sites, states, free, rotation, count=2, counts_override=None, target_ids=None):
    counts = counts_override or {s.id: network_domain_counts(s)['newreg'] for s in sites}
    bands, expanded = size_bands(sites, states)
    pairs = []
    for target in sites:
        if cross.selected_reserve(states[target.id]):continue
        if target_ids is not None and target.id not in target_ids:continue
        for source in sites:
            try:
                cross.require_pair(source, target)
            except ValueError:
                continue
            newreg_count = sum(d['domain_type']=='newreg' for d in free.get(source.id, [])[:count])
            if (len(free.get(source.id, [])) >= count
                    and len(states[source.id]['domains']) - len(states[target.id]['domains']) > count
                    and (newreg_count == 0 or counts[source.id] - counts[target.id] >= newreg_count)):
                pairs.append((source, target))
    if not pairs:
        raise ValueError(f'Нет пары сеток с {count} доступными новорегами для равномерного распределения. Проверьте редиректы, БАН, имена проектов и историю Main.')
    pure = [(s,t) for s,t in pairs if all(d['domain_type']=='newreg' for d in free[s.id][:count])]
    if pure:pairs=pure
    unserved_pairs = [(s,t) for s,t in pairs if s.id not in rotation.get('served_donors', [])]
    if unserved_pairs:pairs=unserved_pairs
    smallest = min(bands[t.id] for _, t in pairs)
    pairs = [(s, t) for s, t in pairs if bands[t.id] == smallest]
    largest = max(bands[s.id] for s, _ in pairs)
    pairs = [(s, t) for s, t in pairs if bands[s.id] == largest]
    # First serve the smallest NewReg population; a full donor round survives reloads.
    targets = list({t.id: t for _, t in pairs}.values())
    received = set(rotation.get('served_recipients', []))
    unserved = [s for s in targets if s.id not in received]
    if not unserved:
        received = set()
        unserved = targets
    target = min(unserved, key=lambda s: (
        counts[s.id], len(states[s.id]['domains']), rotation.get('received', {}).get(s.id, 0), s.name, s.id))
    donors = [s for s, t in pairs if t.id == target.id]
    served = set(rotation.get('served_donors', []))
    waiting = [s for s in donors if s.id not in served]
    if not waiting:
        served = set()
        waiting = donors
    source = min(waiting, key=lambda s: (-len(states[s.id]['domains']), -counts[s.id], s.name, s.id))
    return source, target, served, received


def validate_intent(db, run):
    row = db.get(models.AutoReglueConfig, intent_key(run.id))
    if not row or row.value.get('run_id') != run.id:
        raise ValueError('Move +2 не имеет сохранённого разрешения запуска.')
    original = row.value['plan']
    if any(run.plan.get(k) != value for k, value in original.items()):
        raise ValueError('План Move +2 изменился после сохранения.')
    if run.plan.get('move_count') not in {1, 2} or len(run.plan['domains']) != run.plan['move_count'] or any(d['domain_type'] not in {'newreg','drop'} for d in run.plan['domains']) or sum(d['domain_type']=='drop' for d in run.plan['domains'])>1:
        raise ValueError('Число новорегов не соответствует сохранённому запуску Move.')


def prepare(db, request_id, filters, site_ids, actor, allowed=None, count=2, *, prefetch=None):
    if count not in {1, 2}:
        raise ValueError('Move переносит один или два новорега за нажатие.')
    filters = MassActionFilter.model_validate(filters)
    ids = set(site_ids)
    scoped = constrain(db, filters, allowed)
    if not ids.issubset(scoped) or len(ids) < 2:
        raise ValueError('Выберите не менее двух проектов внутри текущего фильтра бренд + GEO.')
    scope_key = 'move-plus2-rotation:' + auto.digest([filters.brand.casefold(), filters.geo, filters.site_type])[:40]
    with network.network_lock(db, scope_key):
        existing = db.get(models.AutoReglueRun, str(request_id))
        if existing:
            intent = db.get(models.AutoReglueConfig, intent_key(existing.id))
            if (not intent or intent.value.get('site_ids') != sorted(ids)
                    or existing.plan.get('mass_filter') != filters.model_dump() or existing.plan.get('move_requested_count',existing.plan.get('move_count')) != count):
                raise ValueError('Идентификатор Move +2 уже использован с другой выборкой.')
            validate_intent(db, existing)
            return existing, False
        sites = db.scalars(select(models.Site).where(models.Site.id.in_(ids))).all()
        def busy(site):
            return any(r.site_id==site.id or r.plan.get('source_site_id')==site.id for r in auto.active_participants(db)
                if not prefetch or r.plan.get('batch_id')!=prefetch['id'])
        if any(busy(s) for s in sites):
            raise network.NetworkConflict('Дождитесь завершения текущего переноса в этой выборке.')
        pending = set(db.scalars(select(models.NetworkOperation.site_id).where(
            models.NetworkOperation.site_id.in_(ids), models.NetworkOperation.status.in_(['pending', 'unknown']))))
        states, free, ready = {}, {}, []
        from app.move_batch import blocked_domains
        blocked=blocked_domains(db,filters.brand,filters.geo)
        for site in sites:
            if site.id in pending or auto.config(db, site.id).scope == 'personal':
                continue
            state = network.read_network(db, site)
            states[site.id] = state
            free[site.id] = []
            for domain in state['domains']:
                if (site.domain_types or {}).get(domain) not in {'newreg','drop'} or domain in blocked:
                    continue
                try:
                    move.eligible(db, site, state, domain)
                except ValueError:
                    continue
                free[site.id].append({'domain': domain, 'domain_type': site.domain_types[domain]})
            newregs=[d for d in free[site.id] if d['domain_type']=='newreg']
            drops=[d for d in free[site.id] if d['domain_type']=='drop']
            free[site.id]=newregs+drops[:0 if prefetch and prefetch.get('drop_used') else 1]
            ready.append(site)
        rotation_row = db.get(models.AutoReglueConfig, scope_key)
        rotation = rotation_row.value if rotation_row else {}
        import copy
        projected=copy.deepcopy(states)
        projected_counts={s.id:network_domain_counts(s)['newreg'] for s in ready}
        if prefetch:
            bands,_=size_bands(ready,states)
            for site in ready:
                if bands[site.id]<1:free[site.id]=[]
            for peer in prefetch.get('runs',[]):
                a,b=peer.plan['source_site_id'],peer.site_id
                for d in peer.plan['domains']:
                    if a in projected and d['domain'] in projected[a]['domains']:
                        projected[a]['domains'].remove(d['domain']);projected_counts[a]-=int(d['domain_type']=='newreg')
                    if b in projected and d['domain'] not in projected[b]['domains']:
                        projected[b]['domains'].append(d['domain']);projected_counts[b]+=int(d['domain_type']=='newreg')
                if a in free:
                    free[a]=[] if prefetch.get('unique_donors',True) else [d for d in free[a] if d['domain'] not in {v['domain'] for v in peer.plan['domains']}]
        target_ids=None
        if prefetch and prefetch.get('unique_recipients'):
            smallest=min(bands.values())
            target_ids={s.id for s in ready if bands[s.id]==smallest}-{r.site_id for r in prefetch.get('runs',[])}
            donors={r.plan['source_site_id'] for r in prefetch.get('runs',[])}
            if len(donors)>=5:
                for sid in free:
                    if sid not in donors:free[sid]=[]
        actual_count=count
        try:source,target,served,received=choose(ready,projected,free,rotation,count,projected_counts,target_ids)
        except ValueError:
            if count!=2:raise
            actual_count=1
            source,target,served,received=choose(ready,projected,free,rotation,1,projected_counts,target_ids)
        domains = free[source.id][:actual_count]
        # Target GEO bans also apply before removing anything from the donor.
        for item in domains:
            from app.domain_transfer_policy import require_transfer_allowed
            require_transfer_allowed(db, target, item['domain'])
        plan = stamp_plan(db, move.make_plan(db, source, target, states[source.id], states[target.id], domains), states[target.id], target)
        plan = {**plan, 'manual_action': 'move_plus2', 'move_count': actual_count, 'move_requested_count':count}
        if prefetch:plan.update(batch_id=prefetch['id'],prefetch_index=prefetch.get('index',len(prefetch.get('runs',[]))),prefetch=True)
        bands, expanded = size_bands(ready, states)
        plan.update(size_scale='20/10' if expanded else '10/5',
                    source_size_class=['small', 'medium', 'large'][bands[source.id]],
                    target_size_class=['small', 'medium', 'large'][bands[target.id]])
        plan['preview_token'] = auto.digest({k: v for k, v in plan.items() if k != 'preview_token'})
        with cross.participant_locks(db, target.id, plan):
            if any(busy(s) for s in (source, target)):
                raise network.NetworkConflict('Одна из сеток уже участвует в переносе.')
            run = models.AutoReglueRun(id=str(request_id), site_id=target.id, initiator=actor,
                                      status='queued', phase='prepared', plan=plan)
            db.add(run)
            db.add(models.AutoReglueConfig(key=intent_key(run.id), value={
                'run_id': run.id, 'site_ids': sorted(ids), 'actor': actor, 'plan': plan}))
            turn = rotation.get('turn', 0) + 1
            value = {'turn': turn, 'served_donors': sorted(served | {source.id}),
                     'served_recipients': sorted(received | {target.id}),
                     'received': {**rotation.get('received', {}), target.id: turn}, 'last_run_id': run.id}
            if rotation_row:
                rotation_row.value = value
            else:
                db.add(models.AutoReglueConfig(key=scope_key, value=value))
            db.flush()
            mass_action_reports.save(db, run.id, filters.model_dump(), [{'site_id': target.id, 'run_id': run.id}], actor)
            return run, True
