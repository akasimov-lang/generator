from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Literal

from app import models, project_notifications as notifications
from app.db import get_db
from app.security import AuthUser

router = APIRouter(prefix='/sites/{site_id}/notifications', tags=['Project notifications'])


class Notice(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    code: str = Field(min_length=1, max_length=100)
    severity: Literal['info', 'warning', 'error'] = 'error'
    message: str = Field(min_length=1, max_length=20000)
    context: str = Field(default='', max_length=2000)
    active: bool = True


def site_for(db, site_id):
    site = db.get(models.Site, site_id)
    if not site:
        raise HTTPException(404, 'Проект не найден.')
    return site


@router.get('')
def get_notifications(site_id: str, user: AuthUser, db: Session = Depends(get_db),
        offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
        active_only: bool = False, q: str = Query('', max_length=200)):
    return notifications.feed(db, site_for(db, site_id), offset=offset, limit=limit, active_only=active_only, query=q)


@router.post('')
def record_notification(site_id: str, payload: Notice, user: AuthUser, db: Session = Depends(get_db)):
    id = notifications.record(db, site_for(db, site_id), user['username'], payload)
    return {'id': id, 'active': payload.active}
