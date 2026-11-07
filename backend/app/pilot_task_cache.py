"""Persistent, permission-scoped list snapshots; no remote project reads on cache hits."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from app import models
from app.project_network import network_lock, NetworkConflict

PREFIX = 'pilot-tasks:'
VERSION = 1
KINDS = ('auto_pilot_preview', 'mass_reglue_list', 'maintenance_report', 'pilot_internal_pages',
         'pilot_content_publication', 'pilot_text', 'pilot_row_replan')


def key(user, offset, limit, query):
    scope = {'user': user['username'], 'allowed': sorted(user['allowed_site_ids']) if user.get('allowed_site_ids') is not None else None,
             'offset': offset, 'limit': limit, 'query': query.strip(), 'version': VERSION}
    return PREFIX + hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()


def revision(db, *, search=False):
    # A single lightweight query reads modification markers, never large JSON plans.
    tables = [(models.BackgroundJob, models.BackgroundJob.kind.in_(KINDS)),
              (models.AutoReglueRun, None), (models.ContentItem, None), (models.GenerationTask, None),
              (models.NetworkOperation, None),
              (models.AutoReglueConfig, or_(models.AutoReglueConfig.key.startswith('pilot-cancel:'),
                 models.AutoReglueConfig.key.startswith('pilot-report-hidden:'),
                 models.AutoReglueConfig.key.startswith('pilot-replan:'),
                 models.AutoReglueConfig.key.startswith('pilot-report-id:')))]
    columns = []
    for table, condition in tables:
        for value in (func.count(), func.max(table.updated_at)):
            query = select(value).select_from(table)
            if condition is not None: query = query.where(condition)
            columns.append(query.scalar_subquery())
    values = list(db.execute(select(*columns)).one())
    if search:
        # Site cache heartbeat/title refreshes do not change this list. Search
        # depends only on names, brand/GEO and domain membership, not updated_at.
        rows = db.execute(select(models.Site.id, models.Site.name, models.Site.brand,
            models.Site.cache_geo, models.Site.cache_canon, models.Site.cache_domains).order_by(models.Site.id))
        values.append([[*row[:5], sorted(str(d if isinstance(d, str) else d.get('domain', ''))
            for d in (row[5] or []) if isinstance(d, (str, dict)))] for row in rows])
    return hashlib.sha256(json.dumps(values, default=str).encode()).hexdigest()


def tasks(db, user, offset=0, limit=50, *, q='', refresh=False):
    from app import auto_pilot
    cache_key = key(user, offset, limit, q)
    stamp = revision(db, search=bool(q.strip()))
    cached = db.get(models.AutoReglueConfig, cache_key)
    value = (cached.value or {}) if cached else {}
    if not refresh and value.get('revision') == stamp:
        return deepcopy(value['data'])
    try:
        with network_lock(db, cache_key):
            if cached:
                db.refresh(cached)
                if not refresh and cached.value.get('revision') == stamp:
                    return deepcopy(cached.value['data'])
            data = auto_pilot.tasks(db, user, offset, limit, q=q)
            # Cache construction never commits unrelated caller changes.
            from sqlalchemy.orm import Session
            try:
                with Session(bind=db.get_bind()) as storage:
                    record = storage.get(models.AutoReglueConfig, cache_key)
                    payload = {'revision': stamp, 'data': jsonable_encoder(data), 'saved_at': datetime.now(timezone.utc).isoformat()}
                    if record: record.value = payload
                    else: storage.add(models.AutoReglueConfig(key=cache_key, value=payload))
                    storage.commit()
            except SQLAlchemyError as error:
                logging.getLogger(__name__).warning("Plan list cache write failed: %s", type(error).__name__)
            return data
    except NetworkConflict:
        # Another request is building the same view. Keep its last saved snapshot.
        if cached: return deepcopy(cached.value['data'])
        return auto_pilot.tasks(db, user, offset, limit, q=q)
