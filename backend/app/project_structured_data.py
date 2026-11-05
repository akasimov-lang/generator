"""Read and edit native Webdev JSON-LD with durable, idempotent receipts."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models, project_network
from app.db import get_db
from app.project_pages import remote_errors
from app.security import AuthUser

router = APIRouter(prefix='/sites', tags=['Project structured data'])


class StructuredDataUpdate(BaseModel):
    request_id: UUID
    revision: str = Field(min_length=64, max_length=64)
    markup: str = Field(max_length=100000)
    enabled: bool | None = None


def validate_markup(markup):
    """Allow JSON-LD only; never accept executable script or unrelated HTML."""
    markup = markup.strip()
    if not markup:
        raise HTTPException(422, 'Введите код микроразметки.')

    def reject_constant(value):
        raise ValueError(value)

    def parse(value):
        try:
            data = json.loads(value, parse_constant=reject_constant)
        except ValueError as error:
            raise HTTPException(422, 'Некорректный JSON в микроразметке. Проверьте кавычки, запятые и скобки.') from error
        if not isinstance(data, (dict, list)) or not data or (isinstance(data, list) and not all(isinstance(item, dict) for item in data)):
            raise HTTPException(422, 'Микроразметка должна содержать JSON-объект или непустой массив объектов.')
        return data

    from app.structured_data_generation import serialize
    if markup.startswith(('{', '[')):
        return serialize(parse(markup), script=True)
    # Preserve valid native formatting and templates inside JSON strings.
    pattern = re.compile(r'\s*<script\s+type\s*=\s*([\"\'])application/ld\+json\1\s*>(.*?)</script\s*>', re.I | re.S)
    position = 0
    for match in pattern.finditer(markup):
        if match.start() != position:
            break
        parse(match.group(2))
        position = match.end()
    if position != len(markup):
        raise HTTPException(422, 'Допустим только JSON или блоки <script type="application/ld+json"> с JSON внутри.')
    return markup


def get_site(db, site_id, user):
    site = db.get(models.Site, site_id)
    allowed = user.get('allowed_site_ids')
    if not site or not site.is_active or (allowed is not None and site_id not in allowed):
        raise HTTPException(404, 'Проект не найден или недоступен.')
    return site


def view(project):
    head = project.get('head') if isinstance(project, dict) else None
    head = head if isinstance(head, dict) else {}
    enabled = head.get('enableJsonMarkup')
    markup = head.get('jsonMarkup')
    fields = {'enableJsonMarkup': enabled, 'jsonMarkup': markup}
    return {'enabled': enabled if isinstance(enabled, bool) else None,
        'markup': markup if isinstance(markup, str) else '',
        'revision': sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        'verified_at': datetime.now(timezone.utc).isoformat(), 'source': 'webdev'}


def with_receipt(db, value, operation):
    if (value and operation.status != 'confirmed' and value['enabled'] is operation.request_payload['enableJsonMarkup']
            and value['markup'] == operation.request_payload['jsonMarkup']):
        operation.status = 'confirmed'
        operation.message = 'Микроразметка сохранена в Webdev.'
        db.commit()
    return {'data': value, 'operation': {'id': operation.id, 'status': operation.status, 'message': operation.message}}


@router.get('/{site_id}/structured-data')
def read_structured_data(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site = get_site(db, site_id, user)
    with remote_errors(), project_network.Remote(db, site) as remote:
        return view(remote.project())


@router.get('/{site_id}/structured-data/operations/{operation_id}')
def check_structured_data(site_id: str, operation_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    site = get_site(db, site_id, user)
    operation = db.get(models.NetworkOperation, str(operation_id))
    if not operation or operation.site_id != site.id or operation.action != 'structured_data':
        raise HTTPException(404, 'Запрос сохранения ещё не зарегистрирован. Можно повторить сохранение с тем же кодом.')
    with remote_errors(), project_network.network_lock(db, site.id), project_network.Remote(db, site) as remote:
        return with_receipt(db, view(remote.project()), operation)


@router.put('/{site_id}/structured-data')
def save_structured_data(site_id: str, payload: StructuredDataUpdate, user: AuthUser, db: Session = Depends(get_db)):
    site = get_site(db, site_id, user)
    markup = payload.markup if payload.enabled is not None else validate_markup(payload.markup)
    with remote_errors(), project_network.network_lock(db, site.id), project_network.Remote(db, site) as remote:
        existing = db.get(models.NetworkOperation, str(payload.request_id))
        if existing and (existing.site_id != site.id or existing.action != 'structured_data'
                         or existing.initiator != user['username'] or existing.request_payload.get('jsonMarkup') != markup):
            raise HTTPException(409, 'Идентификатор запроса уже используется другой операцией.')
        current = view(remote.project())
        if payload.enabled is not None and payload.markup != current['markup']:
            raise HTTPException(409, 'Код изменился. Обновите данные перед переключением.')
        if existing and payload.enabled is not None and existing.request_payload.get('enableJsonMarkup') is not payload.enabled:
            raise HTTPException(409, 'Идентификатор запроса уже используется.')
        if existing:
            return with_receipt(db, current, existing)  # A repeated request only verifies; never sends again.
        if current['revision'] != payload.revision:
            raise HTTPException(409, 'Микроразметка изменилась в Webdev. Скопируйте правки и загрузите актуальный код.')
        if current['enabled'] is None:
            raise HTTPException(409, 'Webdev не подтвердил настройки микроразметки. Обновите данные.')
        pending = db.scalar(select(models.NetworkOperation.id).where(
            models.NetworkOperation.site_id == site.id, models.NetworkOperation.action == 'structured_data',
            models.NetworkOperation.status.in_(['pending', 'unknown'])).limit(1))
        if pending:
            raise HTTPException(409, 'Предыдущее сохранение микроразметки ещё не подтверждено. Обновите данные сетки.')
        fields = {'enableJsonMarkup': current['enabled'] if payload.enabled is None else payload.enabled, 'jsonMarkup': markup}
        operation = models.NetworkOperation(id=str(payload.request_id), site_id=site.id,
            action='structured_data', status='pending', initiator=user['username'],
            request_payload={**fields, 'before': current}, message='Сохранение отправляется в Webdev.')
        db.add(operation)
        db.commit()  # Durable before the write, including lost responses / process restarts.
        try:
            code, response = remote.request('PATCH', '/projects/update-head', {'folder': site.name, **fields})
            operation.response_status = code
            rejected = isinstance(response, dict) and (response.get('error') or response.get('errors') or response.get('success') is False)
            operation.status = 'failed' if rejected else 'unknown'
            operation.message = 'Webdev отклонил сохранение микроразметки.' if rejected else 'Запрос отправлен. Проверяем сохранение.'
        except httpx.HTTPStatusError as error:
            operation.response_status = error.response.status_code
            operation.status = 'failed' if 400 <= error.response.status_code < 500 else 'unknown'
            operation.message = f'Webdev вернул HTTP {error.response.status_code}. Проверяем результат сохранения.'
        except (httpx.RequestError, ValueError):
            operation.status = 'unknown'
            operation.message = 'Ответ Webdev не получен. Проверьте сохранение; код остаётся в редакторе.'
        db.commit()
        try:
            verified = view(remote.project())
        except (httpx.HTTPError, ValueError, project_network.ProjectCacheError):
            verified = None
        return with_receipt(db, verified, operation)
