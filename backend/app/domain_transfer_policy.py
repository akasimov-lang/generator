"""Persistent domain/GEO bans and calendar-month transfer eligibility."""
import calendar
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from app import models
from app.network_state import domain_name


def domain_key(domain):
    return domain_name(domain).removeprefix('www.')


def geo_key(geo):
    return (geo or '').strip().replace('_', '-').split('-')[-1].upper()


def policy_key(domain):
    return 'domain-policy:' + hashlib.sha256(domain_key(domain).encode()).hexdigest()


def banned_domains(db, site, domains):
    names = list(domains)
    keys = {policy_key(d): d for d in names}
    rows = db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.in_(keys))).all()
    banned = {row.key for row in rows if geo_key(site.cache_geo) in row.value.get('banned_geos', [])}
    return {domain: policy_key(domain) in banned for domain in names}


def set_ban(db, site, domain, checked, actor):
    from app.project_network import network_lock
    geo = geo_key(site.cache_geo)
    if len(geo) != 2 or not geo.isalpha():
        raise ValueError('Для отметки БАН необходимо указать GEO проекта.')
    key = policy_key(domain)
    with network_lock(db, key):
        row = db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key == key).with_for_update())
        if row is None:
            row = models.AutoReglueConfig(key=key, value={})
            db.add(row)
        value = dict(row.value)
        geos = set(value.get('banned_geos', []))
        if checked:
            geos.add(geo)
        else:
            geos.discard(geo)
        value.update(domain=domain_key(domain), banned_geos=sorted(geos))
        value['edits'] = [*value.get('edits', []), {'geo': geo, 'banned': checked, 'actor': actor, 'at': datetime.now(timezone.utc).isoformat()}]
        row.value = value
        db.commit()


def next_transfer_at(added_at):
    if not added_at:
        return None
    added = datetime.fromisoformat(added_at.replace('Z', '+00:00')) if isinstance(added_at, str) else added_at
    if added.tzinfo is None:
        added = added.replace(tzinfo=timezone.utc)
    year, month = (added.year + 1, 1) if added.month == 12 else (added.year, added.month + 1)
    return added.replace(year=year, month=month, day=min(added.day, calendar.monthrange(year, month)[1]))


def require_transfer_allowed(db, site, domain, now=None):
    """Unknown date is allowed; all other transfer guards remain mandatory."""
    if banned_domains(db, site, [domain])[domain]:
        raise ValueError('Домен отмечен БАН в GEO проекта и не может переноситься.')
    # Check all retained membership histories: extraction cannot reset cooldown.
    latest = None
    for state in db.scalars(select(models.Site.network_state)):
        for name, value in (state or {}).get('domain_added_at', {}).items():
            if domain_key(name) != domain_key(domain) or not value:
                continue
            deadline = next_transfer_at(value)
            latest = max(latest, deadline) if latest else deadline
    if latest and (now or datetime.now(timezone.utc)) < latest:
        raise ValueError('Повторный перенос разрешён с ' + latest.isoformat())
    return latest
