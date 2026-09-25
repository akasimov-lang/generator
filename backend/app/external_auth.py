"""Webdev is the sole identity and project-assignment authority."""
import hashlib
import threading
import time
from collections import OrderedDict

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import models
from app.core.config import get_settings

_cache = OrderedDict()
_cache_lock = threading.Lock()
CACHE_SECONDS = 30


class ExternalLoginResponse(Exception):
    """An unsuccessful Webdev login response that must reach the browser unchanged."""

    def __init__(self, response: httpx.Response):
        super().__init__(f"Webdev login returned HTTP {response.status_code}")
        self.status_code = response.status_code
        self.content = response.content
        self.content_type = response.headers.get("content-type")


def _json(response, unauthorized_message="Срок действия токена Webdev истёк."):
    if response.status_code in (400, 401, 403):
        raise HTTPException(401, unauthorized_message)
    if not response.is_success:
        raise HTTPException(503, "Сервис авторизации временно недоступен.")
    try:
        return response.json()
    except ValueError:
        raise HTTPException(503, "Некорректный ответ сервиса авторизации.") from None


def login_external(username, password):
    try:
        with httpx.Client(timeout=20, follow_redirects=False,
                          headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}) as client:
            response = client.post(get_settings().project_cache_url.rstrip('/') + '/auth/login',
                                   json={"username": username.strip(), "pass": password})
            if not response.is_success:
                raise ExternalLoginResponse(response)
            data = _json(response)
        token = data.get('token') if isinstance(data, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise HTTPException(503, "Сервис авторизации не вернул токен.")
        return token
    except httpx.HTTPError:
        raise HTTPException(503, "Сервис авторизации временно недоступен.") from None


def authenticate(username, password):
    """Request a new Webdev token and retry once if that token is already invalid."""
    for attempt in range(2):
        token = login_external(username, password)
        try:
            return token, identity(token, fresh=True)
        except HTTPException as error:
            forget(token)
            if error.status_code != 401:
                raise
            if attempt:
                raise HTTPException(
                    401,
                    "Webdev выдал новый токен, но не подтвердил его. Повторите вход.",
                ) from None
    raise HTTPException(401, "Не удалось подтвердить токен Webdev.")


def assigned_to(settings, profile):
    foreign, name = profile.get('foreign'), profile.get('name')
    developer = (settings.get('webdevDuty') or {}).get('developer') if isinstance(settings.get('webdevDuty'), dict) else None
    return bool((foreign and foreign in (settings.get('duty'), settings.get('secondDuty'), developer))
                or (name and developer == name))


def identity(token, fresh=False):
    key = hashlib.sha256(token.encode()).hexdigest()
    with _cache_lock:
        cached = _cache.get(key)
        if not fresh and cached and cached[0] > time.monotonic():
            _cache.move_to_end(key)
            return cached[1]
        _cache.pop(key, None)
    try:
        with httpx.Client(timeout=20, follow_redirects=False, headers={'Authorization': 'Bearer ' + token}) as client:
            base = get_settings().project_cache_url.rstrip('/')
            profile = _json(client.get(base + '/auth/me'))
            if not isinstance(profile, dict) or not isinstance(profile.get('username'), str) or not profile['username']:
                raise HTTPException(503, "Сервис авторизации не подтвердил пользователя.")
            admin = profile['username'] == 'anton'
            projects = None
            if not admin:
                rows = _json(client.post(base + '/projects/cache', json={'fields': {'settings': True, 'head': False, 'data': False}}))
                if not isinstance(rows, list):
                    raise HTTPException(503, "Не удалось проверить права на проекты.")
                # Names alone are ambiguous: the same project may exist on different servers.
                projects = frozenset((row['name'], row['serverIp']) for row in rows
                    if isinstance(row, dict) and isinstance(row.get('name'), str) and isinstance(row.get('serverIp'), str)
                    and isinstance(row.get('settings'), dict) and assigned_to(row['settings'], profile))
            result = {'username': profile['username'], 'is_admin': admin, 'projects': projects}
    except httpx.HTTPError:
        raise HTTPException(503, "Не удалось проверить авторизацию и права на проекты.") from None
    with _cache_lock:
        _cache[key] = (time.monotonic() + CACHE_SECONDS, result)
        while len(_cache) > 256:
            _cache.popitem(last=False)
    return result


def forget(token):
    with _cache_lock:
        _cache.pop(hashlib.sha256(token.encode()).hexdigest(), None)


def local_profile(db, identity):
    """Keep identity references/favorites, never local credentials or local role grants."""
    username = identity['username']
    user = db.scalar(select(models.User).where(models.User.username == username))
    if user is None:
        if db.bind.dialect.name == 'postgresql':
            db.execute(pg_insert(models.User).values(username=username, password_hash='', is_admin=identity['is_admin'], is_active=True)
                       .on_conflict_do_nothing(index_elements=['username']))
            db.commit()
            user = db.scalar(select(models.User).where(models.User.username == username))
        else:
            user = models.User(username=username, password_hash='', is_admin=identity['is_admin'], is_active=True)
            db.add(user)
    if user.password_hash or user.is_admin != identity['is_admin'] or not user.is_active:
        user.password_hash = ''
        user.is_admin = identity['is_admin']
        user.is_active = True
    if db.new or db.dirty:
        db.commit()
        db.refresh(user)
    return user


def allowed_site_ids(db, identity):
    if identity['is_admin']:
        return None
    projects = identity['projects']
    return frozenset(site_id for site_id, name, server in db.execute(
        select(models.Site.id, models.Site.name, models.Site.cache_server_ip)) if (name, server) in projects)
