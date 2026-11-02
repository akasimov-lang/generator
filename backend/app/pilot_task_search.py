"""Search visible tasks before pagination, without starting or changing their work."""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from sqlalchemy import select
from app import models
from app.pilot_scope import country_key


def normalized(value):
    text = unicodedata.normalize('NFKD', str(value or '')).casefold()
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^\w]+', ' ', text).strip()


@lru_cache(maxsize=1)
def country_names():
    return json.loads(Path(__file__).with_name('data').joinpath('task_search_countries.json').read_text())


def country_terms(value):
    code = country_key(value)
    return ' '.join([code, *country_names().get(code, [])])


def fields(record):
    if not isinstance(record, dict):
        return []
    result = [record.get(key) or '' for key in ('name', 'project', 'brand', 'main', 'old_main', 'new_main', 'source_project', 'parent_domain', 'create_subdomain')]
    result.append(country_terms(record.get('geo') or ''))
    for key in ('before', 'after', 'plan'):
        if isinstance(record.get(key), dict):
            result.extend(fields(record[key]))
    return result


def completed(job, db=None):
    # A prepared draft still needs a launch; it is not an executed task.
    if job.kind == 'auto_pilot_preview' or job.status != 'completed':
        return False
    if db is not None and job.kind == 'mass_reglue_list':
        from app.pilot_internal_pages import report_status
        if report_status(db, job) != 'completed':
            return False
    entries = (job.result or {}).get('entries', [])
    return not any(row.get('status') in {'pending', 'running', 'waiting', 'queued'} for row in entries)


def order_and_filter(db, jobs, query='', numbers=None):
    query = normalized(query)
    numbers = numbers or {}
    if query:
        ids = {site_id for job in jobs for site_id in (job.payload or {}).get('site_ids', [])}
        sites = {site.id: site for site in db.scalars(select(models.Site).where(models.Site.id.in_(ids)))} if ids else {}
        matches = []
        for job in jobs:
            payload, result = job.payload or {}, job.result or {}
            values = [job.id, str(numbers.get(job.id, '')), payload.get('name', ''), payload.get('draft_name', '')]
            if job.kind != 'maintenance_report':
                from app.auto_pilot import draft_name
                values.append(draft_name(job))
            for key in ('planning_filter', 'filter'):
                scope = payload.get(key) or {}
                values.extend([scope.get('brand') or '', *(scope.get('brands') or [])])
                values.extend(country_terms(geo) for geo in (scope.get('geos') or [scope.get('geo') or '']))
            items = result.get('items') or {}
            records = list(items.values()) if isinstance(items, dict) else list(items)
            records.extend(result.get('entries') or [])
            for group in result.get('groups') or []:
                records.append(group.get('filter') or {})
                records.extend(group.get('plans') or [])
            for record in records:
                values.extend(fields(record))
            for site_id in payload.get('site_ids', []):
                site = sites.get(site_id)
                if not site:
                    continue
                values.extend([site.name, site.brand, site.cache_canon or '', country_terms(site.cache_geo or '')])
                values.extend(domain if isinstance(domain, str) else domain.get('domain', '') for domain in (site.cache_domains or []) if isinstance(domain, (str, dict)))
            corpus = normalized(' '.join(str(value) for value in values))
            compact = corpus.replace(' ', '')
            # Brand spelling with spaces or hyphens can differ between names and cache.
            tokens = query.split()
            geo_tokens = {token for token in tokens if len(token) == 2 and token.upper() in country_names()}
            if (all(re.search(r'(?<!\w)' + re.escape(token) + r'(?!\w)', corpus) if token in geo_tokens else token in corpus for token in tokens)
                    or not geo_tokens and query.replace(' ', '') in compact):
                matches.append(job)
        jobs = matches
    # Stable sort preserves the existing newest-first order inside each group.
    return sorted(jobs, key=lambda job: not completed(job, db) if query else completed(job, db))
