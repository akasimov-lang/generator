"""Brand-first generated Titles, without changing Description or heading policy."""
import re

RULE_VERSION = 1


def brand_for_title(site):
    brand = ' '.join(str(getattr(site, 'brand', '') or '').split())
    if getattr(site, 'site_type', None) == 'general' or brand.casefold() == 'общие ключи':
        return ''
    return brand


def title_prefix_instruction(site):
    brand = brand_for_title(site)
    if not brand:
        return 'This is a general-keyword project: no brand-first Title rule applies. '
    return ('The page TITLE must begin with the exact project brand ' + repr(brand) + ', followed by a word boundary. '
            'Use its canonical spelling and casing. If the brand is already elsewhere in the original Title, '
            'move that mention to the beginning and rephrase naturally; do not duplicate it. If it is absent, '
            'add it once as the required project-brand context. Preserve the remaining meaning and facts. '
            'This prefix rule applies only to Title, not Description or headings. ')


def normalize_title_prefix(title, site):
    if not isinstance(title, str) or not title.strip():
        raise ValueError('Новый Title отсутствует.')
    title = title.strip()
    brand = brand_for_title(site)
    if not brand:
        return title
    match = re.match(re.escape(brand) + r'(?!\w)', title, re.I)
    if not match:
        raise ValueError(f'Новый Title должен начинаться с бренда «{brand}». Перепишите естественно, без дублирования бренда.')
    return brand + title[match.end():]


def title_prefix_valid(title, site):
    try:
        return normalize_title_prefix(title, site) == title
    except ValueError:
        return False


def title_validation_source(original, site):
    """Only the required brand addition may be absent from an older source Title."""
    from app.page_content_tools import brand_pattern, Markup
    brand = brand_for_title(site)
    if brand and not brand_pattern(brand).search(''.join(Markup(original).text)):
        return brand + ' — ' + original
    return original


def validate_title(original, revised, site, validator):
    revised = normalize_title_prefix(revised, site)
    source = title_validation_source(original, site)
    return validator(source, revised, brand_for_title(site))


def title_words_without_brand(original, site):
    from app.page_content_tools import Markup, brand_pattern
    brand = brand_for_title(site)
    value = ''.join(Markup(original).text)
    if brand:
        value = brand_pattern(brand).sub('', value)
    return re.findall(r'\w+', value.casefold())


def title_primary_phrase(original, site):
    return title_words_without_brand(original, site)[:2]
