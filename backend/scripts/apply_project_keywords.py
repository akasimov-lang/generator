"""Apply the saved report plan only; existing keys and exact report membership are preserved."""
import sys
from datetime import datetime, timezone
from app import models
from app.db import SessionLocal
from app.generation_anchors import general, settings, parse_anchors, save_settings
from app.project_primary_keywords import additions
from app.maintenance_reports import upsert

with SessionLocal() as db:
    job = db.get(models.BackgroundJob, sys.argv[1])
    if not job or job.kind != 'maintenance_report':
        raise ValueError('Отчёт не найден')
    rows = list((job.result or {}).get('entries', []))
    # Persist the exact localized plan before any settings writes.
    for entry in rows:
        if entry.get('status') == 'completed':
            continue
        site = db.get(models.Site, entry['site_id'])
        keys = additions(site.cache_geo, site.cache_language)
        entry['plan'] = {'action': 'Добавить основные ключи проекта', 'add': keys,
                         'preserve_existing': True, 'planned_at': datetime.now(timezone.utc).isoformat()}
    upsert(db, job.id, job.payload['name'], job.payload['actor'], job.payload['site_ids'], rows)
    for entry in rows:
        if entry.get('status') == 'completed':
            continue
        site = db.get(models.Site, entry['site_id'])
        if not general(site) or site.project_status != 'mass_actions' or site.hidden_from_projects:
            entry.update(status='skipped', message='Проект больше не соответствует фильтру.')
        else:
            before = settings(db, site)['anchors']
            after = parse_anchors([*before, *entry['plan']['add']])
            save_settings(db, site, after)
            confirmed = settings(db, site)['anchors']
            if confirmed != after:
                raise ValueError('Не подтверждено сохранение ' + site.name)
            entry.update(status='completed', before_apply={'anchors': before}, after={'anchors': confirmed},
                         added=[key for key in after if key.casefold() not in {s.casefold() for s in before}],
                         confirmed_at=datetime.now(timezone.utc).isoformat(),
                         message='Ключи сохранены и подтверждены чтением настроек проекта.')
        upsert(db, job.id, job.payload['name'], job.payload['actor'], job.payload['site_ids'], [entry])
    upsert(db, job.id, job.payload['name'], job.payload['actor'], job.payload['site_ids'], rows, status='completed')
    print({'report': job.id, 'completed': sum(r['status'] == 'completed' for r in rows), 'skipped': sum(r['status'] == 'skipped' for r in rows)})
