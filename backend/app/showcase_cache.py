"""Persist confirmed homepage showcase counts; list views never contact Webdev."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select
from app import models

PREFIX = 'showcase-cache:'
KIND = 'showcase_cache_refresh'


def summary(project):
    from app.showcase_editor import view
    from app.showcase_brands import name_key
    # Aggregate cache omits templates. An omitted layout is not an empty layout.
    if not isinstance(project.get('layout'), str) or not isinstance(project.get('shortcodes'), list):
        return None
    data = project.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('pages'), list):
        return None
    homes = [p for p in data['pages'] if isinstance(p, dict) and not str(p.get('slug') or '').strip('/')]
    if len(homes) != 1 or not isinstance((homes[0].get('content') or {}).get('blocks'), list):
        return None
    result = view(project)
    management = result['management']
    if not management['complete']:
        return None
    if any(s['kind'] == 'native' for s in management['sources']) and not isinstance(data.get('casinos'), (dict, list)):
        return None
    external = any(s['kind'] == 'external' for s in management['sources'])
    brands = list({name_key(row['brand']): row['brand'] for row in result['rows']}.values())
    return {'count': None if external else len(brands), 'brands': brands,
            'presence': 'external' if external else 'connected' if brands else 'none',
            'sources': [{k: s[k] for k in ('kind', 'storage', 'location')} for s in management['sources']]}


def preload(db, sites):
    sites = list(sites)
    values = {r.key[len(PREFIX):]: r.value for r in db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.in_([PREFIX + s.id for s in sites])))} if sites else {}
    cached = db.info.setdefault('showcase_summaries', {})
    for site in sites:
        value = deepcopy(values.get(site.id))
        cached[site.id] = value
        site.cache_showcase = value


def cached(db, site):
    if site.id not in db.info.get('showcase_summaries', {}):
        preload(db, [site])
    return deepcopy(db.info['showcase_summaries'][site.id])


def enqueue(db, site):
    job_id = str(uuid5(NAMESPACE_URL, PREFIX + site.id))
    job = db.get(models.BackgroundJob, job_id)
    if job and job.status in {'queued', 'running'}:
        return
    if job and job.status == 'failed' and job.finished_at:
        finished = job.finished_at.replace(tzinfo=job.finished_at.tzinfo or timezone.utc)
        if datetime.now(timezone.utc) - finished < timedelta(minutes=15):
            return  # Repeated cache/list refreshes must not hammer an unavailable server.
    if job is None:
        job = models.BackgroundJob(id=job_id, kind=KIND, payload={'site_id': site.id})
        db.add(job)
    job.status = 'queued'
    job.error = job.started_at = job.finished_at = job.dispatched_at = None
    job.result = {}


def capture(db, site, project, *, source='cache', at=None, queue_missing=True):
    if not site.id:
        db.flush()
    value = summary(project)
    if value is None:
        if queue_missing:
            enqueue(db, site)
        return False
    record = db.get(models.AutoReglueConfig, PREFIX + site.id)
    # Keep the content-change timestamp stable on identical refreshes.
    previous = (record.value or {}) if record else {}
    changed = any(previous.get(k) != v for k, v in value.items())
    now = (at or datetime.now(timezone.utc)).isoformat()
    value.update(checked_at=now, changed_at=now if changed else previous.get('changed_at', now), source=source)
    if record is None:
        record = models.AutoReglueConfig(key=PREFIX + site.id, value=value)
        db.add(record)
    else:
        record.value = value
    db.info.setdefault('showcase_summaries', {})[site.id] = deepcopy(value)
    site.cache_showcase = deepcopy(value)
    return True


def execute(db, job):
    from app.project_network import Remote
    site = db.get(models.Site, job.payload['site_id'])
    if site is None or not site.is_active:
        return {'status': 'skipped'}
    with Remote(db, site) as remote:
        project = remote.project()
    if not capture(db, site, project, source='webdev', queue_missing=False):
        raise ValueError('Неполные данные витрины. Последнее подтверждённое значение сохранено.')
    return {'status': 'confirmed', 'count': site.cache_showcase['count']}
