"""Eligibility and a saved allocation for expanding one-page branded projects."""
from datetime import datetime, timezone
from hashlib import sha256

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app import models, project_network
from app.mass_action_scope import brand_key
from app.project_cache import ProjectCacheError
from app.project_network import NetworkConflict
from app.project_pages import is_home, page_key, pages


def eligibility(db, site, project, *, exclude_task_id=None):
    """`project` must be a fresh Webdev read, never an inferred cached count."""
    snapshot = {'eligible': False, 'checked_at': datetime.now(timezone.utc).isoformat(),
                'page_count': None, 'home_page_key': None, 'brand': site.brand if site else None,
                'geo': site.cache_geo if site else None, 'language': site.cache_language if site else None}
    reason = None
    if not site or not site.is_active or site.hidden_from_projects:
        reason = 'Проект недоступен.'
    elif site.site_type not in (None, 'monobrand') or brand_key(site.brand) in {'', brand_key('Общие ключи')}:
        reason = 'Внутренние страницы планируются только для монобрендов.'
    elif not site.cache_geo or not site.cache_language:
        reason = 'Для генерации меню нужны GEO и язык проекта.'
    else:
        try:
            current = pages(project)
        except (HTTPException, AttributeError, TypeError):
            reason = 'Webdev не подтвердил полный список страниц.'
        else:
            snapshot['page_count'] = len(current)
            if len(current) != 1 or not is_home(current[0]):
                reason = 'Внутренние страницы можно планировать только для одностраничника.'
            elif current[0].get('id') is None or not isinstance(current[0].get('slug'), str):
                reason = 'Webdev не подтвердил главную страницу проекта.'
            else:
                snapshot['home_page_key'] = page_key(current[0])
                # A concurrent local draft/publication must not create a second menu.
                # The shared conflict policy releases only safely archived unpublished drafts.
                from app.services import find_content_slug_conflict
                query = select(models.ContentItem).where(models.ContentItem.site_id == site.id,
                                                        models.ContentItem.status != 'deleted')
                if exclude_task_id:
                    query = query.where(models.ContentItem.task_id != exclude_task_id)
                for item in db.scalars(query):
                    slug = item.slug
                    if not slug or slug.strip('/') == '':
                        continue
                    conflict = find_content_slug_conflict(db, site.id, slug)
                    if conflict and conflict.task_id != exclude_task_id:
                        reason = 'Для проекта уже подготовлены или публикуются внутренние страницы.'
                        break
    return {**snapshot, 'eligible': reason is None, 'reason': reason}


def require_eligible(db, site, project, *, exclude_task_id=None):
    result = eligibility(db, site, project, exclude_task_id=exclude_task_id)
    if not result['eligible']:
        raise ValueError(result['reason'])
    return result


def allocate(db, plans, seed, requested):
    """Independent quota: deterministic spread, no writes to Webdev or AI calls."""
    from app.pilot_variations import distributed
    for plan in plans:
        plan.pop('internal_pages', None)
        plan.pop('internal_pages_eligibility', None)
    if requested == 0:
        return 0
    candidates = []
    for plan in plans:
        site = db.get(models.Site, plan['site_id'])
        # Avoid remote calls for a known non-brand; absence of page data is never success.
        if not site or site.site_type not in (None, 'monobrand') or brand_key(site.brand) in {'', brand_key('Общие ключи')}:
            checked = eligibility(db, site, {})
        else:
            try:
                with project_network.Remote(db, site) as remote:
                    checked = eligibility(db, site, remote.project())
            except (ProjectCacheError, NetworkConflict, httpx.HTTPError, ValueError, HTTPException, AttributeError, TypeError):
                checked = {'eligible': False, 'reason': 'Не удалось подтвердить, что проект одностраничный.',
                           'checked_at': datetime.now(timezone.utc).isoformat(), 'page_count': None}
        plan['internal_pages_eligibility'] = checked
        if checked['eligible']:
            candidates.append(plan)
    offset = int(sha256(seed.encode()).hexdigest()[:8], 16) % 4
    for index, plan in enumerate(list(distributed(candidates, seed + ':internal-pages'))[:requested]):
        plan['internal_pages'] = {'enabled': True, 'count': 3 + (offset + index) % 4,
                                  'menu_type': 'header', 'levels': 1, 'mode': 'thematic',
                                  'auto_publish': True, 'status': 'planned',
                                  'eligibility': plan['internal_pages_eligibility']}
    return len(candidates)
