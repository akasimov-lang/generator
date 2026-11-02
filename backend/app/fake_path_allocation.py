"""Unique reglue paths within a brand/GEO, including in-flight assignments."""
from contextlib import nullcontext
from types import SimpleNamespace
from sqlalchemy import select
from app import models
from app.domain_transfer_policy import geo_key
from app.fake_main import normalize_fake_path, next_fake_path
from app.site_brands import BRANDS, normalized


def group(site):
    brand = normalized(site.brand)
    for canonical, aliases in BRANDS.items():
        if brand in {normalized(canonical), *(normalized(alias) for alias in aliases)}:
            brand = normalized(canonical)
            break
    return brand, geo_key(site.cache_geo)


def group_lock(db, site):
    from app.project_network import network_lock
    brand, geo = group(site)
    return network_lock(db, 'fake-path-group:' + brand + ':' + geo) if brand and geo else nullcontext()


def paths(state):
    alternate = state.get('fake_main_settings') or state.get('alternate') or {}
    values = [state.get('fake_main_current'), alternate.get('currentFakeMain'),
              *state.get('fake_main_history', []), *state.get('fake_main_paths', []),
              *alternate.get('fakeMain', [])]
    result = set()
    for value in values:
        try:
            result.add(normalize_fake_path(value).casefold())
        except ValueError:
            continue
    return result


def occupied(db, site, plans=()):
    from app.auto_reglue import ACTIVE
    peers = {peer.id: peer for peer in db.scalars(select(models.Site).where(models.Site.is_active.is_(True))
             .execution_options(populate_existing=True))
             if peer.id != site.id and group(peer) == group(site)}
    used = set()
    for peer in peers.values():
        used.update(paths(peer.network_state or {}))
    for run in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.status.in_(ACTIVE))
                          .execution_options(populate_existing=True)):
        if run.site_id in peers:
            used.update(paths({'fake_main_current': run.plan.get('create_fake_main_path') or run.plan.get('fake_main_path')}))
    for plan in plans:
        if plan.get('site_id') in peers:
            used.update(paths({'fake_main_current': plan.get('create_fake_main_path') or plan.get('fake_main_path')}))
    for op in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id.in_(peers),
            models.NetworkOperation.action.in_(['create_fake_main', 'select_fake_main']),
            models.NetworkOperation.status.in_(['pending', 'unknown']))
            .execution_options(populate_existing=True)):
        used.update(paths(op.request_payload or {}))
    return used


def next_path(db, site, state, cfg, plans=()):
    snapshot = {**state, 'fake_main_history': [*state.get('fake_main_history', []), *occupied(db, site, [*db.info.get('canonical_allocation_plans', []), *plans])]}
    locale = SimpleNamespace(id=site.id, brand=site.brand, cache_geo=geo_key(site.cache_geo),
                             cache_language=site.cache_language or cfg.language)
    from app.naming_variants import allocation_index
    index = allocation_index([*db.info.get('canonical_allocation_plans', []), *plans], site.id)
    return next_fake_path(locale, snapshot, cfg, allocation_index=index)


def require_available(db, site, path, plans=()):
    if path and normalize_fake_path(path).casefold() in occupied(db, site, plans):
        raise ValueError(f'Внутряк {path} уже используется или зарезервирован в другой сетке этого бренда и GEO. Подготовьте новый план.')
