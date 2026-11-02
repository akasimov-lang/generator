"""Shared stock of fresh roots. Previews read; explicit launches claim atomically."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select
from app import models
from app.domain_transfer_policy import domain_key, geo_key, banned_domains

LOCK = 'reglue-reserve-pool'


def observed_domains(site, state):
    domains = {domain_key(d) for d in [*(state.get('domains') or []),
        *(state.get('amp_domains') or []), state.get('canon'), state.get('amp')] if domain_key(d)}
    # A project's own root remains consumed when its current Main/list contains
    # only children. A child in an unrelated project does not claim its parent.
    own_root = domain_key(site.name)
    if own_root and any(domain.endswith('.' + own_root) for domain in domains):
        domains.add(own_root)
    return domains


def cached_state(site):
    state = site.network_state or {}
    return {**state, 'domains': list(dict.fromkeys([*(state.get('domains') or []),
        *(site.cache_domains or [])])), 'canon': site.cache_canon or state.get('canon')}


def reconcile_memberships(db, snapshots):
    """Record observed stock consumption in the caller's snapshot transaction."""
    owners = {}
    for site, state in snapshots:
        for key in observed_domains(site, state):
            owners.setdefault(key, {})[site.id] = (site, state)
    if not owners:
        return
    rows = db.scalars(select(models.ReglueReserveDomain).where(
        models.ReglueReserveDomain.domain.in_(owners)).order_by(models.ReglueReserveDomain.id)
        .with_for_update().execution_options(populate_existing=True))
    for row in rows:
        matches = owners[row.domain]
        site, state = matches.get(row.site_id) or matches[sorted(matches)[0]]
        # A pool launch records its own confirmed addition and preserves its receipt.
        if row.run_id and row.site_id == site.id:
            continue
        moved = row.site_id != site.id
        if moved:
            row.run_id = None
        row.status, row.site_id, row.error = 'assigned', site.id, None
        if row.assigned_at is None or moved:
            dates = state.get('domain_added_at') or {}
            observed = next((value for domain, value in dates.items() if domain_key(domain) == row.domain), None)
            try:
                row.assigned_at = datetime.fromisoformat(observed.replace('Z', '+00:00')) if observed else datetime.now(timezone.utc)
            except (ValueError, AttributeError):
                row.assigned_at = datetime.now(timezone.utc)


def permit_key(site_id, row_id):
    return 'stock-permit:' + str(uuid5(NAMESPACE_URL, f'reglue-stock:{site_id}:{row_id}'))


def normalize(value):
    value = value.strip().lower()
    parsed = urlsplit(value if '://' in value else '//' + value)
    if parsed.scheme not in ('', 'http', 'https') or parsed.username or parsed.password or parsed.port or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Укажите домен без пути, порта и параметров.')
    name = (parsed.hostname or '').rstrip('.').encode('idna').decode('ascii').removeprefix('www.')
    if len(name) > 253 or '.' not in name or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name):
        raise ValueError('Некорректное доменное имя.')
    if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part) for part in name.split('.')) or name.split('.')[-1].isdigit():
        raise ValueError('Некорректное доменное имя.')
    from app.domain_classification import registrable_root
    root = registrable_root(name)
    if root and root != name:
        raise ValueError('Добавьте корневой домен; поддомены создаются по настройкам переклея.')
    return name


def import_domains(db, text, kind, brand, username):
    from app.project_network import network_lock
    tokens = re.split(r'[\s,;]+', text.strip())
    if not text.strip() or len(tokens) > 5000:
        raise ValueError('Укажите от 1 до 5000 доменов.')
    added, duplicates, errors = [], [], []
    with network_lock(db, LOCK):
        existing = set(db.scalars(select(models.ReglueReserveDomain.domain)))
        memberships = {domain: site.name for site in db.scalars(select(models.Site).where(models.Site.is_active.is_(True)))
                       for domain in observed_domains(site, cached_state(site))}
        for token in tokens:
            try:
                domain = normalize(token)
                from app.domain_transfer_policy import blocked_transfer_zone
                if blocked_transfer_zone(domain):raise ValueError('Доменная зона запрещена для переклея: БАН.')
                if domain in existing:
                    duplicates.append(domain); continue
                if domain in memberships:
                    raise ValueError('Домен уже находится в сетке; в резерв добавляются свободные домены.')
                db.add(models.ReglueReserveDomain(domain=domain, domain_type=kind, brand=brand.strip() or None, added_by=username))
                existing.add(domain); added.append(domain)
            except (ValueError, UnicodeError) as error:
                errors.append({'domain': token, 'error': str(error)})
        db.commit()
    return {'added': added, 'duplicates': duplicates, 'errors': errors}


def require_unused(site, state, domain):
    used = [*(site.main_domain_history or []), state.get('canon'), state.get('prev')]
    if domain_key(domain) in {domain_key(d) for d in used if d}:
        raise ValueError('Выбранный домен уже использовался как Main в этой сетке.')


def require_available(db, row, target, state, *, run=None, assigned=False):
    from app.cross_reglue import brand_key, unique_membership
    if row is None or (run is None and row.status != 'available') or (run is not None and row.run_id != run.id):
        raise ValueError('Домен из базы резервов уже занят другим запуском. Подготовьте планы заново.')
    if row.brand and brand_key(row.brand) != brand_key(target.brand):
        raise ValueError('Резервный домен предназначен для другого бренда.')
    if row.domain_type == 'drop' and geo_key(target.cache_geo) == 'AZ':
        # Operator-recorded exception is bound to one explicitly authorized
        # project/domain/run, and cannot change automatic allocation for AZ.
        permit = db.get(models.AutoReglueConfig, permit_key(target.id, row.id))
        permitted_run = run.id if run else db.info.get('stock_permit_run_id')
        if not (permit and permitted_run and permit.value.get('run_id') == permitted_run
                and permit.value.get('domain') == row.domain and permit.value.get('site_id') == target.id
                and permit.value.get('authorized_by') and permit.value.get('reason')):
            raise ValueError('Дропы из базы резервов запрещены для GEO Азербайджан.')
    require_unused(target, state, row.domain)
    if banned_domains(db, target, [row.domain])[row.domain]:
        raise ValueError('Резервный домен отмечен БАН в GEO проекта.')
    unique_membership(db, row.domain, {target.id} if assigned else set())
    if not assigned and domain_key(row.domain) in {domain_key(d) for d in state['domains']}:
        raise ValueError('Резервный домен уже находится в принимающей сетке.')


def candidate(db, target, state, kinds, used=()):
    from app.cross_reglue import brand_key
    rows = list(db.scalars(select(models.ReglueReserveDomain).where(models.ReglueReserveDomain.status == 'available', models.ReglueReserveDomain.domain_type.in_(kinds)).order_by(models.ReglueReserveDomain.created_at, models.ReglueReserveDomain.id)))
    # Consume stock earmarked for this brand before general stock.
    rows.sort(key=lambda r: not (r.brand and brand_key(r.brand) == brand_key(target.brand)))
    for row in rows:
        if row.domain in used or row.domain in db.info.get('reglue_preview_domains', set()): continue
        try: require_available(db, row, target, state)
        except ValueError: continue
        return row
    return None


def make_plan(db, cfg, target, state, row, plans=(), slot=None):
    from app import cross_reglue as cross, auto_reglue as auto
    from app.mass_action_scope import stamp_plan
    plan = cross.make_plan(cfg, target, state, target, state, row.domain, mode='reserve_pool', db=db, plans=plans)
    plan.update(reserve_pool_id=row.id, local_target=True, source_project='База резервов',
                domain_type=row.domain_type, main_target_kind=row.domain_type,
                requested_target_kind=slot or row.domain_type, target_fallback=bool(slot and slot != row.domain_type),
                required_domain_type=row.domain_type, requires_newreg=False)
    if slot and slot != row.domain_type:
        plan['fallback_reason'] = 'Нет подходящего домена для заданной доли; выбран новорег из базы резервов.'
    if plan.get('replace_banned_reserve'):
        plan['fallback_reason'] = 'Резерв в БАН; выбран новый домен из базы резервов.'
    plan.pop('preview_token', None)
    plan['preview_token'] = auto.digest(plan)
    return stamp_plan(db, plan, state, target)


def validate_plan(db, target, state, plan, *, run=None, assigned=False):
    row = db.get(models.ReglueReserveDomain, plan['reserve_pool_id'])
    if row is None or row.domain != plan['new_main'] or row.domain_type != plan['domain_type']:
        raise ValueError('Запись базы резервов изменилась после предпросмотра.')
    require_available(db, row, target, state, run=run, assigned=assigned)
    return row


def claim(db, run):
    # Caller holds LOCK until the complete run/group has been committed.
    row = db.scalar(select(models.ReglueReserveDomain).where(models.ReglueReserveDomain.id == run.plan['reserve_pool_id']).with_for_update().execution_options(populate_existing=True))
    if row is None or row.status != 'available':
        raise ValueError('Резервный домен уже занят. Подготовьте планы заново.')
    row.status, row.site_id, row.run_id, row.error = 'reserved', run.site_id, run.id, None
    db.flush()


def mark_added(db, run, at):
    row = db.get(models.ReglueReserveDomain, run.plan['reserve_pool_id'])
    if row.run_id != run.id: raise ValueError('Домен зарезервирован другим запуском.')
    row.status = 'assigned'
    row.assigned_at = datetime.fromisoformat(at.replace('Z', '+00:00'))
    row.error = None
    db.commit()


def sync_result(db, run):
    row = db.get(models.ReglueReserveDomain, run.plan.get('reserve_pool_id'))
    if row and row.run_id == run.id:
        row.error = run.message if run.status in ('failed', 'partial', 'waiting') else None
        if run.status in ('failed', 'cancelled') and not row.assigned_at:
            row.status = 'error'
        db.commit()
