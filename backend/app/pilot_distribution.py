"""Read the actual independent settings of a saved plan, without reallocating it."""
from app.domain_classification import registrable_root
from app.network_state import domain_name


def summarize(plans):
    from collections import Counter
    from app.pilot_schemes import parent_domain
    headings, targets = Counter(), Counter()
    counts = dict(subdomains=0, without_alternates=0, redirects=0, title_h1=0, paragraphs=0, internal_pages=0)
    baseline = emergency = 0
    for plan in plans:
        if plan.get('rewrite_title_h1'): headings[plan.get('title_rewrite_mode', 'minimal')] += 1
        kind = plan.get('main_target_kind')
        if not kind:
            kind = plan.get('domain_type') or plan.get('required_domain_type') or 'other'
            if kind in ('newreg', 'drop') and parent_domain(plan): kind = 'sub_' + kind
        targets[kind] += 1
        alternates = plan.get('alternates_after') or {}
        main = domain_name(plan.get('new_main') or '').removeprefix('www.')
        root = registrable_root(main) if main else None
        flags = {
            'subdomains': bool(plan.get('create_subdomain') or plan.get('parent_domain') or
                               str(plan.get('main_target_kind', '')).startswith('sub_') or (root and root != main)),
            'without_alternates': not bool(plan.get('enableAlternates', alternates.get('enabled', True)) and
                                           plan.get('alternateMarkup', alternates.get('markup', ''))),
            'redirects': bool(plan.get('redirect_old_main')),
            'title_h1': bool(plan.get('rewrite_title_h1')),
            'paragraphs': bool(plan.get('rewrite_paragraphs')),
            'internal_pages': bool((plan.get('internal_pages') or {}).get('enabled')),
        }
        for key, enabled in flags.items():
            counts[key] += int(enabled)
        baseline += int(not any(flags.values()))
        emergency += int(bool(plan.get('emergency_subdomain')))
    return {'total': len(plans), 'counts': counts, 'baseline': baseline, 'emergency_subdomains': emergency,
            'heading_modes':dict(headings), 'target_kinds':dict(targets)}
