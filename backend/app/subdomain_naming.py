"""Deterministic names: a persisted run chooses exactly one unused subdomain."""
import re
import hashlib
from app.domain_classification import registrable_root
from app.network_state import domain_name
from app.site_brands import GENERAL
from app.fake_main import alphabetic_suffix


def allow_numeric_subdomains(state):
    numbered = set()
    for value in state.get('domains', []):
        name = domain_name(value).removeprefix('www.')
        root = registrable_root(name)
        if root and name != root and re.search(r'\d', name[:-(len(root) + 1)]):
            numbered.add(name)
    return len(numbered) > 10


def validate_new_names(state, plan):
    from app.fake_main import allow_numeric_fake_paths
    child = domain_name(plan.get('create_subdomain') or '')
    root = registrable_root(child) if child else ''
    label = child[:-(len(root) + 1)] if root and child != root else ''
    path = plan.get('create_fake_main_path') or ''
    if re.search(r'\d', label) and not allow_numeric_subdomains(state):
        raise ValueError('В новой сетке имя поддомена должно быть без цифр. Обновите план.')
    if re.search(r'\d', path) and not allow_numeric_fake_paths(state):
        raise ValueError('Новая внутренняя страница должна иметь адрес без цифр. Обновите план.')


def validate_unstarted_plan(db, run, state, *, cross=False):
    """Reviewed old plans must be refreshed; already-started receipts stay intact."""
    if run.phase != 'prepared': return
    from uuid import UUID, uuid5
    from app import models
    actions = ('delete_domain', 'create_domains', 'create_subdomains', 'create_fake_main', 'reserve', 'reglue', 'alternates')
    prefix = 'cross:' if cross else ''
    if any(db.get(models.NetworkOperation, str(uuid5(UUID(run.id), prefix + action))) for action in actions): return
    validate_new_names(state, run.plan)


def next_subdomain(site, state, cfg, parent, *, prefer_geo=False, allocation_index=None):
    parent = domain_name(parent).removeprefix('www.')
    network = {domain_name(d).removeprefix('www.') for d in state['domains']}
    cached = {domain_name(d).removeprefix('www.') for d in (getattr(site, 'cache_domains', None) or [])}
    if parent not in network or parent not in cached:
        raise ValueError('Родитель поддомена должен присутствовать в кеше и актуальной сетке.')
    if registrable_root(parent) != parent:
        raise ValueError('Для создания поддомена выберите корневой домен.')
    types = getattr(site, 'domain_types', None) or {}
    kind = types.get(parent) or types.get('www.' + parent)
    if parent in {d.removeprefix('www.') for d in state.get('amp_domains', [])} or kind == 'amp':
        raise ValueError('Нельзя создавать поддомены AMP для переклеев.')
    if kind != cfg.parent_kind:
        raise ValueError('Тип родителя не соответствует выбранному варианту создания поддомена.')
    brand = getattr(site, 'brand', '') or ''
    generic = not brand.strip() or brand.strip() == GENERAL
    brand = re.sub(r'[^a-z0-9]', '', brand.lower())
    geo = (site.cache_geo or '').lower()
    language = (getattr(site, 'cache_language', None) or cfg.language).lower().replace('_', '-').split('-')[0]
    if (not generic and not brand) or not re.fullmatch('[a-z]{2}', geo) or not re.fullmatch('[a-z]{2,3}', language):
        raise ValueError('Для имени поддомена нужны бренд латиницей, GEO и язык проекта.')
    brands = [brand]
    if cfg.subdomain_add_casino and 'casino' not in brand:
        brands.append(brand + 'casino')
    occupied = {domain_name(d) for d in [*state['domains'], *state.get('amp_domains', []),
        *(getattr(site, 'cache_domains', None) or []), *(getattr(site, 'main_domain_history', None) or []),
        *(getattr(site, 'alternate_domain_history', None) or []),
        *(getattr(site, 'x_default_history', None) or []), *types]}
    candidates = []
    if generic:
        templates = [f'online-casino-{geo}-{language}', f'casino-online-{geo}', f'casinos-top-{geo}']
        if cfg.subdomain_name_style in {'hyphen', 'mixed'}:
            candidates.extend(templates)
        if cfg.subdomain_name_style in {'joined', 'mixed'}:
            candidates.extend(label.replace('-', '') for label in templates)
    for prefix in ([] if generic else brands):
        base = prefix + geo
        if cfg.subdomain_name_style in {'joined', 'mixed'}:
            candidates.extend([base, *(base + str(i) for i in range(1, 11)), base + language])
        if cfg.subdomain_name_style in {'hyphen', 'mixed'}:
            dashed_brand = brand + '-casino' if prefix != brand else brand
            dashed = dashed_brand + '-' + geo
            candidates.extend([dashed, *(dashed + '-' + str(i) for i in range(1, 11)), dashed + '-' + language])
    candidates = list(dict.fromkeys(candidates))
    numeric = [label for label in candidates if re.search(r'\d', label)]
    candidates = list(dict.fromkeys(re.sub(r'\d', '', label).strip('-') for label in candidates))
    candidates = [label for label in candidates if label]
    if prefer_geo:
        # Digits in the root (e.g. 22bet.com) do not establish a numbered
        # subdomain convention. Only current subdomain labels can do that.
        preferred = [geo]
        suffixes = ([] if generic else brands) + ([language] if language != geo else [])
        for suffix in suffixes:
            if cfg.subdomain_name_style in {'joined', 'mixed'}:
                preferred.append(geo + suffix)
            if cfg.subdomain_name_style in {'hyphen', 'mixed'}:
                preferred.append(geo + '-' + suffix)
        numeric = list(dict.fromkeys([*numeric, *(label + str(i) for label in preferred for i in range(1, 11))]))
        candidates = list(dict.fromkeys(re.sub(r'\d', '', label).strip('-') for label in [*preferred, *candidates]))
    if allocation_index is not None:
        from app.naming_variants import names
        diverse = names(getattr(site, 'brand', '') or '', geo, language, index=allocation_index,
                        seed=str(getattr(site, 'id', '') or getattr(site, 'name', '')) + ':' + parent,
                        style=cfg.subdomain_name_style, casino=True)
        numeric = list(dict.fromkeys([*diverse, *numeric]))
        candidates = list(dict.fromkeys(re.sub(r'\d', '', label).strip('-') for label in [*diverse, *candidates]))
        candidates = [label for label in candidates if label]
    elif cfg.subdomain_name_style == 'mixed' and not prefer_geo:
        # Stable per-project order: preview/retry chooses the same name, while
        # different projects and subsequent iterations vary the spelling.
        seed = str(getattr(site, 'id', None) or site.name) + ':' + parent
        candidates.sort(key=lambda label: hashlib.sha256((seed + ':' + label).encode()).hexdigest())
    if allow_numeric_subdomains(state): candidates.extend(numeric)
    for label in candidates:
        candidate = label + '.' + parent
        if len(label) <= 63 and len(candidate) <= 253 and candidate not in occupied:
            return candidate
    separator = '' if cfg.subdomain_name_style == 'joined' else '-'
    base = candidates[0] if candidates else geo
    maximum = min(63, 252 - len(parent))
    for index in range(len(occupied) + 1):
        suffix = alphabetic_suffix(index)
        prefix = base[:maximum - len(suffix) - len(separator)].rstrip('-')
        if not prefix: raise ValueError('Родительский домен слишком длинный для нового поддомена.')
        candidate = prefix + separator + suffix + '.' + parent
        if candidate not in occupied: return candidate
