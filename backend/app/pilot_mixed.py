"""A per-draft distribution preset; it never changes global automation settings."""
from collections import Counter
from typing import Literal

PlanningMode = Literal['percentages', 'mixed']
# Only network settings belong to this preset. Content has independent controls.
MIXED_PERCENTAGES = dict(subdomains=50, without_alternates=50, redirects=50)


def parameters(db, percentages=None, title_rewrite_mode='minimal', planning_mode='percentages'):
    from app import auto_reglue as auto
    from app.pilot_variations import PilotPercentages, title_mode
    if planning_mode not in ('percentages', 'mixed'):
        raise ValueError('Выберите допустимый режим планирования.')
    shares = PilotPercentages.model_validate(percentages or {'title_h1': auto.config(db).title_h1_rewrite_percent}).model_dump()
    heading = title_mode(title_rewrite_mode)
    if planning_mode == 'mixed':
        shares = {**shares, **MIXED_PERCENTAGES}
    return dict(percentages=shares, title_rewrite_mode=heading, planning_mode=planning_mode)


def target_order(db, plans):
    """Balance the four available Main types across groups, without changing reserves."""
    from app.mass_main_targets import KINDS
    from app.pilot_schemes import parent_domain
    counts = Counter()
    allocated = {p['site_id']: p for p in [*db.info.get('canonical_allocation_plans', []), *plans]}
    for plan in allocated.values():
        kind = plan.get('main_target_kind')
        if not kind:
            kind = plan.get('domain_type') or plan.get('required_domain_type')
            if kind and parent_domain(plan): kind = 'sub_' + kind
        counts[kind] += 1
    return sorted(KINDS, key=lambda kind: (counts[kind], KINDS.index(kind)))


def manual_allowed(db, run):
    from app import models
    from app.mass_reglue_launch import manual_pilot_allowed
    job_id = run.plan.get('list_launch_id')
    job = db.get(models.BackgroundJob, job_id) if job_id else None
    return bool(job and job.payload.get('planning_mode') == 'mixed'
                and run.plan.get('planning_mode') == 'mixed' and manual_pilot_allowed(db, run.site_id, run))
