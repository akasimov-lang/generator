"""Confirmed field changes, committed with the saved value or Webdev receipt."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from app import models
from app.network_state import domain_name


def record(db, site, field, before, after, actor, *, page_path=None, edit_id=None):
    if before == after:
        return
    identity = str(uuid5(NAMESPACE_URL, f'pagepilot:title-history:{edit_id}')) if edit_id else str(uuid4())
    if db.get(models.NetworkOperation, identity):
        return
    now = datetime.now(timezone.utc)
    domain = domain_name(site.cache_canon) or domain_name(site.name)
    db.add(models.NetworkOperation(
        id=identity, site_id=site.id, action=field, status='confirmed', initiator=actor,
        created_at=now, updated_at=now,
        message='Значение поля GSC сохранено в PagePilot.' if field == 'gsc' else 'Изменение Title подтверждено в Webdev.',
        request_payload={'confirmed_at': now.isoformat(), 'field_change': {
            'before': before, 'after': after, 'domain': domain, 'page_path': page_path,
        }},
    ))
