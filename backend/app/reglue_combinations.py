"""Structural experiment identity, independent of random domain and path names.

Only completed runs count as tested. Draft allocation is counted separately.
The saved plan remains the source of truth; reading history never changes it.
"""
from collections import Counter
from hashlib import sha256
import json
from urllib.parse import urlsplit

from sqlalchemy import select
from app import models
from app.domain_transfer_policy import geo_key
from app.network_state import alternate_links, domain_name

VERSION = 1


def group(plan):
    from app.cross_reglue import brand_key
    return brand_key(plan.get('brand')), geo_key(plan.get('geo'))


def settings(plan):
    from app.canonical_allocation import canonical_href
    from app.domain_classification import registrable_root
    main = domain_name(plan.get('new_main') or '')
    parent = registrable_root(main) if main else None
    fake = plan.get('fake_main_path') or plan.get('new_fake_main_path')
    kind = plan.get('domain_type') or plan.get('required_domain_type') or plan.get('parent_kind') or 'unknown'
    def address(href):
        url = urlsplit((href or '').replace('{{settings.canon}}', main).replace('{{reqPath}}', fake or '/'))
        host = (url.hostname or '').lower()
        role = ('main' if host == main else 'parent' if host == parent else
                'child' if main and host.endswith('.' + main) else
                'old_main' if host == plan.get('old_main') else 'other')
        classification = (plan.get('domain_classification') or {}).get(host) or {}
        return {'host': role, 'type': classification.get('parent_type') or (kind if role in {'main', 'parent'} else ('newreg' if plan.get('x_default_use_newreg') else 'drop') if host and host == plan.get('x_default_domain') else None),
                'path': 'root' if url.path in ('', '/') else 'fake' if fake and url.path == fake else 'other',
                'query': bool(url.query), 'fragment': bool(url.fragment)}
    language = (plan.get('language') or '').lower().split('-')[0]
    geo = geo_key(plan.get('geo'))
    links = alternate_links(plan.get('alternateMarkup') or '') if plan.get('enableAlternates', True) else []
    def role(code):
        code = code.lower()
        if code == 'x-default': return code
        if code == language: return 'lang'
        if geo and code.endswith('-' + geo.lower()): return 'locale'
        if '-' not in code and not language: return 'lang'
        return 'auxiliary:' + code
    alternates = sorted([{'role': role(link['hreflang']), **address(link['href'])} for link in links],
                        key=lambda x: json.dumps(x, sort_keys=True))
    child = main.removesuffix('.' + parent) if parent and parent != main else ''
    internal = plan.get('internal_pages') or {}
    def family(value):
        if not value: return None
        from app.naming_variants import families
        try:
            for label, spellings in families(plan.get('brand'), geo.lower(), language, casino=True):
                if value.lower().strip('/') in {name for spelling in spellings for name in (spelling, spelling.replace('-', ''))}:
                    return label
        except ValueError: pass
        return 'other'
    return {'version': VERSION,
            'main': {'type': kind, 'subdomain': bool(child),
                     'origin': 'pool' if plan.get('reserve_pool_id') else 'own' if plan.get('source_site_id', plan.get('site_id')) == plan.get('site_id') else 'other',
                     'create_subdomain': bool(plan.get('create_subdomain')),
                     'name_style': ('hyphen' if '-' in child else 'joined') if child else None,
                     'casino': 'casino' in child if child else False, 'name_family': family(child)},
            'canonical': address(canonical_href(plan.get('canonicalFakeMainMarkup'), main, fake)),
            'fake': 'new' if fake and plan.get('create_fake_main_path') == fake else 'current' if fake else 'off',
            'fake_name_family': family(fake),
            'alternates': alternates,
            'redirect': bool(plan.get('redirect_old_main')),
            'headings': plan.get('title_rewrite_mode', 'minimal') if plan.get('rewrite_title_h1') else 'off',
            'short_h1': bool(plan.get('short_h1')) if plan.get('rewrite_title_h1') else False,
            'paragraphs': bool(plan.get('rewrite_paragraphs')),
            'internal_pages': {'enabled': bool(internal.get('enabled')), 'count': internal.get('count', 0) if internal.get('enabled') else 0}}


def identity(plan):
    return sha256(json.dumps(settings(plan), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class History:
    def __init__(self, db, fixed=()):
        self.pair, self.project, self.total, self.batch = Counter(), Counter(), Counter(), Counter()
        self.last = {}
        runs = db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.status == 'completed')
                          .order_by(models.AutoReglueRun.created_at, models.AutoReglueRun.id))
        for run in runs:
            plan = {**(run.plan or {}), 'site_id': run.site_id}
            if not plan.get('new_main'): continue
            key = identity(plan)
            self.total[key] += 1
            # Missing historical brand/GEO is unknown, never borrowed from today's cache.
            if all(group(plan)):
                self.pair[(group(plan), key)] += 1
                self.last[(group(plan), key)] = {'run_id': run.id, 'at': run.updated_at.isoformat()}
            self.project[(run.site_id, key)] += 1
        for plan in fixed: self.record(plan)

    def rank(self, plan):
        key = identity(plan)
        return (self.pair[(group(plan), key)], self.project[(plan['site_id'], key)],
                self.batch[(group(plan), key)], self.total[key])

    def record(self, plan):
        self.batch[(group(plan), identity(plan))] += 1

    def stamp(self, plan, *, available=1):
        key = identity(plan)
        plan.update(combination_id=key, combination_settings=settings(plan), combination_history={
            'brand_geo_completed': self.pair[(group(plan), key)],
            'project_completed': self.project[(plan['site_id'], key)],
            'planned_in_group': self.batch[(group(plan), key)],
            'last_completed': self.last.get((group(plan), key)), 'compatible_variants': available})
