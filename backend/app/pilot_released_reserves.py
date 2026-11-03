"""Return stock freed by subdomain allocation to skipped targets in this preview."""
from app import models, auto_reglue as auto, reglue_reserves as stock
from app.domain_transfer_policy import domain_key
from app.mass_action_scope import MassActionFilter, matches, stamp_plan


def recover(db, job, result, previous, plans):
    from app.mass_reglue_launch import skip_reason
    if job.kind != 'auto_pilot_preview' or job.payload.get('launched_at'):
        return []
    cfg = auto.config(db)
    if cfg.main_target_mode != 'legacy' or job.payload.get('config_hash') != auto.digest(cfg.model_dump()):
        return []
    selected = {p['site_id'] for p in plans}
    occupied = {domain_key(p.get(key)) for p in plans
                for key in ('new_main', 'parent_domain', 'parent_alternate_domain') if p.get(key)}
    retained = {p.get('reserve_pool_id') for p in plans}
    released = {p['reserve_pool_id']: p for p in previous if p.get('reserve_pool_id')
                and p['reserve_pool_id'] not in retained and domain_key(p['new_main']) not in occupied}
    if not released:
        return []
    reserves = [db.get(models.ReglueReserveDomain, id) for id in released]
    reserves = sorted((row for row in reserves if row is not None
                       and domain_key(row.domain) == domain_key(released[row.id]['new_main'])
                       and row.domain_type == released[row.id].get('domain_type')),
                      key=lambda row: (row.created_at, row.id))
    candidates = []
    allowed = job.payload.get('allowed')
    for group in result['groups']:
        for id in group['site_ids']:
            item = result['items'].get(id, {})
            if (id in selected or id not in job.payload['site_ids'] or item.get('run_id')
                    or item.get('status') != 'skipped' or not item.get('retry_state')
                    or allowed is not None and id not in allowed):
                continue
            site = db.get(models.Site, id)
            if site is None or skip_reason(db, site) or not matches(site, MassActionFilter.model_validate(group['filter'])):
                continue
            candidates.append((site, group, item))
    candidates.sort(key=lambda row: (row[0].name, row[0].id))
    recovered = []
    missing = object()
    keys = ('mass_action_filter', 'canonical_allocation_plans', 'reglue_preview_domains')
    saved = {key: db.info.get(key, missing) for key in keys}
    try:
        db.info['canonical_allocation_plans'] = plans
        db.info['reglue_preview_domains'] = occupied
        for site, group, item in candidates:
            state = item['retry_state']
            db.info['mass_action_filter'] = group['filter']
            # Preserve the stock policy: brand-specific reserves precede general ones.
            ordered = sorted(reserves, key=lambda row: not bool(row.brand))
            for row in ordered:
                if domain_key(row.domain) in occupied:
                    continue
                try:
                    stock.require_available(db, row, site, state)
                    plan = stock.make_plan(db, cfg, site, state, row, [*plans, *recovered])
                    plan = stamp_plan(db, plan, state, site, group['filter'])
                except ValueError:
                    continue
                plan['reallocated_from_site_id'] = released[row.id]['site_id']
                group.setdefault('plans', []).append(plan)
                recovered.append(plan)
                occupied.add(domain_key(row.domain))
                result.setdefault('reserve_reallocation', []).append({
                    'site_id': site.id, 'project': site.name, 'reserve_pool_id': row.id, 'domain': row.domain,
                    'previous_site_id': released[row.id]['site_id'], 'previous_reason': item.get('reason'),
                })
                item.update(status='ready', reason=None)
                item.pop('retry_state', None)
                break
    finally:
        for key, value in saved.items():
            if value is missing:
                db.info.pop(key, None)
            else:
                db.info[key] = value
    return recovered
