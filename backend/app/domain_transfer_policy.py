"""Persistent domain/GEO bans and calendar-month transfer eligibility."""
import calendar
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from app import models
from app.network_state import domain_name, is_project_identity


def domain_key(domain):
    return domain_name(domain).removeprefix('www.')


def geo_key(geo):
    return (geo or '').strip().replace('_', '-').split('-')[-1].upper()


def policy_key(domain):
    return 'domain-policy:' + hashlib.sha256(domain_key(domain).encode()).hexdigest()


def blocked_transfer_zone(domain):
    name = domain_key(domain).rstrip('.')
    return name == 'it.com' or name.endswith('.it.com') or name.endswith('.space')


def banned_domains(db, site, domains):
    names = list(domains)
    keys = {policy_key(d): d for d in names}
    rows = db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.in_(keys))).all()
    banned = {row.key for row in rows if geo_key(site.cache_geo) in row.value.get('banned_geos', [])}
    return {domain: is_project_identity(site, domain) or blocked_transfer_zone(domain) or policy_key(domain) in banned for domain in names}


def set_ban(db, site, domain, checked, actor):
    from app.project_network import network_lock
    if not checked and is_project_identity(site, domain):
        raise ValueError('Домен является именем проекта Webdev. Защитные отметки снимать нельзя.')
    if not checked and blocked_transfer_zone(domain):
        raise ValueError('Для этой доменной зоны установлен общий БАН на переклей и перенос между сетками.')
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


def main_pin_owners(db, domains):
    """Independent of editable Main-history flags and GEO bans."""
    names = {domain_key(domain) for domain in domains}
    names.discard("")
    owners = {domain: set() for domain in names}
    if not names:
        return owners
    records = db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.in_([policy_key(domain) for domain in names])))
    for row in records:
        key = domain_key(row.value.get("domain", ""))
        if key in owners:
            owners[key].update(row.value.get("main_pins", {}))
    # This integrity check spans owners outside the caller's project grants.
    # Use only internal ownership data; no other project's details are returned.
    sites = models.Site.__table__.c
    for site_id, canon, status, state in db.execute(select(sites.id, sites.cache_canon,
                                                        sites.project_status, sites.network_state)):
        protected = list((state or {}).get("protected_main_domains", []))
        if status == "mass_actions" and canon:
            protected.append(canon)
        for domain in protected:
            key = domain_key(domain)
            if key in owners:
                owners[key].add(site_id)
    return owners


def require_main_destination(db, site, domains):
    for domain, owners in main_pin_owners(db, domains).items():
        if owners and site.id not in owners:
            raise ValueError(f"Домен {domain} закреплён как Main с начала массового переклея. Перенос в другую сетку запрещён.")


def initialize_main_baseline(db, baseline):
    """Import the original read-only snapshot once, without changing live networks."""
    from app.project_network import network_lock
    for entry in baseline['projects']:
        domain = domain_key(entry['domain'])
        if not domain:
            continue
        with network_lock(db, policy_key(domain)):
            row = db.scalar(select(models.AutoReglueConfig).where(
                models.AutoReglueConfig.key == policy_key(domain)).with_for_update())
            if row is None:
                row = models.AutoReglueConfig(key=policy_key(domain), value={})
                db.add(row)
            value = dict(row.value)
            pins = dict(value.get('main_pins') or {})
            pins.setdefault(entry['site_id'], {'project': entry['project'], 'captured_at': baseline['captured_at'],
                                               'source': baseline['source']})
            row.value = {**value, 'domain': domain, 'main_pins': pins}
            db.flush()
    db.commit()


def require_non_project_domain(db, domain):
    # Project names are immutable transfer exclusions, across all project grants.
    names = db.scalars(select(models.Site.__table__.c.name))
    if any(domain_key(name) == domain_key(domain) for name in names):
        raise ValueError('Домен является именем проекта Webdev и не может переноситься между сетками.')


def record_transfer_cooldown(db, domain, added_at, reglued_at):
    # Caller holds the domain policy lock for the complete transfer phase.
    key = policy_key(domain)
    row = db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key == key).with_for_update())
    if row is None:
        row = models.AutoReglueConfig(key=key, value={}); db.add(row)
    value = dict(row.value)
    deadline = max(filter(None, (next_transfer_at(added_at), next_transfer_at(reglued_at))))
    previous = value.get('transfer_not_before')
    if previous:
        deadline = max(deadline, datetime.fromisoformat(previous))
    row.value = {**value, 'domain': domain_key(domain), 'last_added_at': added_at,
                 'last_reglued_at': reglued_at or value.get('last_reglued_at'), 'transfer_not_before': deadline.isoformat()}
    db.flush()
    return deadline.isoformat()

def require_transfer_allowed(db, site, domain, now=None, *, ignore_cooldown=False):
    """Unknown date is allowed; all other transfer guards remain mandatory."""
    require_non_project_domain(db, domain)
    if main_pin_owners(db, [domain]).get(domain_key(domain)):
        raise ValueError('Main закреплён с начала массового переклея и не может переноситься между сетками.')
    if banned_domains(db, site, [domain])[domain]:
        raise ValueError('Домен отмечен БАН в GEO проекта и не может переноситься.')
    if ignore_cooldown:
        return None  # Only a verified inverse operation may bypass its own new membership date.
    # Membership/import dates do not lock ordinary roots. Only a current Main
    # retains the calendar-month rule; Main ownership protection above also applies.
    columns = models.Site.__table__.c
    current_mains = db.scalars(select(columns.cache_canon).where(columns.is_active.is_(True)))
    if domain_key(domain) not in {domain_key(canon) for canon in current_mains}:
        return None
    # Check all retained membership histories: extraction cannot reset cooldown.
    policy = db.get(models.AutoReglueConfig, policy_key(domain))
    latest = datetime.fromisoformat(policy.value['transfer_not_before']) if policy and policy.value.get('transfer_not_before') else None
    for state in db.scalars(select(models.Site.__table__.c.network_state)):
        for name, value in (state or {}).get('domain_added_at', {}).items():
            if domain_key(name) != domain_key(domain) or not value:
                continue
            deadline = next_transfer_at(value)
            latest = max(latest, deadline) if latest else deadline
    if latest and (now or datetime.now(timezone.utc)) < latest:
        raise ValueError('Повторный перенос разрешён с ' + latest.isoformat())
    return latest
