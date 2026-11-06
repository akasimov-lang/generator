"""Read and edit native showcase cards without replacing unrelated project data."""
from copy import deepcopy
import hashlib
import json
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import models, showcase_logos, showcase_management
from app.core.config import get_settings
from app.db import get_db
from app.project_cache import ProjectCacheError
from app.project_network import Remote, network_lock
from app.project_pages import site_for, remote_errors, read_project
from app.security import AuthUser
from app.showcase_brands import brand_name, showcase_brands

router = APIRouter(prefix='/sites/{site_id}/showcase', tags=['Showcase'])
PAGE_KEY = 'showcase:casinos'
LABELS = {'brand': 'Бренд', 'name': 'Бренд', 'bonus': 'Бонус', 'minDep': 'Мин. депозит',
          'wager': 'Вейджер', 'rating': 'Рейтинг', 'description': 'Описание',
          'text': 'Текст', 'title': 'Заголовок', 'tags': 'Метки', 'conditions': 'Условия',
          'buttonPlay': 'Кнопка'}
HIDDEN = {'icons_html', 'actions_html', 'number', 'split', 'id', 'logo', 'image', 'url', 'href', 'link', 'slug'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def native_groups(project):
    import re
    data = project.get('data') or {}
    casinos = data.get('casinos')
    if isinstance(casinos, list):
        return [('', casinos)]
    if not isinstance(casinos, dict):
        return []
    home = next((p for p in data.get('pages', []) if isinstance(p, dict) and not str(p.get('slug') or '').strip('/')), {})
    used = [b.get('data', {}).get('shortcode', '') for b in (home.get('content') or {}).get('blocks', []) if isinstance(b, dict) and b.get('type') == 'shortcode' and isinstance(b.get('data'), dict)]
    definitions = {str(s.get('name', '')).removesuffix('.hbs'): s.get('data', '') for s in project.get('shortcodes', []) if isinstance(s, dict)}
    groups, visited = [], set()
    def visit(name):
        name = str(name).strip().removesuffix('.hbs')
        if name in visited or name in {'header', 'footer', 'menu', 'navigation'}:
            return
        visited.add(name)
        markup = definitions.get(name, '')
        if isinstance(markup, str):
            groups.extend(re.findall(r'{{#each\s+(?:\.\./)?casinos\.([\w]+)\s*}}', markup))
            for nested in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}', markup):
                visit(nested)
        # Aggregate cache intentionally omits templates. The native casinos
        # shortcode uses standard cards; basic is a shared logo/label gallery.
        if not definitions and name == 'casinos':
            groups.append('standard')
    for name in used:
        visit(name)
    for name in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}', str(project.get('layout') or '')):
        visit(name)
    return [(group, casinos[group]) for group in dict.fromkeys(groups) if group != 'basic' and isinstance(casinos.get(group), list)]


def rows(project):
    result = []
    for group, records in native_groups(project):
        for index, record in enumerate(records):
            fields = []
            if isinstance(record, list):
                values = {f.get('key'): f.get('value') for f in record if isinstance(f, dict)}
                for pos, field in enumerate(record):
                    if not isinstance(field, dict) or field.get('key') in HIDDEN:
                        continue
                    key = field.get('key', '')
                    if isinstance(field.get('value'), str) and field.get('type', 'text') == 'text':
                        fields.append({'id': str(pos), 'key': key, 'label': LABELS.get(key, key), 'value': field['value'], 'list': False})
                    elif field.get('type') == 'list' and isinstance(field.get('data'), list) and all(isinstance(x, str) for x in field['data']):
                        fields.append({'id': str(pos), 'key': key, 'label': LABELS.get(key, key), 'value': '\n'.join(field['data']), 'list': True})
            elif isinstance(record, dict):
                values = record
                fields = [{'id': key, 'key': key, 'label': LABELS.get(key, key), 'value': value, 'list': False}
                          for key, value in record.items() if key not in HIDDEN and isinstance(value, str)]
            else:
                continue
            brand = brand_name(values.get('brand') or values.get('name'))
            if brand:
                result.append({'id': json.dumps([group, index], separators=(',', ':')), 'brand': brand,
                               'fields': fields, 'editable': bool(fields), 'group': group, 'logo': showcase_logos.url(project, record)})
    return result


def view(project, source='webdev', warning=None):
    cards = rows(project)
    management, legacy = showcase_management.inspect(project, cards)
    cards = cards + legacy
    if not cards:
        cards = [{'id': f'legacy:{index}', 'brand': brand, 'fields': [], 'editable': False, 'group': ''}
                 for index, brand in enumerate(showcase_brands(project)['brands'])]
    return {'revision': digest((project.get('data') or {}).get('casinos')), 'rows': cards,
            'count': len(cards), 'source': source, 'warning': warning, 'management': management,
            'message': '' if cards else 'В сохранённых данных проекта нет карточек брендов витрины.'}


def edited_casinos(project, row_id, changes):
    card = next((r for r in rows(project) if r['id'] == row_id), None)
    if card is None:
        raise HTTPException(409, 'Карточка витрины изменилась. Загрузите актуальный список.')
    allowed = {f['id']: f for f in card['fields']}
    if not changes or not set(changes).issubset(allowed):
        raise HTTPException(422, 'Можно изменять только текстовые поля выбранного бренда.')
    casinos = deepcopy(project['data']['casinos'])
    group, index = json.loads(row_id)
    record = (casinos[group] if group else casinos)[index]
    for field_id, value in changes.items():
        field = allowed[field_id]
        if field['key'] in {'brand', 'name'} and not brand_name(value):
            raise HTTPException(422, 'Укажите корректное название бренда.')
        if isinstance(record, list):
            record[int(field_id)]['data' if field['list'] else 'value'] = value.splitlines() if field['list'] else value
        else:
            record[field_id] = value
    return casinos


class ShowcaseEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    row_id: str = Field(max_length=300)
    fields: dict[str, str]
    logo: showcase_logos.LogoUpload | None = None


def allowed_site(db, site_id, user):
    if user.get('allowed_site_ids') is not None and site_id not in user['allowed_site_ids']:
        raise HTTPException(404, 'Проект недоступен.')
    return site_for(db, site_id)


def version2(remote):
    remote.client.headers['Accept'] = 'application/json;v=2'
    return remote


def result(operation, project=None):
    return {'id': operation.id, 'status': operation.status, 'error': operation.error,
            'showcase': view(project) if project is not None and operation.status == 'confirmed' else None}


def confirm(db, operation, remote):
    if operation.after_page.get('logo_upload_pending'):
        operation.status, operation.error = 'failed', 'Загрузка логотипа не подтверждена. Карточка не отправлялась; выберите файл и сохраните заново.'
        db.commit()
        return result(operation)
    project = remote.project()
    if not operation.after_page.get('logo_upload_pending') and (project.get('data') or {}).get('casinos') == operation.after_page['casinos']:
        operation.status, operation.error = 'confirmed', None
    else:
        operation.status, operation.error = 'unknown', 'Webdev пока не подтвердил изменения. Проверьте сохранение; повторной отправки не было.'
    db.commit()
    return result(operation, project)


@router.get('/history')
def history(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    allowed_site(db, site_id, user)
    from app.showcase_history import events
    return {'items': events(db, site_id)}


@router.get('')
def load(site_id: str, user: AuthUser, db: Session = Depends(get_db), refresh: bool = False):
    site = allowed_site(db, site_id, user)
    project, source, warning = read_project(db, site, refresh=refresh)
    response = view(project, source, warning)
    if not response['management']['complete'] and not refresh:
        project, source, warning = read_project(db, site, refresh=True)
        response = view(project, source, warning)
    response['management']['record_id'] = showcase_management.remember(db, site, user, response['management'])
    return response


@router.put('')
def save(site_id: str, payload: ShowcaseEdit, user: AuthUser, db: Session = Depends(get_db)):
    site = allowed_site(db, site_id, user)
    if len(payload.fields) > 100 or sum(len(v) for v in payload.fields.values()) > 100000:
        raise HTTPException(422, 'Текст карточки слишком большой.')
    prepared_logo = showcase_logos.prepare(payload.logo) if payload.logo else None
    fingerprint = digest(payload.model_dump(mode='json'))
    with remote_errors(), network_lock(db, site_id):
        operation = db.get(models.ProjectPageEdit, str(payload.request_id))
        if operation:
            if operation.site_id != site_id or operation.page_key != PAGE_KEY or operation.fingerprint != fingerprint:
                raise HTTPException(409, 'Идентификатор сохранения уже использован.')
            return result(operation)
        with Remote(db, site) as remote:
            version2(remote)
            project = remote.project()
            before = (project.get('data') or {}).get('casinos')
            if digest(before) != payload.revision:
                raise HTTPException(409, 'Витрина изменилась в Webdev. Скопируйте свои изменения и обновите список.')
            after = edited_casinos(project, payload.row_id, payload.fields)
            if prepared_logo:
                showcase_logos.target(after, payload.row_id)
            operation = models.ProjectPageEdit(id=str(payload.request_id), site_id=site_id, page_key=PAGE_KEY,
                requested_by=user['username'], fingerprint=fingerprint, before_page={'casinos': before},
                after_page={'casinos': after, 'logo_upload_pending': bool(prepared_logo)}, status='confirmed' if before == after and not prepared_logo else 'pending')
            db.add(operation); db.commit()
            if before == after and not prepared_logo:
                return result(operation, project)
            try:
                if prepared_logo:
                    path = showcase_logos.upload(remote, site.name, payload.request_id, prepared_logo)
                    showcase_logos.attach(after, payload.row_id, path, payload.logo.name, int(payload.request_id.int % (2**52)))
                    operation.after_page = {'casinos': after, 'logo_upload_pending': False}
                    db.commit()
                code, response = remote.request('POST', '/projects/casinos', {
                    'project': site.name, 'casinos': after, 'initiator': get_settings().project_cache_username})
                operation.response_status = code
                if isinstance(response, dict) and (response.get('success') is False or response.get('error') not in (None, False, '', 'none')):
                    operation.status, operation.error = 'failed', 'Webdev отклонил сохранение карточки.'
                    db.commit(); return result(operation)
            except httpx.HTTPStatusError as error:
                operation.response_status = error.response.status_code
                operation.status = 'failed' if error.response.status_code < 500 else 'unknown'
                operation.error = f'Webdev вернул HTTP {error.response.status_code}. Проверьте сохранение перед повторной отправкой.'
                db.commit(); return result(operation)
            except (httpx.RequestError, ValueError):
                operation.status, operation.error = 'unknown', 'Ответ Webdev не получен. Проверьте сохранение; повторной отправки не было.'
                db.commit(); return result(operation)
            try:
                return confirm(db, operation, remote)
            except (httpx.HTTPError, ProjectCacheError):
                operation.status, operation.error = 'unknown', 'Изменения отправлены, но подтверждение пока недоступно.'
                db.commit(); return result(operation)


@router.get('/edits/{request_id}')
def check(site_id: str, request_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    site = allowed_site(db, site_id, user)
    operation = db.get(models.ProjectPageEdit, str(request_id))
    if not operation or operation.site_id != site_id or operation.page_key != PAGE_KEY:
        raise HTTPException(404, 'Сохранение не найдено.')
    if operation.status in {'pending', 'unknown'}:
        with remote_errors(), network_lock(db, site_id), Remote(db, site) as remote:
            version2(remote)
            return confirm(db, operation, remote)
    return result(operation)
