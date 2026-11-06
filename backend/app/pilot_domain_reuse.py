"""Explicit brand/GEO plans may reuse a former Main after fourteen full days."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app import models
from app.domain_transfer_policy import domain_key, geo_key, banned_domains
from app.reglue_history import utc

DAYS = 14


def release_evidence(db, domain, now=None):
    """Use observed departures, never membership dates or editable history flags."""
    key = domain_key(domain); now = utc(now) or datetime.now(timezone.utc)
    sites = db.execute(select(models.Site.id, models.Site.cache_canon, models.Site.main_domain_history,
                             models.Site.network_snapshot_history, models.Site.network_state)).all()
    events = {}; known = set()
    def event(site_id, before, after, at):
        at = utc(at)
        if not at or at > now: return
        old, new = domain_key(before), domain_key(after)
        if key in {old,new}:
            known.add(site_id)
            events.setdefault(site_id, []).append((at, new == key))
    from app.domain_transfer_policy import main_pin_owners
    known.update(main_pin_owners(db, [domain]).get(key, set()))
    for site in sites:
        if domain_key(site.cache_canon) == key:
            raise ValueError('Домен сейчас является Main. Повторное использование недоступно.')
        if key in {domain_key(d) for d in site.main_domain_history or []}: known.add(site.id)
        previous = None
        for snap in sorted(site.network_snapshot_history or [], key=lambda s:str(s.get('observed_at',''))):
            canon = snap.get('canon')
            if canon:
                event(site.id, previous, canon, snap.get('observed_at')); previous=canon
        for row in (site.network_state or {}).get('cache_change_history', []):
            if row.get('kind') == 'reglue': event(site.id,row.get('old_main'),row.get('new_main'),row.get('at'))
    for op in db.execute(select(models.NetworkOperation.site_id, models.NetworkOperation.request_payload,
                                models.NetworkOperation.updated_at).where(
            models.NetworkOperation.action=='reglue', models.NetworkOperation.status=='confirmed')):
        p=op.request_payload or {}
        event(op.site_id,p.get('source_domain'),p.get('reserve'),p.get('confirmed_at') or op.updated_at)
    departures=[]
    for owner in known:
        history=sorted(events.get(owner, []), key=lambda e:(e[0],e[1]))
        if not history or history[-1][1]:
            raise ValueError('Не подтверждена дата, когда домен перестал быть Main.')
        departures.append(history[-1][0])
    if not departures: raise ValueError('Для домена нет подтверждённой истории смены Main.')
    ended=max(departures)
    if now < ended + timedelta(days=DAYS):
        raise ValueError('Бывший Main доступен через 14 дней после смены: ' + (ended+timedelta(days=DAYS)).isoformat())
    return {'domain':key,'ended_at':ended.isoformat(),'days':DAYS,'owners':sorted(known)}


def allows(site, state, domain, plan):
    """Pure guard for existing call sites; execution also rechecks DB evidence."""
    p=plan or {}; evidence=p.get('former_main') or {}; ended=utc(evidence.get('ended_at'))
    from app.cross_reglue import brand_key
    return bool(p.get('pilot_reuse_job_id') and not p.get('reserve_pool_id') and not p.get('create_subdomain')
        and evidence.get('days')==DAYS and ended and datetime.now(timezone.utc)>=ended+timedelta(days=DAYS)
        and domain_key(domain)==evidence.get('domain')==domain_key(p.get('new_main'))
        and site.id in {p.get('site_id'),p.get('source_site_id')}
        and geo_key(site.cache_geo)==p.get('geo') and brand_key(site.brand)==brand_key(p.get('brand'))
        and domain_key(state.get('canon'))!=domain_key(domain))


def validate(db, plan):
    """Only a server-prepared saved alternative may relax historical Main pins."""
    if not plan.get('former_main'): return False
    job=db.get(models.BackgroundJob,plan.get('pilot_reuse_job_id'))
    if not job or job.kind not in {'pilot_row_replan','auto_pilot_preview','mass_reglue_list'}:
        raise ValueError('Не найдено разрешение на повторное использование бывшего Main.')
    target=db.get(models.Site,plan['site_id']); source=db.get(models.Site,plan['source_site_id'])
    from app.cross_reglue import require_pair
    if source.id!=target.id: require_pair(source,target)
    members=[job.payload.get('site_id')] if job.kind=='pilot_row_replan' else job.payload.get('site_ids',[])
    if target.id not in members or not allows(source, {'canon':source.cache_canon},plan['new_main'],plan):
        raise ValueError('Условия повторного использования Main изменились.')
    fresh=release_evidence(db,plan['new_main'])
    if fresh!=plan['former_main']: raise ValueError('История Main изменилась после подготовки плана.')
    if banned_domains(db,target,[plan['new_main']])[plan['new_main']]: raise ValueError('Домен отмечен БАН.')
    return True


def candidate(db, cfg, target, states, sites, used, plans=(), *, unused_first=True):
    """Own unused drop/newreg, peer unused newreg, then a retired Main; no stock."""
    from app import cross_reglue as cross
    from app.mass_main_targets import target_kind, require_target
    from app.domain_transfer_policy import require_transfer_allowed
    from app.mass_action_scope import stamp_plan
    target_state=states[target.id]
    errors=[]
    options=[]
    for source in sorted(sites.values(),key=lambda s:(s.id!=target.id,s.name)):
        if source.id!=target.id:
            outgoing=[p for p in plans if p['source_site_id']==source.id and p['site_id']!=source.id]
            if len(outgoing)>=10 or any(p['source_site_id']==target.id and p['site_id']==source.id for p in plans):continue
            try: cross.require_pair(source,target)
            except ValueError: continue
        for domain in states[source.id]['domains']:
            if domain_key(domain) in used: continue
            kind=target_kind(source,states[source.id],domain)
            if not kind: continue
            used_before=domain_key(domain) in {domain_key(d) for d in [*(source.main_domain_history or []),states[source.id].get('prev'),states[source.id].get('canon')] if d}
            if not used_before:
                if not unused_first: continue
                if source.id!=target.id and kind!='newreg': continue
            rank=(3 if used_before else 2 if source.id!=target.id else 0 if kind.removeprefix('sub_')=='drop' else 1,
                  source.id!=target.id,kind.startswith('sub_'),domain)
            options.append((rank,source,domain,kind,used_before))
    for _,source,domain,kind,used_before in sorted(options,key=lambda item:item[0]):
        state=states[source.id]
        try:
            plan=cross.make_plan(cfg,target,target_state,source,state,domain,mode='brand_geo_alternative',db=db,plans=plans)
            plan.update(local_target=source.id==target.id,main_target_kind=kind,required_domain_type=kind.removeprefix('sub_'),domain_type=kind.removeprefix('sub_'),requires_newreg=False)
            if db.info.get('pilot_job_id'):plan['pilot_brand_geo_job_id']=db.info['pilot_job_id']
            if db.info.get('pilot_alternative_id'):
                plan['pilot_alternative_id']=db.info['pilot_alternative_id']
            if used_before:
                plan.update(former_main=release_evidence(db,domain),pilot_reuse_job_id=db.info.get('pilot_alternative_id') or db.info.get('pilot_job_id'))
                validate(db,plan)
            require_target(db,source,state,plan)
            if source.id!=target.id:
                cross.require_import_for_plan(db,target,target_state,plan)
                cross.transferable(source,state,domain,plan=plan)
                require_transfer_allowed(db,source,domain,plan=plan)
            cross.unique_membership(db,domain,{source.id})
            return stamp_plan(db,plan,target_state,target)
        except ValueError as error:errors.append(str(error))
    detail='; '.join(dict.fromkeys(errors))[:1200]
    raise ValueError('Нет подходящего домена без базы резервов: неиспользованный дроп/новорег своей сетки, новорег другой сетки того же бренда и GEO или бывший Main после 14 дней.'+(' '+detail if detail else ''))
