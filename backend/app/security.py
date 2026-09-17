from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db import get_db
from app import external_auth, project_access


async def require_auth(request: Request, authorization: Annotated[str | None, Header()] = None,
                       db: Session = Depends(get_db)) -> dict:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Требуется авторизация.')
    token = authorization.removeprefix('Bearer ').strip()
    if not token:
        raise HTTPException(401, 'Требуется авторизация.')
    identity = await run_in_threadpool(external_auth.identity, token,
                                     fresh=request.method not in ('GET', 'HEAD') or request.url.path.endswith('/auth/me'))
    user = external_auth.local_profile(db, identity)
    ids = external_auth.allowed_site_ids(db, identity)
    db.info['allowed_site_ids'] = ids
    db.info['allowed_project_keys'] = identity['projects']
    if ids is not None:
        project_access.guard_references(db, request.path_params)
        project_access.guard_references(db, dict(request.query_params))
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            try:
                body = await request.json()
            except ValueError:
                body = None
            if isinstance(body, dict):
                project_access.guard_references(db, body)
    return {'id': user.id, 'username': identity['username'], 'is_admin': identity['is_admin'],
            'allowed_site_ids': sorted(ids) if ids is not None else None}


AuthUser = Annotated[dict, Depends(require_auth)]


def require_admin(user: AuthUser) -> dict:
    if not user.get('is_admin'):
        raise HTTPException(403, 'Требуются права администратора.')
    return user


AdminUser = Annotated[dict, Depends(require_admin)]
