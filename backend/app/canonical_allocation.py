"""Balance reviewed mass plans without changing a scheme during execution."""
from collections import Counter
from contextlib import contextmanager
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit


def canonical_href(markup, main='main.test', fake_path=None):
    class Canonical(HTMLParser):
        href = None
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag.lower() == 'link' and 'canonical' in (attrs.get('rel') or '').lower().split():
                self.href = attrs.get('href')
    parser = Canonical(); parser.feed(markup or '')
    if not parser.href: return None
    return parser.href.replace('{{settings.canon}}', main).replace('{{reqPath}}', fake_path or '/')


def mode(markup, fake_path=None):
    href = canonical_href(markup, fake_path=fake_path)
    if not href: return None
    return 'internal' if urlsplit(href).path not in ('', '/') else 'self'


def apply(db, site, plan, plans=()):
    _apply(db, site, plan, plans)
    from app.pilot_schemes import allocate_parent_x_defaults, validate_parent_x_default
    saved = db.info.get('canonical_replay_plan') or {}
    if saved:
        for key in ('x_default_parent_path', 'x_default_policy_version', 'parent_alternate_domain', 'combination_id', 'combination_settings', 'combination_history', 'planning_options', 'language', 'brand', 'domain_type'):
            if key in saved: plan[key] = saved[key]
        validate_parent_x_default(plan)
    else:
        fixed = [*db.info.get('canonical_allocation_plans', []), *plans]
        allocate_parent_x_defaults([plan], fixed=fixed)
        if plan.get('scope') == 'mass' and not db.info.get('auto_pilot_preview'):
            from app.pilot_schemes import assign
            from app.reglue_combinations import History
            if (plan.get('planning_options') or {}).get('profile_id') or plan.get('scheme_mode') == 'locale_base':
                # A manually selected template is a constraint, not a catalogue suggestion.
                plan.setdefault('brand', site.brand)
                History(db, fixed).stamp(plan)
            else:
                assign(db, [plan], fixed=fixed)


def _apply(db, site, plan, plans=()):
    saved = db.info.get('canonical_replay_plan') or {}
    for key in ('short_h1','title_rewrite_mode','rewrite_paragraphs','paragraphs_preview','paragraphs_error','without_alternates','title_h1_current','title_h1_preview','title_h1_error','fake_main_path','create_fake_main_path','new_fake_main_path','redirect_old_main','rewrite_title_h1','pilot_variation_version','scheme_variant','fake_hreflang_role','alternateMarkup','enableAlternates','canonicalFakeMainMarkup','required_page_urls'):
        if key in saved: plan[key] = saved[key]
    if saved.get('pilot_variation_version') and not saved.get('fake_main_path'):
        for key in ('fake_main_path','create_fake_main_path','new_fake_main_path'): plan.pop(key,None)
    path = plan.get('fake_main_path')
    if not path or path == '/': return
    # The catalogue is not used by every planning path. Apply the same rule to
    # a newly built single-link plan, but never change a saved/replayed scheme.
    from app.network_state import alternate_links
    links = alternate_links(plan.get('alternateMarkup') or '') if plan.get('enableAlternates', True) else []
    if not saved and plan.get('new_main') and len(links) == 1:
        href = 'https://' + plan['new_main'] + path
        plan['alternateMarkup'] = '<link rel="alternate" hreflang="' + escape(links[0]['hreflang'], quote=True) + '" href="' + escape(href, quote=True) + '" />'
        plan['canonical_mode'] = 'self'
        plan['canonicalFakeMainMarkup'] = '<link rel="canonical" href="https://{{settings.canon}}/" />'
        plan['brand'] = site.brand
        plan['required_page_urls'] = list(dict.fromkeys([*(plan.get('required_page_urls') or []), 'https://' + plan['new_main'] + '/', href]))
        from app.pilot_schemes import validate_single_alternate
        validate_single_alternate(plan)
        return
    if plan.get('scope') == 'personal': return
    forced = db.info.get('canonical_replay')
    if forced not in ('self', 'internal') and 'canonical_allocation_plans' not in db.info: return
    plan['brand'] = site.brand
    if forced in ('self', 'internal'):
        choice = forced
    else:
        from app.cross_reglue import brand_key, geo_key
        def group(p):
            return brand_key(p.get('brand')), geo_key(p.get('geo'))
        plan['brand'] = site.brand
        allocated = {p['site_id']: p for p in [*db.info['canonical_allocation_plans'], *plans] if p['site_id'] != site.id}
        total, local = Counter(), Counter()
        for p in allocated.values():
            m = p.get('canonical_mode') or mode(p.get('canonicalFakeMainMarkup'), p.get('fake_main_path'))
            if not m or not p.get('fake_main_path'): continue
            total[m] += 1
            if group(p) == (brand_key(site.brand), geo_key(site.cache_geo)): local[m] += 1
        old = mode((site.network_state or {}).get('canonicalFakeMainMarkup'), (site.network_state or {}).get('fake_main_current'))
        choice = min(('self', 'internal'), key=lambda m: (local[m], total[m], m == old))
    plan['canonical_mode'] = choice
    plan['canonicalFakeMainMarkup'] = '<link rel="canonical" href="https://{{settings.canon}}' + (path if choice == 'internal' else '/') + '" />'


@contextmanager
def replay(db, plan):
    from app.pilot_schemes import validate_single_alternate, validate_parent_x_default
    validate_single_alternate(plan or {})
    validate_parent_x_default(plan or {})
    previous = db.info.get('canonical_replay')
    previous_plan = db.info.get('canonical_replay_plan')
    db.info['canonical_replay_plan'] = plan
    db.info['canonical_replay'] = (plan or {}).get('canonical_mode')
    try: yield
    finally:
        if previous_plan is None: db.info.pop('canonical_replay_plan', None)
        else: db.info['canonical_replay_plan'] = previous_plan
        if previous is None: db.info.pop('canonical_replay', None)
        else: db.info['canonical_replay'] = previous
