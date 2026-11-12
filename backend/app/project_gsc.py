"""Manual project-local GSC note. Never included in site sync/publication payloads."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.security import AuthUser

router = APIRouter(prefix='/sites/{site_id}/gsc', tags=['Project GSC'])
PREFIX = 'project-private:gsc:'


class GscValue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str = Field(max_length=2000, strict=True)


def project(db, site_id, user, *, lock=False):
    allowed = user.get('allowed_site_ids')
    if allowed is not None and site_id not in allowed:
        raise HTTPException(404, 'Проект не найден или недоступен.')
    site = db.get(models.Site, site_id, with_for_update=lock)
    if site is None:
        raise HTTPException(404, 'Проект не найден или недоступен.')
    return site


@router.get('', response_model=GscValue)
def read_gsc(site_id: str, user: AuthUser, response: Response, db: Session = Depends(get_db)):
    project(db, site_id, user)
    response.headers['Cache-Control'] = 'no-store'
    row = db.get(models.AutoReglueConfig, PREFIX + site_id)
    return {'value': (row.value or {}).get('value', '') if row else ''}


@router.put('', response_model=GscValue)
def save_gsc(site_id: str, payload: GscValue, user: AuthUser, response: Response,
             db: Session = Depends(get_db)):
    # Lock the existing project so simultaneous first saves cannot create duplicate keys.
    project(db, site_id, user, lock=True)
    key = PREFIX + site_id
    row = db.get(models.AutoReglueConfig, key)
    if row is None:
        row = models.AutoReglueConfig(key=key)
        db.add(row)
    row.value = {'value': payload.value}
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'value': payload.value}
