"""Deterministic names: a persisted run chooses exactly one unused subdomain."""
import re
import hashlib
from app.domain_classification import registrable_root
from app.network_state import domain_name
from app.site_brands import GENERAL


def next_subdomain(site, state, cfg, parent):
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
        *(getattr(site, 'alternate_domain_history', None) or []), *types]}
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
    if cfg.subdomain_name_style == 'mixed':
        # Stable per-project order: preview/retry chooses the same name, while
        # different projects and subsequent iterations vary the spelling.
        seed = str(getattr(site, 'id', None) or site.name) + ':' + parent
        candidates.sort(key=lambda label: hashlib.sha256((seed + ':' + label).encode()).hexdigest())
    for label in candidates:
        candidate = label + '.' + parent
        if len(label) <= 63 and len(candidate) <= 253 and candidate not in occupied:
            return candidate
    raise ValueError('Все варианты имён поддомена заняты. Освобождение старого имени не приводит к его повторному использованию.')
