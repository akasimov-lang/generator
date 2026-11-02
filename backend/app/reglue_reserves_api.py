"""Reserve pool inventory. Assigned project details respect project access."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models, reglue_reserves as pool
from app.db import get_db
from app.security import AuthUser
from app.project_network import network_lock

router = APIRouter(prefix='/reserves', tags=['reglue-reserves'])


class ImportRequest(BaseModel):
    domains: str = Field(min_length=1, max_length=1500000)
    domain_type: Literal['drop', 'newreg'] = 'drop'
    brand: str = Field(default='', max_length=160)


class BrandRequest(BaseModel):
    brand: str = Field(default='', max_length=160)


@router.get('')
def inventory(user: AuthUser, db: Session = Depends(get_db)):
    sites = {s.id: s for s in db.scalars(select(models.Site))}
    pool.reconcile_memberships(db, [(s, pool.cached_state(s)) for s in sites.values() if s.is_active])
    # The response below needs this same local snapshot. Expiring it at commit
    # caused another full Site query for every project when building the brands.
    expire = db.expire_on_commit
    try:
        db.expire_on_commit = False
        db.commit()
    finally:
        db.expire_on_commit = expire
    rows = list(db.scalars(select(models.ReglueReserveDomain).order_by(
        models.ReglueReserveDomain.created_at.desc(), models.ReglueReserveDomain.id)
        .execution_options(populate_existing=True)))
    allowed = user.get('allowed_site_ids')
    from app.domain_transfer_policy import blocked_transfer_zone
    items = []
    for row in rows:
        visible = not row.site_id or allowed is None or row.site_id in allowed
        site = sites.get(row.site_id) if visible else None
        run = db.get(models.AutoReglueRun, row.run_id) if visible and row.run_id else None
        error = (run.message if run and run.status in ('failed', 'waiting', 'partial') else row.error) if visible else None
        items.append(dict(id=row.id, domain=row.domain, domain_type=row.domain_type, brand=row.brand,
            status='banned' if blocked_transfer_zone(row.domain) else row.status, created_at=row.created_at, assigned_at=row.assigned_at,
            project=site.name if site else None, fibery_name=site.fibery_name if site else None,
            membership_checked_at=site.cache_synced_at if site else None,
            error=error, run_status=run.status if run else None,
            project_restricted=bool(row.site_id and not visible)))
    from app.reglue_reserve_refresh import latest
    return dict(items=items, total=len(rows), available=sum(r.status == 'available' and not blocked_transfer_zone(r.domain) for r in rows),
                brands=sorted({s.brand for s in sites.values() if s.brand}), refresh=latest(db, user))


class RefreshRequest(BaseModel):
    request_id: UUID


@router.post('/refresh', status_code=202)
def refresh(payload: RefreshRequest, user: AuthUser, db: Session = Depends(get_db)):
    from app import reglue_reserve_refresh
    return reglue_reserve_refresh.view(reglue_reserve_refresh.request(db, payload.request_id, user))


@router.get('/refresh/{job_id}')
def refresh_status(job_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    from app import reglue_reserve_refresh
    return reglue_reserve_refresh.view(reglue_reserve_refresh.authorized(db, job_id, user))


@router.post('')
def add(payload: ImportRequest, user: AuthUser, db: Session = Depends(get_db)):
    try:
        return pool.import_domains(db, payload.domains, payload.domain_type, payload.brand, user['username'])
    except ValueError as error: raise HTTPException(400, str(error)) from error


@router.patch('/{reserve_id}')
def brand(reserve_id: str, payload: BrandRequest, user: AuthUser, db: Session = Depends(get_db)):
    with network_lock(db, pool.LOCK):
        row = db.get(models.ReglueReserveDomain, reserve_id)
        if not row: raise HTTPException(404, 'Домен не найден.')
        if row.status != 'available': raise HTTPException(409, 'Домен уже выделен запуску. Изменение бренда недоступно.')
        row.brand = payload.brand.strip() or None
        db.commit()
        return {'id': row.id, 'brand': row.brand}
