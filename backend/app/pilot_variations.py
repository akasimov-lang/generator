"""Finalize global shares once, then persist exactly the plan shown to the user."""
from collections import Counter, defaultdict
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from copy import deepcopy
from hashlib import sha256
from html import escape
from app import models, auto_reglue as auto, cross_reglue as cross
from app.canonical_allocation import replay, mode
from app.domain_transfer_policy import domain_key
from app.network_state import alternate_links, validate_markup
from app.mass_action_scope import stamp_plan

SUBDOMAIN_PERCENT = 10
TitleRewriteMode = Literal['minimal', 'full_h1', 'full_all', 'mixed']
TITLE_REWRITE_LABELS = {
    'minimal': 'точечное обновление Title и H1',
    'full_h1': 'полное переписывание Title и H1',
    'full_all': 'полное переписывание Title и всех заголовков H1–H6',
}


def title_mode(value='minimal'):
    if value not in {*TITLE_REWRITE_LABELS, 'mixed'}:
        raise ValueError('Выберите допустимый режим переписывания заголовков.')
    return value



class PilotPercentages(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subdomains: int = Field(default=10, ge=0, le=100, strict=True)
    without_alternates: int = Field(default=10, ge=0, le=100, strict=True)
    redirects: int = Field(default=20, ge=0, le=100, strict=True)
    title_h1: int = Field(default=20, ge=0, le=100, strict=True)
    paragraphs: int = Field(default=0, ge=0, le=100, strict=True)
    internal_pages: int = Field(default=0, ge=0, le=100, strict=True)


def percentages(db, job=None):
    saved = job.payload.get('percentages') if job else None
    if not saved and job and job.result.get('variation_summary'):
        summary = job.result['variation_summary']
        saved = {'subdomains': summary.get('subdomains_percent', 15),
                 'without_alternates': summary.get('without_alternates_percent', 10),
                 'redirects': summary.get('redirects_percent', 20),
                 'title_h1': summary.get('title_h1_percent', 20),
                 'paragraphs': summary.get('paragraphs_percent', 0),
                 'internal_pages': summary.get('internal_pages_percent', 0)}
    return PilotPercentages.model_validate(saved or {'title_h1': auto.config(db).title_h1_rewrite_percent}).model_dump()



def count_share(total, percent):
    return (total * percent + 50) // 100


def distributed(plans, seed):
    groups = defaultdict(list)
    for p in plans: groups[(cross.brand_key(p.get('brand')), p.get('geo'))].append(p)
    for rows in groups.values(): rows.sort(key=lambda p: sha256((seed+p['site_id']).encode()).hexdigest())
    while groups:
        for key in sorted(list(groups)):
            yield groups[key].pop(0)
            if not groups[key]: del groups[key]


def allocate_headings(plans, requested, selected_mode, seed):
    fields = {'minimal':'editable_h1', 'full_h1':'editable_full_h1', 'full_all':'editable_all_headings'}
    modes = list(fields) if selected_mode == 'mixed' else [selected_mode]
    available = {p['site_id']: [m for m in modes if (p.get('title_h1_current') or {}).get(fields[m])] for p in plans}
    candidates = [p for p in distributed(plans, seed) if available[p['site_id']]][:requested]
    # Allocate constrained pages first, then fill the least-used compatible mode.
    counts, local, assigned = Counter(), Counter(), {}
    for plan in sorted(candidates, key=lambda p: len(available[p['site_id']])):
        group = (cross.brand_key(plan.get('brand')), plan.get('geo'))
        choice = min(available[plan['site_id']], key=lambda m: (counts[m], local[(group, m)], modes.index(m)))
        assigned[plan['site_id']] = choice
        counts[choice] += 1; local[(group, choice)] += 1
    return assigned


def parent_alternate(plan, parent, language):
    if not plan.get('enableAlternates', True): return
    links = alternate_links(plan.get('alternateMarkup') or '') if plan.get('enableAlternates', True) else []
    links = [link for link in links if link['hreflang'].lower() != 'x-default']
    if not links: links = [{'hreflang': language or 'und', 'href': 'https://' + plan['new_main'] + '/'}]
    links.append({'hreflang': 'x-default', 'href': 'https://' + parent + '/'})
    plan['alternateMarkup'] = '\n'.join('<link rel="alternate" hreflang="' + escape(link['hreflang'], quote=True) + '" href="' + escape(link['href'], quote=True) + '" />' for link in links)
    plan['enableAlternates'] = True
    plan['parent_alternate_domain'] = parent
    from app.pilot_schemes import apply_parent_x_default
    apply_parent_x_default(plan, use_internal=plan.get('x_default_parent_path', '/') != '/')
    validate_markup(plan['alternateMarkup'])


def finalize(db, job, result):
    if result.get('variations_finalized'): return
    if result.get('variations_allocated'):
        prepare_titles(db,job,result)
        return
    cfg = auto.config(db)
    all_plans = [p for g in result['groups'] for p in g.get('plans', [])]
    mixed = job.payload.get('planning_mode') == 'mixed'
    shares = percentages(db, job)
    plans = all_plans
    from app.pilot_released_reserves import recover
    # Each iteration can only add a previously skipped target. Bound the loop by
    # the saved selection, and never revise a finalized/reviewed plan on a read.
    for _ in range(len(result['items']) + 1):
        previous = plans
        desired = count_share(len(plans), shares['subdomains'])
        plans = allocate_subdomains(db, job, cfg, previous, desired, mixed)
        recovered = recover(db, job, result, previous, plans)
        if not recovered:
            break
        plans = [*plans, *recovered]
    total = len(plans)
    desired = count_share(total, shares['subdomains'])
    subplans = [p for p in plans if p.get('create_subdomain') or str(p.get('main_target_kind', '')).startswith('sub_')]
    redirect_count = count_share(total,shares['redirects'])
    # Avoid redirecting the parent required as an alternate for a subdomain Main.
    redirect_candidates = [p for p in plans if domain_key(p.get('old_main','')) != domain_key(p.get('parent_alternate_domain',''))]
    redirects = {p['site_id'] for p in list(distributed(redirect_candidates,job.id+':redirect'))[:redirect_count]}
    rewrite_count = count_share(total,shares['title_h1'])
    rewrite_mode = title_mode(job.payload.get('title_rewrite_mode', 'minimal'))
    heading_modes = allocate_headings(plans, rewrite_count, rewrite_mode, job.id+':title-h1')
    rewrites = set(heading_modes)
    from app.short_h1 import allocate as allocate_short_h1
    short_h1_ids = set(allocate_short_h1([p['site_id'] for p in plans
        if p['site_id'] in rewrites and (p.get('title_h1_current') or {}).get('h1')], job.id))
    paragraphs_count = count_share(total, shares['paragraphs'])
    paragraphs = {p['site_id'] for p in list(distributed(plans, job.id+':paragraphs'))[:paragraphs_count]}
    from app.pilot_internal_pages_policy import allocate as allocate_internal_pages
    internal_pages_requested = count_share(total, shares['internal_pages'])
    internal_pages_eligible = allocate_internal_pages(db, plans, job.payload.get('generation_id', job.id), internal_pages_requested)
    internal_pages_count = sum(bool(p.get('internal_pages', {}).get('enabled')) for p in plans)
    no_alternate_target=count_share(total,shares['without_alternates'])
    eligible=[p for p in plans if not p.get('parent_domain') and not p.get('create_subdomain')
        and (p.get('main_target_kind')=='newreg' or p.get('domain_type')=='newreg' or p.get('required_domain_type')=='newreg')
        and mode(p.get('canonicalFakeMainMarkup'),p.get('fake_main_path'))=='self']
    if mixed:
        # A subdomain always needs its parent in x-default; split only compatible roots.
        no_alternate_target = count_share(len(eligible), 50)
    without_alternates={p['site_id'] for p in list(distributed(eligible,job.id+':no-alternates'))[:no_alternate_target]}
    by_id = {}
    for p in plans:
        p['without_alternates'] = p['site_id'] in without_alternates
        p['redirect_old_main'] = p['site_id'] in redirects
        p['rewrite_title_h1'] = p['site_id'] in rewrites
        p['title_rewrite_mode'] = heading_modes.get(p['site_id'], 'minimal' if rewrite_mode == 'mixed' else rewrite_mode)
        if mixed: p['planning_mode'] = 'mixed'
        p['short_h1'] = p['site_id'] in short_h1_ids
        p['rewrite_paragraphs'] = p['site_id'] in paragraphs
        p['pilot_variation_version'] = 1
        p.pop('preview_token', None)
        by_id[p['site_id']] = p
    from app.pilot_schemes import assign
    assign(db, list(by_id.values()))
    from app.cross_reglue_batch import key, validate
    from app.auto_pilot import describe
    for g in result['groups']:
        g['plans'] = [by_id[p['site_id']] for p in g.get('plans',[])]
        for p in g['plans']:
            if g.get('batch_id'): p['batch_id'] = g['batch_id']
            p['preview_token'] = auto.digest(p)
            result['items'][p['site_id']].update(**describe(db,p))
        if g.get('batch_id'):
            validate(g['plans'])
            ledger = db.get(models.AutoReglueConfig,key(g['batch_id']))
            ledger.value = {**ledger.value, 'plans':deepcopy(g['plans']),
                            'skipped':[row for row in ledger.value.get('skipped', []) if row['site_id'] not in by_id]}
    counts = Counter(mode(p.get('canonicalFakeMainMarkup'),p.get('fake_main_path')) for p in plans)
    result['variation_summary'] = {'total':total,'subdomains':len(subplans),'emergency_subdomains':sum(bool(p.get('emergency_subdomain')) for p in plans),'subdomains_requested':desired,'subdomains_percent':shares['subdomains'], 'redirects_percent':shares['redirects'], 'without_alternates_percent':shares['without_alternates'],
        'redirects':len(redirects),'redirects_requested':redirect_count,'title_h1':len(rewrites),
        'title_h1_requested':rewrite_count, 'title_h1_percent':shares['title_h1'], 'short_h1':len(short_h1_ids),'short_h1_percent':50,
        'paragraphs':len(paragraphs), 'paragraphs_requested':paragraphs_count, 'paragraphs_percent':shares['paragraphs'],'canonical_self':counts['self'],'canonical_internal':counts['internal'],
        'internal_pages':internal_pages_count, 'internal_pages_requested':internal_pages_requested,
        'internal_pages_eligible':internal_pages_eligible, 'internal_pages_percent':shares['internal_pages'],
        'without_alternates':len(without_alternates), 'without_alternates_requested':no_alternate_target, 'catalogue_upper_bound':672, 'used_variants':len({p.get('scheme_variant') for p in plans if p.get('scheme_variant')}),
        'warning': ('Недостаточно подходящих заголовков для заданной доли и режима Title/H1. ' if len(rewrites)<rewrite_count else '') + ('Не хватает совместимых корневых новорегов для заданной доли без альтернейтов. ' if len(without_alternates)<no_alternate_target else '') + ('Не для всех долей поддоменов найдены разрешённые родители. ' if len(subplans)<desired else 'Поддомены сверх заданной доли: исключение для сеток без резервов. ' if len(subplans)>desired and any(p.get('emergency_subdomain') for p in plans) else '') + ('Не хватает совместимых проектов для доли 301.' if len(redirects)<redirect_count else '')}
    result['variations_allocated'] = True
    if internal_pages_count < internal_pages_requested:
        result['variation_summary']['warning'] += ' Не хватает подтверждённых одностраничных монобрендов для заданной доли внутренних страниц.'
    result['variation_summary'].update(naming_summary(plans))
    if mixed:
        result['variation_summary']['warning'] += ' Смешанный режим: равномерно распределены доступные варианты. Выбранные резервы и совместимость схем имеют приоритет; доля без альтернейтов считается среди совместимых корневых новорегов.'
    if rewrite_mode == 'mixed':
        counts = Counter(heading_modes.values())
        if max((counts[m] for m in TITLE_REWRITE_LABELS), default=0) - min((counts[m] for m in TITLE_REWRITE_LABELS), default=0) > 1:
            result['variation_summary']['warning'] += ' Режимы заголовков распределены не поровну: часть страниц поддерживает не все способы переписывания.'
    prepare_titles(db,job,result)


def allocate_subdomains(db, job, cfg, all_plans, desired, mixed):
    subplans = [p for p in all_plans if p.get('create_subdomain') or str(p.get('main_target_kind', '')).startswith('sub_')]
    assigned = {domain_key(p.get(key)) for p in all_plans for key in ('new_main', 'parent_domain', 'parent_alternate_domain') if p.get(key)}
    replacements = {}
    reasons = []
    # Existing selected reserves keep their priority. Pick local parents without transfers.
    candidates = [] if mixed else [p for p in all_plans if p not in subplans and not p.get('use_selected_reserve') and p.get('execution_mode') == 'cross_network' and not p.get('replace_banned_reserve')]
    for old in distributed(candidates, job.id + ':subdomains'):
        if len(subplans) >= desired: break
        site = db.get(models.Site, old['site_id'])
        state = {**old['target_guard'], 'domains':old['target_domains'], 'revision':old['revision']}
        allowed = {**state, 'domains':[d for d in state['domains'] if domain_key(d) not in assigned or domain_key(d) == domain_key(old['new_main'])]}
        from app.mass_main_targets import subdomain_candidate
        choice = None
        types = ('newreg', 'drop') if len(subplans) % 2 == 0 else ('drop', 'newreg')
        for kind in types:
            if cfg.main_target_mode in ('newreg','drop') and kind != cfg.main_target_mode: continue
            try:
                parent, child = subdomain_candidate(db, site, allowed, 'sub_' + kind, cfg, prefer_geo=True, allocation_plans=subplans)
                if domain_key(child) in assigned: continue
                choice = parent, child, kind; break
            except ValueError: continue
        if not choice: continue
        parent, child, kind = choice
        try:
            with replay(db, old):
                plan = cross.make_plan(cfg, site, state, site, state, child, mode='local_subdomain', db=db,
                    plans=[p for p in all_plans if p['site_id'] != site.id])
            # Keep the already reviewed, collision-free fake path instead of allocating again.
            for key in ('title_h1_current','fake_main_path','create_fake_main_path','new_fake_main_path','canonicalFakeMainMarkup','canonical_mode'):
                if key in old: plan[key] = old[key]
            if old.get('fake_main_path') and plan.get('fake_main_path'):
                plan['alternateMarkup'] = old.get('alternateMarkup','').replace(old['new_main'], child)
            plan.update(local_target=True, parent_domain=parent, create_subdomain=child, main_target_kind='sub_'+kind,
                required_domain_type=kind, domain_type=kind, requires_newreg=False, pilot_subdomain=True)
            parent_alternate(plan, parent, (site.cache_language or '').replace('_','-').split('-')[0])
            plan['required_page_urls'] = ['https://' + child + '/'] + (['https://' + child + plan['fake_main_path']] if plan.get('fake_main_path') else [])
            plan = stamp_plan(db, plan, state, site, old.get('mass_filter'))
            replacements[site.id] = plan; subplans.append(plan); assigned.add(domain_key(child))
        except ValueError as error: reasons.append(str(error))
    return [replacements.get(p['site_id'], p) for p in all_plans]


def naming_summary(plans):
    from app.domain_classification import registrable_root
    prefixes, paths = Counter(), Counter()
    for plan in plans:
        child = plan.get('create_subdomain')
        root = registrable_root(child) if child else None
        if root and child != root: prefixes[child[:-(len(root) + 1)]] += 1
        if plan.get('create_fake_main_path'): paths[plan['create_fake_main_path']] += 1
    return {'subdomain_names': dict(prefixes), 'fake_path_names': dict(paths),
            'unique_subdomain_names': len(prefixes), 'unique_fake_path_names': len(paths),
            'x_default_parent_root': sum(p.get('x_default_policy_version') == 1 and p.get('x_default_parent_path') == '/' for p in plans),
            'x_default_parent_internal': sum(p.get('x_default_policy_version') == 1 and p.get('x_default_parent_path') not in (None, '/') for p in plans)}


def prepare_titles(db,job,result):
    """Checkpoint each selected text draft; resumes keep the reviewed allocation."""
    if db.info.get("parallel_pilot_texts") or result.get("parallel_texts"):
        from app.pilot_text_jobs import sync
        sync(db,job,result)
        return
    from app.mass_reglue_launch import check_preview_cancelled
    from app.reglue_title_h1 import prepare_for_plan
    from app.reglue_paragraphs import prepare_for_plan as prepare_paragraphs
    from app.cross_reglue_batch import key
    from app.auto_pilot import describe
    plans=[p for g in result['groups'] for p in g.get('plans',[])]
    selected={field:[p for p in plans if p.get('rewrite_'+field)] for field in ('title_h1','paragraphs')}
    def save():
        check_preview_cancelled(db,job)
        for field, rows in selected.items():
            result[field+'_progress']={'done':sum(bool(p.get(field+'_preview') or p.get(field+'_error')) for p in rows),'total':len(rows)}
        job.result=deepcopy(result);db.commit()
    save()
    for group in result['groups']:
        for plan in group.get('plans',[]):
            for field, prepare in (('title_h1',prepare_for_plan),('paragraphs',prepare_paragraphs)):
                check_preview_cancelled(db,job)
                if not plan.get('rewrite_'+field) or plan.get(field+'_preview') or plan.get(field+'_error'):continue
                prepare(db,plan,job.payload.get('generation_id',job.id))
                check_preview_cancelled(db,job)
                plan.pop('preview_token',None);plan['preview_token']=auto.digest(plan)
                result['items'][plan['site_id']].update(**describe(db,plan))
                if group.get('batch_id'):
                    ledger=db.get(models.AutoReglueConfig,key(group['batch_id']))
                    ledger.value={**ledger.value,'plans':deepcopy(group['plans'])}
                save()
    result['variations_finalized']=True
    save()


def update_summary(result):
    plans = [p for g in result['groups'] for p in g.get('plans', [])]
    old = result.get('variation_summary') or {}
    total = len(plans)
    counts = Counter(mode(p.get('canonicalFakeMainMarkup'), p.get('fake_main_path')) for p in plans)
    subs = sum(bool(p.get('create_subdomain') or p.get('parent_domain')) for p in plans)
    redirects = sum(bool(p.get('redirect_old_main')) for p in plans)
    rewrites = sum(bool(p.get('rewrite_title_h1')) for p in plans)
    paragraphs = sum(bool(p.get('rewrite_paragraphs')) for p in plans)
    internal_pages = sum(bool((p.get('internal_pages') or {}).get('enabled')) for p in plans)
    internal_pages_percent = old.get('internal_pages_percent', 0)
    paragraph_percent = old.get('paragraphs_percent', 0)
    percent = old.get('title_h1_percent', 20)
    sub_percent = old.get('subdomains_percent', 15)  # Preserve already reviewed historic plans.
    redirect_percent = old.get('redirects_percent', 20)
    no_alt_percent = old.get('without_alternates_percent', 10)
    mixed = any(p.get('planning_mode') == 'mixed' for p in plans)
    no_alt_base = sum(not p.get('parent_domain') and not p.get('create_subdomain')
        and (p.get('main_target_kind') == 'newreg' or p.get('domain_type') == 'newreg' or p.get('required_domain_type') == 'newreg')
        and mode(p.get('canonicalFakeMainMarkup'), p.get('fake_main_path')) == 'self' for p in plans) if mixed else total
    mismatch = paragraphs != count_share(total, paragraph_percent) or subs != count_share(total,sub_percent) or redirects != count_share(total,redirect_percent) or rewrites != count_share(total,percent) or sum(bool(p.get('without_alternates')) for p in plans) != count_share(no_alt_base,no_alt_percent)
    result['variation_summary'] = {**old, 'total':total, 'subdomains':subs, 'subdomains_requested':count_share(total,sub_percent),'subdomains_percent':sub_percent,
        'redirects':redirects, 'redirects_requested':count_share(total,redirect_percent), 'title_h1':rewrites,'title_h1_percent':percent,'title_h1_requested':count_share(total,percent),
        'short_h1':sum(bool(p.get('rewrite_title_h1') and p.get('short_h1')) for p in plans),
        'paragraphs':paragraphs, 'paragraphs_requested':count_share(total,paragraph_percent), 'paragraphs_percent':paragraph_percent,
        'internal_pages':internal_pages, 'internal_pages_requested':count_share(total,internal_pages_percent),
        'internal_pages_percent':internal_pages_percent,
        'internal_pages_eligible':sum(bool((p.get('internal_pages_eligibility') or {}).get('eligible')) for p in plans),
        'canonical_self':counts['self'], 'canonical_internal':counts['internal'],
        'without_alternates':sum(bool(p.get('without_alternates')) for p in plans), 'without_alternates_requested':count_share(no_alt_base,no_alt_percent),
        'used_variants':len({p.get('scheme_variant') for p in plans if p.get('scheme_variant')}),
        'warning':'После изменения состава плана доли отличаются от заданных. Обновите весь план для нового распределения.' if mismatch else ''}
    if internal_pages < count_share(total, internal_pages_percent):
        result['variation_summary']['warning'] += ' Не хватает подтверждённых одностраничных монобрендов для заданной доли внутренних страниц.'
