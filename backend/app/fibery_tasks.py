"""Read-only dashboard index of Fibery tasks created through PagePilot."""
import re
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app import models
from app.project_notifications import safe_text
from app.reglue_history import utc

TASK_URL = re.compile(r'https://hzhz\.fibery\.io/favorites/Alfasearch_Config/SEO_Tasks/(\d+)')


def project_number(value):
    match = re.search(r'#\s*(\d+)', value or '')
    return match.group(1) if match else None


def feed(db, user, *, query='', before=None, limit=50):
    allowed = user.get('allowed_site_ids')
    sites_query = select(models.Site).options(load_only(models.Site.id, models.Site.name,
        models.Site.fibery_name, models.Site.cache_canon))
    if allowed is not None:
        sites_query = sites_query.where(models.Site.id.in_(allowed))
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
        if allowed is not None and (site_id and site_id not in sites or not projects):
            return
        at = utc(task.get('verified_at')) or utc(at)
        row = {'id': number, 'number': number, 'title': safe_text(task.get('title') or
            task.get('Alfasearch Config/Name') or 'SEO-задача #' + number),
            'url': match.group(0), 'at': at.isoformat(), 'verified_at': at.isoformat(),
            'kind': kind, 'status': 'created', 'projects': [project(s) for s in projects],
            'fibery_project_url': 'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/' + number_project if number_project.isdigit() else None,
            'project_number': number_project}
        existing = tasks.get(number)
        if existing:
            # Several work reports may update one task. Keep its latest title,
            # earliest confirmation date and one row in the collection.
            first = min(existing['at'], row['at'])
            if existing['verified_at'] > row['verified_at']:
                row = existing
            row['at'] = first
        tasks[number] = row

    job = models.BackgroundJob
    jobs_query = select(job.id, job.status, job.error, job.created_at, job.finished_at,
        job.payload['site_id'].as_string().label('site_id'),
        job.payload['title'].as_string().label('title'),
        job.payload['due_at'].as_string().label('due_at'),
        job.result['task'].label('task'), job.result['verified_at'].as_string().label('verified_at')
    ).where(job.kind == 'fibery_reglue')
    if allowed is not None:
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

    # Older SEO work stored explicit receipts in per-project ledgers. Fetch only
    # the receipt, not the potentially large backups stored alongside it.
    config = models.AutoReglueConfig
    for task, at in db.execute(select(config.value['fibery_task'], config.updated_at).where(
            config.value['fibery_task']['url'].as_string().is_not(None))):
        add(task, at)

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
