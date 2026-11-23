"""Per-project opt-in for retargeting redirects during a Main change."""
from datetime import datetime, timezone
from sqlalchemy import select
from app import models

PREFIX = 'reglue-redirect-policy:'


def enabled(db, site_id):
    row = db.get(models.AutoReglueConfig, PREFIX + str(site_id))
    return bool(row and row.value.get('enabled') is True)


def save(db, site, value, actor):
    db.execute(select(models.Site.id).where(models.Site.id == site.id).with_for_update()).scalar_one()
    key = PREFIX + str(site.id)
    row = db.get(models.AutoReglueConfig, key)
    if row is None:
        row = models.AutoReglueConfig(key=key)
        db.add(row)
    row.value = {'enabled': bool(value), 'updated_by': actor,
                 'updated_at': datetime.now(timezone.utc).isoformat()}
    db.commit()
    return {'site_id': site.id, 'enabled': enabled(db, site.id)}
