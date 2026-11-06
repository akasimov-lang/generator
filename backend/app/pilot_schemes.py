"""Explicit scheme catalogue; incompatible combinations never reach execution."""
from collections import Counter
from copy import deepcopy
from html import escape
from sqlalchemy import select
from app import models
from app.canonical_allocation import canonical_href, mode
from app.domain_transfer_policy import geo_key
from app.cross_reglue import brand_key
from app.network_state import alternate_links


def parent_domain(plan):
    from app.domain_classification import registrable_root
    from app.network_state import domain_name
    main = domain_name(plan.get('new_main') or '')
    root = registrable_root(main) if main else None
    if not root or root == main: return None
    explicit = plan.get('parent_domain') or plan.get('parent_alternate_domain')
    if explicit and domain_name(explicit).removeprefix('www.') != root:
        raise ValueError('Родитель поддомена не совпадает с корневым доменом нового Main.')
    return root


def apply_parent_x_default(plan, *, use_internal=False):
    """Change only x-default for a new plan, never a reviewed execution snapshot."""
    parent = parent_domain(plan)
    if not parent or not plan.get('enableAlternates', True): return
    from app.fake_main import normalize_fake_path
    path = normalize_fake_path(plan['fake_main_path']) if use_internal and plan.get('fake_main_path') else '/'
    links = [link for link in alternate_links(plan.get('alternateMarkup') or '') if link['hreflang'].lower() != 'x-default']
    links.append({'hreflang': 'x-default', 'href': 'https://' + parent + path})
    plan['alternateMarkup'] = '\n'.join('<link rel="alternate" hreflang="' + escape(link['hreflang'], quote=True)
        + '" href="' + escape(link['href'], quote=True) + '" />' for link in links)
    plan.update(parent_alternate_domain=parent, x_default_parent_path=path, x_default_policy_version=1)
    required = plan.get('required_page_urls') or []
    plan['required_page_urls'] = list(dict.fromkeys([*required, 'https://' + parent + path]))


def allocate_parent_x_defaults(plans, *, fixed=()):
    """An even split across eligible projects; resume uses the persisted choice."""
    from hashlib import sha256
    selected_ids = {p.get('site_id') for p in plans}
    fixed = {p.get('site_id'): p for p in fixed if p.get('site_id') not in selected_ids}
    counts = Counter()
    for plan in fixed.values():
        if parent_domain(plan) and plan.get('enableAlternates', True) and plan.get('fake_main_path'):
            counts[plan.get('x_default_parent_path', '/') != '/'] += 1
    for plan in sorted(plans, key=lambda p: sha256(str(p.get('site_id', '')).encode()).hexdigest()):
        if not parent_domain(plan) or not plan.get('enableAlternates', True): continue
        eligible = bool(plan.get('fake_main_path') and plan['fake_main_path'] != '/')
        internal = eligible and counts[True] <= counts[False]
        apply_parent_x_default(plan, use_internal=internal)
        if eligible: counts[internal] += 1


def validate_parent_x_default(plan):
    if not plan.get('x_default_policy_version') or not plan.get('enableAlternates', True): return
    parent = parent_domain(plan)
    if not parent: return
    path = plan.get('x_default_parent_path')
    if path not in ('/', plan.get('fake_main_path')):
        raise ValueError('Путь x-default изменился после подготовки плана.')
    links = [link for link in alternate_links(plan.get('alternateMarkup') or '') if link['hreflang'].lower() == 'x-default']
    if len(links) != 1 or links[0]['href'] != 'https://' + parent + path:
        raise ValueError('x-default должен вести на сохранённый адрес родительского домена. Обновите план.')

# Single-role arrangements use the new internal page. An internal canonical is
# compatible only when adding the parent x-default produces a second actual link.
ALTERNATES = [((),None), (('lang',),'lang'), (('locale',),'locale'),
    (('lang','locale'),'lang'), (('lang','locale'),'locale'),
    (('lang','locale','x-default'),'lang'), (('lang','locale','x-default'),'locale'),
    (('lang','locale','x-default'),'x-default'),
    (('lang','x-default'),'lang'), (('lang','x-default'),'x-default'),
    (('locale','x-default'),'locale'), (('locale','x-default'),'x-default')]
CATALOGUE = [{'id':f'{canonical}-{index}', 'canonical':canonical,'links':links,'fake_on':fake}
             for canonical in ('self','internal') for index,(links,fake) in enumerate(ALTERNATES)]


def validate_single_alternate(plan):
    """Reject an incompatible reviewed plan without silently rewriting it."""
    path, main = plan.get('fake_main_path'), plan.get('new_main')
    if not path or not main or not plan.get('enableAlternates', True): return
    links = alternate_links(plan.get('alternateMarkup') or '')
    if len(links) != 1: return
    href = links[0]['href'].replace('{{settings.canon}}', main).replace('{{reqPath}}', path)
    old_path = plan.get('old_fake_main_path') or ((plan.get('target_guard') or {}).get('fake_main_settings') or {}).get('currentFakeMain')
    if (path == '/' or plan.get('create_fake_main_path') != path or path == old_path
            or href != 'https://' + main + path
            or plan.get('canonical_mode') not in (None, 'self')
            or canonical_href(plan.get('canonicalFakeMainMarkup'), main, path) not in ('https://' + main, 'https://' + main + '/')):
        raise ValueError('Для схемы с одним альтернейтом нужна ссылка на новый внутряк, а canonical — на корень нового Main. Обновите план.')


def strategy(plan):
    kind=plan.get('domain_type') or plan.get('required_domain_type') or 'newreg'
    if plan.get('parent_domain') or plan.get('create_subdomain'):return 'sub_'+kind
    if plan.get('reserve_pool_id'):return 'pool_drop'
    return ('own_' if plan.get('source_site_id',plan['site_id'])==plan['site_id'] else 'other_')+kind


def assign(db,plans, *, fixed=(), exclude=None):
    from app.reglue_combinations import History, identity
    selected_ids = {p['site_id'] for p in plans}
    fixed = list({p['site_id']:p for p in fixed if p['site_id'] not in selected_ids}.values())
    combinations = History(db, fixed)
    # Allocate parent paths before comparing actual combinations, keeping the existing split.
    allocate_parent_x_defaults(plans, fixed=fixed)
    history=list(db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.status=='completed').order_by(models.AutoReglueRun.created_at, models.AutoReglueRun.id)))
    counts,local,personal=Counter(),Counter(),Counter()
    fake_counts, fake_global, last_fake = Counter(), Counter(), {}
    def group(p):return brand_key(p.get('brand')),geo_key(p.get('geo'))
    def record(p):
        if v:=p.get('scheme_variant'):
            counts[v]+=1;local[(group(p),v)]+=1;personal[(p['site_id'],v)]+=1
            role=p.get('fake_hreflang_role')
            if role:
                fake_counts[(group(p),role)]+=1;fake_global[role]+=1;last_fake[group(p)]=role
    for run in history:record({**run.plan,'site_id':run.site_id})
    for p in fixed:record(p)
    for plan in plans:
        site=db.get(models.Site,plan['site_id'])
        if site:
            plan.update(brand=site.brand, geo=geo_key(site.cache_geo))
        if not plan.get('fake_main_path') or plan.get('scheme_mode')=='clean' or (plan.get('planning_options') or {}).get('profile_id'):
            combinations.stamp(plan); combinations.record(plan)
            continue
        site=db.get(models.Site,plan['site_id'])
        lang=(site.cache_language or plan.get('language') or '').replace('_','-').split('-')[0].lower()
        geo=geo_key(site.cache_geo)
        if not lang or not geo:continue
        plan.update(brand=site.brand, geo=geo, language=lang)
        if not plan.get('domain_type'):
            root = parent_domain(plan) or plan['new_main']
            plan['domain_type'] = (site.domain_types or {}).get(root) or plan.get('parent_kind')
        parent = parent_domain(plan)
        canonical=plan.get('canonical_mode') or mode(plan.get('canonicalFakeMainMarkup'),plan['fake_main_path'])
        candidates=[v for v in CATALOGUE if v['canonical']==canonical and v['links'] and v['fake_on']
                    and (len(v['links']) > 1 or canonical == 'self' or parent)
                    and not (parent and v['fake_on']=='x-default')]
        # No-alternate + internal canonical is not supported by Webdev. Parent needs a link.
        if plan.get('without_alternates'):
            if canonical!='self' or plan.get('parent_domain'):raise ValueError('Режим без альтернейтов требует корневой Main и canonical на себя.')
            candidates = [CATALOGUE[0]]
        suffix=f":{strategy(plan)}:301={int(plan.get('redirect_old_main',False))}:rewrite={int(plan.get('rewrite_title_h1',False))}"
        def rank(v):
            key=v['id']+suffix
            role=v['fake_on']
            return (*combinations.rank(rendered[key]), bool(role and role==last_fake.get(group(plan))),
                    fake_counts[(group(plan),role)] if role else 0,
                    personal[(site.id,key)],local[(group(plan),key)],counts[key],
                    fake_global[role] if role else 0,v['id'])
        candidates=[v for v in candidates if plan.get('without_alternates') or v['id']+suffix != (exclude or {}).get(plan['site_id'])]
        previous_id=((exclude or {}).get(plan['site_id']) or '').split(':')[0]
        previous=next((v for v in CATALOGUE if v['id']==previous_id),None)
        if previous and not plan.get('without_alternates'):
            def signature(v):
                links=set(v['links'])
                if parent:links.add('x-default')
                return frozenset(links),v['fake_on']
            candidates=[v for v in candidates if signature(v)!=signature(previous)]
        if not candidates:raise ValueError('Нет другой совместимой схемы для проекта.')
        rendered = {}
        unique = {}
        for candidate in candidates:
            trial = deepcopy(plan)
            try:
                render(trial, candidate, suffix, lang, geo)
            except ValueError:
                continue
            key = candidate['id'] + suffix
            rendered[key] = trial
            unique.setdefault(identity(trial), candidate)
        candidates = list(unique.values())
        if not candidates: raise ValueError('Нет совместимой комбинации настроек проекта.')
        chosen = min(candidates, key=rank)
        plan.update(rendered[chosen['id'] + suffix])
        combinations.stamp(plan, available=len(candidates))
        combinations.record(plan)
        record(plan)


def render(plan, chosen, suffix, lang, geo):
    plan['fake_hreflang_role']=chosen['fake_on']
    plan['scheme_variant']=chosen['id']+suffix
    if not chosen['links']:
        plan['alternateMarkup']='';plan['enableAlternates']=False
        plan['required_page_urls']=['https://'+plan['new_main']+'/']
    else:
        codes={'lang':lang,'locale':lang+'-'+geo,'x-default':'x-default'}
        links=[]
        if not plan.get('pilot_variation_version') and plan.get('scheme_mode') in {'preserve', 'add_auxiliary'}:
            basic = {lang.lower(), (lang+'-'+geo).lower(), 'x-default'}
            links = [(link['hreflang'], link['href']) for link in alternate_links(plan.get('alternateMarkup') or '') if link['hreflang'].lower() not in basic]
        for key in chosen['links']:
            path=plan['fake_main_path'] if key==chosen['fake_on'] else '/'
            host = plan.get('x_default_domain') if key == 'x-default' else plan.get('language_domain')
            links.append((codes[key],'https://'+(host or plan['new_main'])+path))
        parent=parent_domain(plan)
        if parent:
            # Prefer x-default for the parent; retain the fake link on another hreflang.
            links=[(code,href) for code,href in links if code!='x-default']
            links.append(('x-default','https://'+parent+'/'));plan['parent_alternate_domain']=parent
        plan['alternateMarkup']='\n'.join('<link rel="alternate" hreflang="'+escape(code,quote=True)+'" href="'+escape(href,quote=True)+'" />' for code,href in links)
        plan['enableAlternates']=True
        if len(links) == 1:
            plan['canonical_mode'] = 'self'
            plan['canonicalFakeMainMarkup'] = '<link rel="canonical" href="https://{{settings.canon}}/" />'
        if parent:
            apply_parent_x_default(plan, use_internal=plan.get('x_default_parent_path', '/') != '/')
        plan['required_page_urls'] = list(dict.fromkeys([*(plan.get('required_page_urls') or []), *[x['href'] for x in alternate_links(plan['alternateMarkup'])]]))
        validate_single_alternate(plan)
