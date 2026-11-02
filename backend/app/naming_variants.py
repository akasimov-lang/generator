"""Stable spelling families shared by new domain and internal-page plans."""
import hashlib
import re

from app.site_brands import BRANDS, GENERAL, normalized


def allocation_index(plans, site_id=None, *, subdomains=False):
    """Count distinct already allocated projects, including previous batch groups."""
    return len({p['site_id'] for p in plans if p.get('site_id') and p['site_id'] != site_id
                and (not subdomains or p.get('create_subdomain'))})


def families(brand, geo, language, *, casino=True):
    generic = not (brand or '').strip() or brand.strip() == GENERAL
    if generic:
        return [('geo-language', [geo + '-' + language]),
                ('casino-geo', ['casino-' + geo]),
                ('geo-casino', [geo + '-casino']),
                ('online-casino', ['online-casino-' + geo])]
    aliases = [brand]
    for canonical, known in BRANDS.items():
        if normalized(brand) in {normalized(canonical), *(normalized(v) for v in known)}:
            aliases = [canonical, *known]; break
    spellings = list(dict.fromkeys(re.sub('[^a-z0-9-]', '', re.sub(r'[\s_.]+', '-', alias.lower())).strip('-')
                                  for alias in aliases if re.search('[a-z]', alias.lower())))
    if not spellings: raise ValueError('Для имени нужны бренд латиницей, GEO и язык проекта.')
    result = [('brand-geo', [v + '-' + geo for v in spellings]),
              ('geo-brand', [geo + '-' + v for v in spellings]),
              ('brand-language', [v + '-' + language for v in spellings]) if language != geo else
              ('brand', [re.sub('casino', '', v).strip('-') or v for v in spellings])]
    if casino or any('casino' in v for v in spellings):
        result.insert(2, ('brand-casino', [v if 'casino' in v else v + '-casino' for v in spellings]))
    return result


def names(brand, geo, language, *, index, seed='', style='mixed', casino=True):
    """Rotate families evenly; choose spelling deterministically within a family."""
    options = families(brand, geo, language, casino=casino)
    shift = index % len(options)
    ordered = options[shift:] + options[:shift]
    result = []
    for family, spellings in ordered:
        labels = []
        for spelling in spellings:
            if style in {'hyphen', 'mixed'}: labels.append(spelling)
            if style in {'joined', 'mixed'}: labels.append(spelling.replace('-', ''))
        labels = list(dict.fromkeys(labels))
        labels.sort(key=lambda label: hashlib.sha256((str(seed) + ':' + family + ':' + label).encode()).hexdigest())
        result.extend(labels)
    return list(dict.fromkeys(result))
