"""Remove local Webdev projects only after explicit remote absence, retaining an archive."""
from datetime import datetime, timezone
import json
from urllib.parse import quote

import httpx
from sqlalchemy import select, or_, and_, delete

from app import models
from app.db import Base
from app.core.config import get_settings
from app.webdev import webdev_origin_headers


def excluded_project_names(db):
    """Manual removals stay out of imports; ordinary inventory cleanup may recover."""
    archives = db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.startswith('removed-project:')))
    return {str(row.value.get('project') or '').strip().lower().rstrip('.')
            for row in archives if (row.value.get('evidence') or {}).get('exclude_from_import')}


def archive_and_delete(db, site, evidence):
    """Follow foreign keys, but never delete another project's shared work."""
    tables = Base.metadata.sorted_tables
    selected = {'sites': [dict(db.execute(select(models.Site.__table__).where(models.Site.id == site.id)).mappings().one())]}
    changed = True
    while changed:
        changed = False
        for table in tables:
            if table.name == 'sites':
                continue
            predicates = []
            for column in table.c:
                for fk in column.foreign_keys:
                    parents = selected.get(fk.column.table.name, [])
                    values = {row[fk.column.name] for row in parents if row[fk.column.name] is not None}
                    if values:
                        predicates.append(column.in_(values))
            if not predicates:
                continue
            rows = [dict(r) for r in db.execute(select(table).where(or_(*predicates))).mappings()]
            if any('site_id' in row and row['site_id'] not in {None, site.id} for row in rows):
                raise ValueError('Есть общие данные другого проекта; удаление отложено.')
            if len(rows) != len(selected.get(table.name, [])):
                selected[table.name] = rows
                changed = True
    # Persist all rows before deleting the first one. Reports have their own durable snapshots.
    value = json.loads(json.dumps({'project': site.name, 'site_id': site.id,
        'removed_at': datetime.now(timezone.utc).isoformat(), 'evidence': evidence, 'tables': selected}, default=str))
    key = 'removed-project:' + site.id
    row = db.get(models.AutoReglueConfig, key)
    if row:
        row.value = value
    else:
        db.add(models.AutoReglueConfig(key=key, value=value))
    db.flush()
    for user in db.scalars(select(models.User)):
        if site.id in (user.favorite_site_ids or []):
            user.favorite_site_ids = [sid for sid in user.favorite_site_ids if sid != site.id]
    # Self references must be detached before removing their owning rows.
    for table in reversed(tables):
        rows = selected.get(table.name, [])
        if not rows:
            continue
        predicate = or_(*(and_(*(column == row[column.name] for column in table.primary_key)) for row in rows))
        own_refs = {column.name: None for column in table.c if column.nullable
                    and any(fk.column.table.name == table.name for fk in column.foreign_keys)}
        if own_refs:
            db.execute(table.update().where(predicate).values(**own_refs))
        db.execute(delete(table).where(predicate))
    db.commit()
    db.expire_all()
    return value['project']


def prune_deleted_projects(db, projects, inventories, failures, *, actor='system'):
    names = {str(p.get('name') or '').strip() for p in projects}
    settings = get_settings()
    removed, deferred = [], {}
    candidates = [s for s in db.scalars(select(models.Site)) if s.external_project_id and s.cache_server_ip and s.name not in names]
    if not candidates:
        return {'removed_projects': [], 'deferred_projects': {}}
    with httpx.Client(timeout=25) as client:
        login = client.post(settings.project_cache_url.rstrip('/') + '/auth/login',
            json={'username': settings.project_cache_username, 'pass': settings.project_cache_password},
            headers=webdev_origin_headers(settings))
        login.raise_for_status()
        token = login.json().get('token')
        if not token:
            raise ValueError('Webdev не вернул токен для проверки удалённых проектов.')
        for site in candidates:
            servers = {site.cache_server_ip, *(sid for sid, ns in inventories.items() if site.name in ns)}
            if any(sid not in inventories or sid in failures for sid in servers):
                deferred[site.name] = 'Не подтверждён полный список сервера проекта.'
                continue
            evidence = []
            try:
                for server in sorted(servers):
                    response = client.get(f'https://{server}.{settings.alfan_url.strip().strip("/")}/projects/one/{quote(site.name, safe="")}',
                                          headers={'Authorization': 'Bearer ' + token})
                    absent_from_lists = not any(site.name in ns for ns in inventories.values())
                    # Webdev returns Forbidden for deleted names too. Accept this only
                    # for an already inactive local row absent from every successful
                    # server inventory and the freshly fetched complete central cache.
                    retired = response.status_code == 403 and not site.is_active and absent_from_lists
                    if response.status_code != 404 and not retired:
                        raise ValueError(f'Отсутствие не подтверждено: {server} HTTP {response.status_code}.')
                    evidence.append({'server': server, 'status': response.status_code,
                                     'absent_from_server_inventories': absent_from_lists})
                from app.auto_reglue import active_run
                if active_run(db, site.id):
                    raise ValueError('Есть незавершённый перенос доменов.')
                from app.project_network import network_lock
                with network_lock(db, site.id):
                    removed.append(archive_and_delete(db, site, {'actor': actor, 'absent_from_full_cache': True, 'direct_checks': evidence}))
            except (ValueError, httpx.HTTPError) as error:
                db.rollback()
                deferred[site.name] = str(error)
    return {'removed_projects': removed, 'deferred_projects': deferred}
