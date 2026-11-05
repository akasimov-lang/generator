"""Project membership behind Auto Pilot domain summary filters."""

def domain_projects(plans, items, *, confirmed=False):
    eligible = {row['site_id'] for row in items if not confirmed or row.get('performed_at')}
    groups = {key: [] for key in ('reserve_drops', 'newregs', 'drops', 'other')}
    for site_id, plan in plans.items():
        if site_id not in eligible:
            continue
        kind = plan.get('domain_type') or plan.get('required_domain_type') or plan.get('main_target_kind')
        if plan.get('reserve_pool_id'):
            groups['reserve_drops'].append(site_id)
            kind = 'drop'
        key = 'newregs' if kind in ('newreg', 'sub_newreg', 'newreg_subdomain') else 'drops' if kind in ('drop', 'sub_drop', 'drop_subdomain') else 'other'
        groups[key].append(site_id)
    return groups
