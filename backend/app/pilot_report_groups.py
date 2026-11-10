"""Stable report grouping from saved task intent, with legacy maintenance fallbacks."""
import re
from collections import Counter

GROUPS = ('layout', 'showcases', 'reglues', 'brands', 'other')
LAYOUT_TYPES = {'site_maintenance', 'structured_data', 'toc_repair', 'article_image_localization'}
GENERAL_BRANDS = {'общие ключи', 'основные ключи', 'все бренды', 'general'}


def brand_scope(payload):
    scope = payload.get('planning_filter') or payload.get('filter') or {}
    if scope.get('scope_mode') == 'exclude':
        return False
    brands = scope.get('brands') or [scope.get('brand') or payload.get('split_brand')]
    brands = {str(b).strip().casefold() for b in brands if b and str(b).strip()}
    return len(brands) == 1 and not brands.intersection(GENERAL_BRANDS)


def group(job):
    payload, result = job.payload or {}, job.result or {}
    explicit = payload.get('report_group')
    if explicit in GROUPS:
        return explicit
    kind = payload.get('task_type') or ''
    if job.kind in {'auto_pilot_preview', 'mass_reglue_list'}:
        return 'brands' if brand_scope(payload) else 'reglues'
    if kind == 'brand_content_network_program':
        return 'brands'
    # Early brand programs predate task_type; their saved operations distinguish
    # them from layout/content jobs whose title happens to mention the same brand.
    entries = result.get('entries') or []
    if not kind and (payload.get('program') or payload.get('text_revision_20261027')) and any(
            row.get('network_operation_ids') or row.get('network_operations') for row in entries):
        return 'brands'
    name = str(payload.get('name') or '').casefold().replace('ё', 'е')
    if kind.startswith('showcase_') or re.search(r'\bвитрин|\bshowcase', name):
        return 'showcases'
    # The presence of a saved showcase design alone is insufficient: reports can
    # explicitly preserve an existing showcase while changing only the footer.
    if not payload.get('preserve_existing_showcases') and any(
            row.get('showcase_actions') or row.get('showcase_change') or row.get('showcase_applied_at') for row in entries):
        return 'showcases'
    if kind in LAYOUT_TYPES or re.search(
            r'верстк|шаблон|футер|шапк|меню|навигац|кнопк|хлебн|крош|отступ|логотип|favicon|faq|ссылк|содержани|микроразметк', name):
        return 'layout'
    return 'other'


def partition(jobs, selected='all'):
    if selected not in ('all', *GROUPS):
        raise ValueError('Неизвестная группа отчётов.')
    classified = [(job, group(job)) for job in jobs]
    counts = Counter(category for _, category in classified)
    return ([job for job, category in classified if selected == 'all' or category == selected],
            {'all': len(jobs), **{key: counts[key] for key in GROUPS}})
