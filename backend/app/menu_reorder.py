"""Move menu siblings without changing URLs, content, nesting or metadata."""
from copy import deepcopy
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.project_cache import ProjectCacheError
from app.project_network import Remote
from app.security import AuthUser
from app.technical_pages import menu_lock

router = APIRouter(tags=['Project menu'])
CHILD_KEYS = ('children', 'items', 'submenu', 'subMenu')


class MoveMenuItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: list[int] = Field(min_length=1, max_length=12)
    target: list[int] = Field(min_length=1, max_length=12)
    position: Literal['before', 'after']
    expected_menu: list[Any] = Field(max_length=1500)


def move_item(items, source, target, position):
    if not source or not target or source[:-1] != target[:-1] or any(i < 0 for i in source + target):
        raise ValueError('Перемещайте пункты внутри одного раздела меню.')
    updated = deepcopy(items)
    siblings = updated
    try:
        for index in source[:-1]:
            node = siblings[index]
            siblings = next(node[key] for key in CHILD_KEYS if isinstance(node.get(key), list))
        if not isinstance(siblings[source[-1]], dict) or not isinstance(siblings[target[-1]], dict):
            raise ValueError('Неподдерживаемый пункт меню.')
        if source == target:
            return updated
        item = siblings.pop(source[-1])
        destination = target[-1] - int(source[-1] < target[-1]) + int(position == 'after')
        siblings.insert(destination, item)
        if updated == items:
            return updated
        for order, sibling in enumerate(siblings):
            if not isinstance(sibling, dict):
                raise ValueError('Неподдерживаемый пункт меню.')
            sibling['order'] = order
    except (IndexError, KeyError, TypeError, AttributeError, StopIteration) as error:
        raise ValueError('Меню изменилось. Обновите его перед перемещением.') from error
    return updated


def remote_menu(project, menu_type):
    menu = (project.get('data') or {}).get('menu')
    if not isinstance(menu, dict) or not isinstance(menu.get(menu_type), list):
        raise ProjectCacheError('Webdev не вернул меню проекта.')
    return menu[menu_type]


def cache_menu(db, site, menu_type, items):
    db.refresh(site)
    site.default_menu = {**(site.default_menu or {}), menu_type: items}
    db.commit()


def reorder(db, site, menu_type, payload, username):
    with menu_lock(db, site.id), Remote(db, site) as remote:
        original = remote_menu(remote.project(), menu_type)
        if original != payload.expected_menu:
            cache_menu(db, site, menu_type, original)
            raise HTTPException(409, 'Меню уже изменилось. Загружена актуальная версия; повторите перемещение.')
        updated = move_item(original, payload.source, payload.target, payload.position)
        if updated == original:
            return {'success': True, 'changed': False, 'items': original}
        log = models.PublicationLog(endpoint_url=f'internal://sites/{site.id}/menu/{menu_type}/reorder',
            request_payload={'action': 'menu_reorder', 'project_name': site.name, 'username': username,
                'menu_type': menu_type, 'source': payload.source, 'target': payload.target,
                'position': payload.position, 'menu_before': original, 'menu_after': updated})
        db.add(log)
        db.commit()
        request_error = None
        status = None
        try:
            status, _ = remote.request('POST', '/projects/menu',
                {'type': menu_type, 'folder': site.name, 'list': updated})
        except (httpx.HTTPError, ProjectCacheError, ValueError) as error:
            request_error = type(error).__name__
        # A timeout is ambiguous: confirm by reading, never retry a write blindly.
        try:
            confirmed = remote_menu(remote.project(), menu_type)
        except (httpx.HTTPError, ProjectCacheError, ValueError):
            log.response_status = status
            log.error_message = 'Не удалось подтвердить сохранение порядка в Webdev.'
            db.commit()
            raise HTTPException(502, 'Не удалось подтвердить порядок. Обновите меню перед повтором.')
        cache_menu(db, site, menu_type, confirmed)
        if confirmed != updated:
            log.response_status = status or 502
            log.error_message = 'Webdev не подтвердил новый порядок.' + (f' {request_error}' if request_error else '')
            db.commit()
            raise HTTPException(409, 'Webdev не подтвердил новый порядок. Показано фактическое меню.')
        log.response_status = status or 200
        log.response_body = {'confirmed': True, 'items': len(updated)}
        db.commit()
        return {'success': True, 'changed': True, 'items': confirmed}


@router.post('/sites/{site_id}/menu/{menu_type}/reorder')
def reorder_menu(site_id: str, menu_type: Literal['header', 'footer'], payload: MoveMenuItem,
                 user: AuthUser, db: Session = Depends(get_db)):
    allowed = user.get('allowed_site_ids')
    if allowed is not None and site_id not in allowed:
        raise HTTPException(404, 'Проект недоступен.')
    site = db.get(models.Site, site_id)
    if site is None:
        raise HTTPException(404, 'Проект не найден.')
    try:
        return reorder(db, site, menu_type, payload, user['username'])
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except (httpx.HTTPError, ProjectCacheError) as error:
        raise HTTPException(502, 'Не удалось прочитать меню Webdev. Изменения не отправлены.') from error
