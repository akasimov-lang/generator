"""Editable, authenticated author catalog, independent of site publication.

Each persona occupies its own database record in the existing JSON registry.
Bundled starter profiles are inserted once; deployments never overwrite edits.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AutoReglueConfig
from app.security import AuthUser, AdminUser

router = APIRouter(prefix='/personas', tags=['Personas'])
PREFIX = 'author-persona:'
SEED = Path(__file__).parent / 'data' / 'personas.json'
COUNTRIES = {
    'PL': {'name': 'Польша', 'flag': '🇵🇱', 'language': 'pl'},
    'CZ': {'name': 'Чехия', 'flag': '🇨🇿', 'language': 'cs'},
    'DK': {'name': 'Дания', 'flag': '🇩🇰', 'language': 'da'},
    'CA': {'name': 'Канада', 'flag': '🇨🇦', 'language': 'en-CA'},
    'AU': {'name': 'Австралия', 'flag': '🇦🇺', 'language': 'en-AU'},
}


def word_count(value: str) -> int:
    return len(re.findall(r"\b[^\W_]+(?:['’–-][^\W_]+)*\b", value))


class Award(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=200)
    year: int = Field(ge=1900, le=2100)


class PersonaInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    geo: str
    specialization: str = Field(min_length=3, max_length=180)
    biography: str = Field(max_length=50000)
    specializations: list[str] = Field(min_length=4, max_length=9)
    awards: list[Award] = Field(min_length=4, max_length=9)
    portrait_url: str = ''

    @field_validator('geo')
    @classmethod
    def known_geo(cls, value):
        value = value.upper()
        if value not in COUNTRIES:
            raise ValueError('Выберите GEO из списка.')
        return value

    @field_validator('biography')
    @classmethod
    def complete_biography(cls, value):
        if word_count(value) < 400:
            raise ValueError('Биография должна содержать минимум 400 слов.')
        return value

    @field_validator('specializations')
    @classmethod
    def distinct_tags(cls, values):
        values = [s.strip() for s in values]
        if any(not s or len(s) > 160 for s in values):
            raise ValueError('Каждая специализация: от 1 до 160 символов.')
        if len({s.casefold() for s in values}) != len(values):
            raise ValueError('Специализации не должны повторяться.')
        return values

    @field_validator('awards')
    @classmethod
    def distinct_awards(cls, values):
        if len({(v.title.casefold(), v.year) for v in values}) != len(values):
            raise ValueError('Награды не должны повторяться.')
        return values

    @field_validator('portrait_url')
    @classmethod
    def local_portrait(cls, value):
        if value and not re.fullmatch(r'/personas-images/[a-z0-9-]+\.webp', value):
            raise ValueError('Используйте локальный портрет из базы персон.')
        return value


class PersonaEdit(PersonaInput):
    revision: int = Field(ge=1)


def seed_catalog(db: Session):
    records = json.loads(SEED.read_text(encoding='utf-8'))
    # Serialize concurrent application starts without altering existing records.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(642588200)'))
    now = datetime.now(timezone.utc).isoformat()
    for original in records:
        key = PREFIX + original['id']
        if db.get(AutoReglueConfig, key) is not None:
            continue
        body = PersonaInput.model_validate({k: original[k] for k in PersonaInput.model_fields if k in original}).model_dump()
        body.update(id=original['id'], language=COUNTRIES[body['geo']]['language'], fictional=True,
                    revision=1, created_at=now, updated_at=now)
        db.add(AutoReglueConfig(key=key, value=body))
    db.commit()


def public_record(value, *, summary=False):
    result = dict(value)
    result['word_count'] = word_count(result['biography'])
    result['country'] = COUNTRIES[result['geo']]['name']
    result['flag'] = COUNTRIES[result['geo']]['flag']
    if summary:
        result['biography_excerpt'] = result.pop('biography')[:200].rsplit(' ', 1)[0] + '…'
    return result


def lookup(db, persona_id):
    if not re.fullmatch(r'[a-z0-9-]{1,60}', persona_id):
        raise HTTPException(404, 'Персона не найдена.')
    row = db.get(AutoReglueConfig, PREFIX + persona_id)
    if row is None:
        raise HTTPException(404, 'Персона не найдена.')
    return row


@router.get('')
def list_personas(user: AuthUser, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    rows = db.scalars(select(AutoReglueConfig).where(AutoReglueConfig.key.startswith(PREFIX))).all()
    items = sorted([public_record(r.value, summary=True) for r in rows],
                   key=lambda p: (list(COUNTRIES).index(p['geo']), p['last_name'], p['first_name']))
    return {'items': items, 'total': len(items), 'countries': [
        {'code': code, **data, 'count': sum(p['geo'] == code for p in items)}
        for code, data in COUNTRIES.items()]}


@router.get('/{persona_id}')
def read_persona(persona_id: str, user: AuthUser, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return public_record(lookup(db, persona_id).value)


@router.post('', status_code=201)
def create_persona(payload: PersonaInput, user: AdminUser, db: Session = Depends(get_db)):
    base = unicodedata.normalize('NFKD', payload.first_name + '-' + payload.last_name).encode('ascii', 'ignore').decode().lower()
    base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:40] or 'author'
    persona_id = base + '-' + uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    value = payload.model_dump()
    value.update(id=persona_id, language=COUNTRIES[value['geo']]['language'], fictional=True,
                 revision=1, created_at=now, updated_at=now)
    db.add(AutoReglueConfig(key=PREFIX + persona_id, value=value)); db.commit()
    return public_record(value)


@router.put('/{persona_id}')
def edit_persona(persona_id: str, payload: PersonaEdit, user: AdminUser, db: Session = Depends(get_db)):
    row = lookup(db, persona_id)
    value = {**row.value, **payload.model_dump(exclude={'revision'}),
             'language': COUNTRIES[payload.geo]['language'], 'revision': payload.revision + 1,
             'updated_at': datetime.now(timezone.utc).isoformat()}
    result = db.execute(update(AutoReglueConfig).where(
        AutoReglueConfig.key == row.key,
        AutoReglueConfig.value['revision'].as_integer() == payload.revision
    ).values(value=value).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Профиль уже изменён. Откройте его заново перед сохранением.')
    db.commit()
    return public_record(value)
