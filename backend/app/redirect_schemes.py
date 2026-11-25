"""User-owned editable snapshots. Saving never calls Webdev or changes live routes."""
from datetime import datetime, timezone
import hashlib
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.db import get_db
from app.security import AuthUser
from app.project_gsc import project
from app.domain_redirects import redirect_address
from app.reglue_journal import confirmed_at

router = APIRouter(prefix='/sites/{site_id}/network/schemes', tags=['redirect-schemes'])

class Route(BaseModel):
    url: str = Field(max_length=4096)
    value: str = Field(max_length=4096)

class Expected(BaseModel):
    rows: list[Route] = Field(max_length=1000)

class DraftRow(Route):
    id: str = Field(max_length=100)
    original: str = Field(max_length=4096)
    removed: bool = False
    expected: Expected

class Point(BaseModel):
    x: float = Field(ge=0, le=100000, allow_inf_nan=False)
    y: float = Field(ge=0, le=100000, allow_inf_nan=False)

class Board(BaseModel):
    min_height: float = Field(default=0, ge=0, le=100000, allow_inf_nan=False)
    positions: dict[str, Point] = Field(default_factory=dict, max_length=2000)
    placed: list[str] = Field(default_factory=list, max_length=2000)
    zoom: float = Field(default=1, ge=.4, le=2, allow_inf_nan=False)

class Save(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['draft', 'scheme', 'backup']
    name: str = Field(default='', max_length=120)
    rows: list[DraftRow] = Field(max_length=1000)
    board: Board = Field(default_factory=Board)


def prefix(site_id, owner):
    return 'redirect-scheme:' + hashlib.sha256(f'{site_id}:{owner}'.encode()).hexdigest()[:31] + ':'


def metadata(value):
    return {k: value[k] for k in ('id', 'name', 'kind', 'saved_at')}


def address(value):
    try:
        return redirect_address(value, source=True).removeprefix('www.')
    except ValueError:
        return ''


def redirect_dates(db, site):
    """Date only when a confirmed receipt proves this exact route was changed."""
    current = (site.network_state or {}).get('domain_redirects') or []
    pending = {address(r['url']): r['value'] for r in current if isinstance(r, dict) and r.get('url') and r.get('value')}
    dates = {}
    ops = db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.status == 'confirmed', models.NetworkOperation.action.in_(['domain_redirect', 'domain_redirects_main', 'reglue_redirects', 'reglue'])).order_by(models.NetworkOperation.updated_at.desc())).all()
    for op in sorted(ops, key=confirmed_at, reverse=True):
        payload = op.request_payload or {}
        after = payload.get('redirects_after') if op.action == 'reglue' else payload.get('redirects')
        before = payload.get('redirects_before')
        if not isinstance(after, list) or not isinstance(before, list):
            continue
        a = {address(r.get('url', '')): r.get('value') for r in after if isinstance(r, dict)}
        b = {address(r.get('url', '')): r.get('value') for r in before if isinstance(r, dict)}
        for source, target in list(pending.items()):
            if a.get(source) != target:
                pending.pop(source)
            elif b.get(source) != target:
                dates[source] = confirmed_at(op).isoformat()
                pending.pop(source)
    return dates


def reconcile_draft(value, site):
    """Discard completed deletions and unchanged baseline rows deleted in Webdev."""
    state = site.network_state or {}
    if value['kind'] != 'draft' or not state.get('redirects_verified', state.get('has_domain_redirects')):
        return value
    live = state.get('domain_redirects')
    if not isinstance(live, list) or any(not isinstance(r, dict) or not isinstance(r.get('url'), str) or not isinstance(r.get('value'), str) for r in live):
        return value
    def source(value):
        try:
            return redirect_address(value, source=True)
        except ValueError:
            return None
    sources = {source(row['url']) for row in live}
    def settled(row):
        original = source(row.get('original', ''))
        expected = row.get('expected', {}).get('rows', [])
        unchanged = row['url'] == row.get('original') and len(expected) == 1 and source(expected[0]['url']) == original and row['value'] == expected[0]['value']
        return original and original not in sources and (row.get('removed') or unchanged)
    return {**value, 'rows': [row for row in value['rows'] if not settled(row)]}


@router.get('')
def listing(site_id: str, user: AuthUser, response: Response, db: Session = Depends(get_db)):
    site = project(db, site_id, user)
    response.headers['Cache-Control'] = 'no-store'
    rows = db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.startswith(prefix(site_id, user['username'])))).all()
    documents = [reconcile_draft(r.value, site) for r in rows]
    return {'items': sorted([metadata(v) for v in documents if v['kind'] != 'draft'], key=lambda v: v['saved_at'], reverse=True),
            'draft': next((v for v in documents if v['kind'] == 'draft'), None), 'redirect_dates': redirect_dates(db, site)}


@router.post('')
def save(site_id: str, payload: Save, user: AuthUser, db: Session = Depends(get_db)):
    site = project(db, site_id, user)
    name = payload.name.strip()
    if payload.kind == 'scheme' and not name:
        raise HTTPException(422, 'Укажите название схемы.')
    identity = 'draft' if payload.kind == 'draft' else uuid4().hex
    key = prefix(site_id, user['username']) + identity
    now = datetime.now(timezone.utc).isoformat()
    value = {**payload.model_dump(), 'id': identity, 'saved_at': now, 'site_id': site_id,
             'name': name or ('Резервная копия' if payload.kind == 'backup' else 'Черновик')}
    value = reconcile_draft(value, site)
    row = db.get(models.AutoReglueConfig, key)
    if row is None:
        row = models.AutoReglueConfig(key=key)
        db.add(row)
    row.value = value
    db.commit()
    return value


@router.get('/{identity}')
def read(site_id: str, identity: str, user: AuthUser, response: Response, db: Session = Depends(get_db)):
    site = project(db, site_id, user)
    response.headers['Cache-Control'] = 'no-store'
    row = db.get(models.AutoReglueConfig, prefix(site_id, user['username']) + identity)
    if row is None:
        raise HTTPException(404, 'Схема не найдена.')
    return reconcile_draft(row.value, site)
