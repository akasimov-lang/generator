"""Read-only dashboard index of Fibery tasks created through PagePilot."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import String, cast, select
from sqlalchemy.orm import load_only
from sqlalchemy.exc import IntegrityError

from app import models
from app.project_notifications import safe_text
from app.reglue_history import utc

TASK_URL = re.compile(r'https://hzhz\.fibery\.io/favorites/Alfasearch_Config/SEO_Tasks/(\d+)')
INDEX_KEY = 'fibery-task-index'
RECEIPT_PREFIX = 'fibery-task-receipt:'


def refresh_legacy_receipts(db, *, now=None, force=False):
    """Index old work ledgers off the request path; never copy their backups."""
    now = utc(now) or datetime.now(timezone.utc)
    if db.get(models.AutoReglueConfig, INDEX_KEY) is None:
        try:
            with db.begin_nested():
                db.add(models.AutoReglueConfig(key=INDEX_KEY, value={}))
                db.flush()
        except IntegrityError:
            pass
    state = db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key == INDEX_KEY)
                      .with_for_update().execution_options(populate_existing=True))
    last = utc((state.value or {}).get('at'))
    if last and now < last + timedelta(minutes=1) and not force:
        db.commit()
        return 0
    full_at = utc((state.value or {}).get('full_at'))
    full = force or not full_at or now >= full_at + timedelta(days=1)
    config = models.AutoReglueConfig
    query = select(config.key, config.value, config.updated_at).where(
        config.key != INDEX_KEY, ~config.key.startswith(RECEIPT_PREFIX),
        cast(config.value, String).contains('"fibery_task"'))
    if not full and last:
        query = query.where(config.updated_at >= last - timedelta(minutes=5))
    count = 0
    for key, value, at in db.execute(query):
        task = value.get('fibery_task') if isinstance(value, dict) else None
        if not isinstance(task, dict) or not TASK_URL.fullmatch(str(task.get('url') or '')):
            continue
        receipt = {k: task[k] for k in ('url', 'title', 'public_id', 'project_number', 'task_id',
            'fibery/public-id', 'fibery/id', 'Alfasearch Config/Name', 'verified_at', 'created_at', 'fibery/creation-date') if k in task}
        project = task.get('Alfasearch Config/SEO Project')
        if isinstance(project, dict):
            receipt['Alfasearch Config/SEO Project'] = {k: project[k] for k in ('fibery/id', 'fibery/public-id') if k in project}
        id_ = RECEIPT_PREFIX + str(uuid5(NAMESPACE_URL, key))
        target = db.get(models.AutoReglueConfig, id_)
        if target is None:
            target = models.AutoReglueConfig(key=id_, value={})
            db.add(target)
        target.value = {'task': receipt, 'at': utc(at).isoformat()}
        count += 1
    state.value = {'at': now.isoformat(), 'full_at': now.isoformat() if full else full_at.isoformat()}
    db.commit()
    return count


def project_number(value):
    match = re.search(r'#\s*(\d+)', value or '')
    return match.group(1) if match else None


def feed(db, user, *, query='', before=None, limit=50, site_id=None):
    allowed = user.get('allowed_site_ids')
    sites_query = select(models.Site).options(load_only(models.Site.id, models.Site.name,
        models.Site.fibery_name, models.Site.cache_canon))
    if allowed is not None:
        sites_query = sites_query.where(models.Site.id.in_(allowed))
    if site_id is not None:
        sites_query = sites_query.where(models.Site.id == site_id)
    sites = {s.id: s for s in db.scalars(sites_query)}
    by_number = {}
    for site in sites.values():
        number = project_number(site.fibery_name)
        if number:
            by_number.setdefault(number, []).append(site)

    def project(site):
        return {'id': site.id, 'name': site.name, 'fibery_name': site.fibery_name,
                'main': site.cache_canon, 'url': '/project-network/' + quote(site.name, safe='') + '/'}

    tasks, pending = {}, []

    def add(task, at, *, site_id=None, kind='seo'):
        if not isinstance(task, dict):
            return
        match = TASK_URL.fullmatch(str(task.get('url') or ''))
        if not match:
            return
        number = str(task.get('public_id') or task.get('fibery/public-id') or match.group(1))
        if number != match.group(1):
            return
        number_project = str(task.get('project_number') or
            (task.get('Alfasearch Config/SEO Project') or {}).get('fibery/public-id') or '')
        projects = [sites[site_id]] if site_id in sites else by_number.get(number_project, []) if not site_id else []
        if (allowed is not None or project_filter is not None) and (site_id and site_id not in sites or not projects):
            return
        at = utc(task.get('verified_at')) or utc(at)
        created_at = utc(task.get('created_at') or task.get('fibery/creation-date'))
        row = {'id': number, 'number': number, 'title': safe_text(task.get('title') or
            task.get('Alfasearch Config/Name') or 'SEO-задача #' + number),
            'url': match.group(0), 'at': at.isoformat(), 'verified_at': at.isoformat(),
            'created_at': created_at.isoformat() if created_at else None,
            'kind': kind, 'status': 'created', 'projects': [project(s) for s in projects],
            'fibery_project_url': 'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/' + number_project if number_project.isdigit() else None,
            'project_number': number_project}
        existing = tasks.get(number)
        if existing:
            # Several work reports may update one task. Keep its latest title,
            # earliest confirmation date and one row in the collection.
            first = min(existing['at'], row['at'])
            created = row['created_at'] or existing['created_at']
            if existing['verified_at'] > row['verified_at']:
                row = existing
            row['at'] = first
            row['created_at'] = created
        tasks[number] = row

    project_filter = site_id
    job = models.BackgroundJob
    jobs_query = select(job.id, job.status, job.error, job.created_at, job.finished_at,
        job.payload['site_id'].as_string().label('site_id'),
        job.payload['title'].as_string().label('title'),
        job.payload['due_at'].as_string().label('due_at'),
        job.result['task'].label('task'), job.result['verified_at'].as_string().label('verified_at')
    ).where(job.kind == 'fibery_reglue')
    if allowed is not None or project_filter is not None:
        jobs_query = jobs_query.where(job.payload['site_id'].as_string().in_(sites))
    for row in db.execute(jobs_query).mappings():
        if row['task']:
            add(row['task'], row['verified_at'] or row['finished_at'] or row['created_at'], site_id=row['site_id'], kind='reglue')
        elif row['status'] != 'completed':
            site = sites.get(row['site_id'])
            pending.append({'id': row['id'], 'title': safe_text(row['title'] or 'Переклей'),
                'status': 'error' if row['error'] or row['status'] == 'failed' else 'running' if row['status'] == 'running' else 'collecting',
                'error': safe_text(row['error']), 'at': utc(row['created_at']).isoformat(),
                'due_at': row['due_at'], 'projects': [project(site)] if site else []})

    # The scheduler indexes historical ledgers separately. Dashboard requests
    # only read compact receipts, never scan or decode article backups.
    config = models.AutoReglueConfig
    for value in db.scalars(select(config.value).where(config.key.startswith(RECEIPT_PREFIX))):
        if isinstance(value, dict):
            add(value.get('task'), value.get('at'))

    search = query.strip().casefold()
    def matches(row):
        values = [row['title'], '#' + row.get('number', ''), '#' + row.get('project_number', '')]
        for p in row['projects']:
            values.extend([p['name'], p['fibery_name'] or '', p['main'] or ''])
        return not search or search in ' '.join(values).casefold()

    rows = sorted((r for r in tasks.values() if matches(r)), key=lambda r: (r['at'], r['id']), reverse=True)
    total = len(rows)
    if before:
        rows = [r for r in rows if r['at'] + '|' + r['id'] < before]
    selected = rows[:limit]
    return {'total': total, 'items': selected,
            'pending': sorted((r for r in pending if matches(r)), key=lambda r: (r['at'], r['id']), reverse=True),
            'next_before': selected[-1]['at'] + '|' + selected[-1]['id'] if len(rows) > limit else None,
            'timezone': 'Europe/Moscow'}
