"""Exclude this Moscow calendar week's completed reglues, including stale drafts."""
from copy import deepcopy
from types import SimpleNamespace
from sqlalchemy import select
from app import models
from app.reglue_history import weekly_reason


def exclusions(db, plans):
    reasons = {}
    ids = {id for p in plans for id in (p['site_id'], p.get('source_site_id', p['site_id']))}
    sites = {row.id: SimpleNamespace(id=row.id, name=row.name, last_reglue_at=row.last_reglue_at)
             for row in db.execute(select(models.Site.id, models.Site.name, models.Site.last_reglue_at).where(models.Site.id.in_(ids)))} if ids else {}
    for plan in plans:
        for site_id in dict.fromkeys((plan['site_id'], plan.get('source_site_id', plan['site_id']))):
            site = sites.get(site_id)
            if site and (reason := weekly_reason(site)):
                reasons[plan['site_id']] = reason if site_id == plan['site_id'] else f'Сетка-донор {site.name}: {reason}'
                break
    return reasons


def exclude(db, result, *, job=None):
    from app.pilot_observed_reglues import retire
    retired = retire(db, job, result) if job is not None else False
    plans = [p for g in result['groups'] for p in g.get('plans', [])
             if not result['items'][p['site_id']].get('run_id')]
    reasons = exclusions(db, plans)
    if not reasons: return retired
    from app.cross_reglue_batch import key
    for group in result['groups']:
        old = group.get('plans', [])
        group['plans'] = [p for p in old if p['site_id'] not in reasons]
        if len(group['plans']) == len(old): continue
        if not group['plans']: group['status'] = 'done'
        ledger = db.get(models.AutoReglueConfig, key(group['batch_id'])) if group.get('batch_id') else None
        if ledger:
            ledger.value = {**ledger.value, 'plans': deepcopy(group['plans'])}
    for site_id, reason in reasons.items():
        result['items'][site_id].update(status='skipped', reason=reason)
    if result.get('variation_summary'):
        from app.pilot_variations import update_summary
        update_summary(result)
    return True
