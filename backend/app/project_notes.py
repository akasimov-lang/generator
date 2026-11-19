"""One shared, revision-checked sticky note per project. Never published to Webdev."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.db import get_db
from app.security import AuthUser

router = APIRouter(tags=['Project notes'])
PREFIX = 'project-note:'

class NoteEdit(BaseModel):
    text: str = Field(max_length=20000)
    revision: str = Field(default='', max_length=36)

def site_for(db, site_id, user, lock=False):
    allowed = user.get('allowed_site_ids')
    if allowed is not None and site_id not in allowed:
        raise HTTPException(404, 'Проект не найден.')
    query = select(models.Site).where(models.Site.id == site_id)
    if lock:
        query = query.with_for_update()
    site = db.scalar(query)
    if site is None:
        raise HTTPException(404, 'Проект не найден.')
    return site

def value(row):
    return row.value if row else {'text': '', 'revision': '', 'updated_at': None, 'updated_by': None}

@router.get('/project-notes')
def note_index(user: AuthUser, db: Session = Depends(get_db)):
    ids = set(db.scalars(select(models.Site.id)))
    allowed = user.get('allowed_site_ids')
    if allowed is not None:
        ids.intersection_update(allowed)
    rows = db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.startswith(PREFIX)))
    return {'site_ids': [r.key[len(PREFIX):] for r in rows
                         if r.key[len(PREFIX):] in ids and r.value.get('text', '').strip()]}

@router.get('/sites/{site_id}/note')
def get_note(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site_for(db, site_id, user)
    return value(db.get(models.AutoReglueConfig, PREFIX + site_id))

@router.put('/sites/{site_id}/note')
def save_note(site_id: str, payload: NoteEdit, user: AuthUser, db: Session = Depends(get_db)):
    # Lock the always-existing site, including the first note write (no row yet).
    site_for(db, site_id, user, lock=True)
    row = db.scalar(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key == PREFIX + site_id).execution_options(populate_existing=True))
    current = value(row)
    # A lost response can be retried without changing or duplicating the note.
    if current['text'] == payload.text:
        return current
    if current['revision'] != payload.revision:
        raise HTTPException(409, 'Заметка изменена в другой вкладке. Ваш текст сохранён в черновике.')
    result = {'text': payload.text, 'revision': str(uuid4()),
              'updated_at': datetime.now(timezone.utc).isoformat(), 'updated_by': user['username']}
    if row is None:
        db.add(models.AutoReglueConfig(key=PREFIX + site_id, value=result))
    else:
        row.value = result
    db.commit()
    return result
