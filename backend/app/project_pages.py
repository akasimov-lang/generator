"""Edit Webdev pages without rebuilding or discarding their existing fields."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db import get_db
from app.project_cache import ProjectCacheError, fetch_project_cache
from app.project_network import Remote, network_lock, NetworkConflict
from app.security import AuthUser

router = APIRouter(prefix="/sites/{site_id}/pages", tags=["Project pages"])


class PageEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(max_length=2000)
    description: str = Field(max_length=10000)
    content: dict

    @field_validator("content")
    @classmethod
    def editor_document(cls, value):
        blocks = value.get("blocks")
        if not isinstance(blocks, list) or len(blocks) > 2000:
            raise ValueError("Нужен документ страницы с массивом блоков (до 2000).")
        if any(not isinstance(b, dict) or not isinstance(b.get("type"), str) or "data" not in b for b in blocks):
            raise ValueError("Некорректный блок страницы.")
        if len(json.dumps(value, ensure_ascii=False).encode()) > 2_000_000:
            raise ValueError("Контент превышает 2 МБ.")
        return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def page_key(page):
    return digest([str(page.get("id")), page.get("slug")])


def pages(project):
    result = (project.get("data") or {}).get("pages")
    if not isinstance(result, list) or any(not isinstance(p, dict) for p in result):
        raise HTTPException(502, "Webdev не вернул список страниц. Повторите загрузку.")
    return result


def find_page(project, key):
    matches = [page for page in pages(project) if page_key(page) == key]
    if not matches:
        raise HTTPException(404, "Страница больше не существует. Обновите список страниц.")
    if len(matches) != 1 or matches[0].get("id") is None:
        raise HTTPException(409, "Webdev вернул неоднозначный идентификатор страницы. Сохранение остановлено.")
    return matches[0]


def is_home(page):
    return str(page.get("slug") or "").strip() in {"", "/"}


def page_summary(page):
    return {"key": page_key(page), "title": page.get("title") or "Без названия",
            "slug": page.get("slug") or "/", "is_home": is_home(page),
            "created_at": page.get("createdTime") or page.get("publishedTime"),
            "created_at_source": "createdTime" if page.get("createdTime") else "publishedTime",
            "updated_at": page.get("updatedTime"), "published_at": page.get("publishedTime")}


def editable(page):
    return {"title": page.get("title") or "", "description": page.get("description") or "", "content": page.get("content")}


def page_detail(page):
    return {**page_summary(page), **editable(page), "revision": digest(page)}


def site_for(db, site_id):
    site = db.scalar(select(models.Site).where(models.Site.id == site_id, models.Site.is_active.is_(True)))
    if not site:
        raise HTTPException(404, "Проект не найден или недоступен.")
    return site


@contextmanager
def remote_errors():
    try:
        yield
    except NetworkConflict as error:
        raise HTTPException(409, "С проектом выполняется другая операция. Повторите через несколько секунд.") from error
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        raise HTTPException(403 if status == 403 else 502,
                            "Нет служебного доступа к проекту в Webdev." if status == 403 else f"Webdev вернул HTTP {status}. Повторите загрузку.") from error
    except (httpx.RequestError, ProjectCacheError) as error:
        raise HTTPException(502, "Не удалось подключиться к Webdev. Повторите загрузку.") from error


def cached_pages_project(site):
    try:
        matches = [p for p in fetch_project_cache([site.name]) if p.get("name") == site.name]
        if len(matches) == 1:
            pages(matches[0])
            return matches[0]
    except (ProjectCacheError, HTTPException):
        pass
    return None


def read_project(db, site, refresh=False):
    if not refresh:
        cached = cached_pages_project(site)
        if cached is not None:
            return cached, "cache", None
    try:
        with remote_errors(), Remote(db, site) as remote:
            project = remote.project()
            pages(project)
            return project, "webdev", None
    except HTTPException:
        if refresh:
            cached = cached_pages_project(site)
            if cached is not None:
                return cached, "cache", "Webdev недоступен. Показана сохранённая версия из серверного кеша."
        raise


@router.get("")
def list_pages(site_id: str, user: AuthUser, db: Session = Depends(get_db), refresh: bool = False):
    site = site_for(db, site_id)
    project, source, warning = read_project(db, site, refresh)
    result = [page_summary(p) for p in pages(project)]
    result.sort(key=lambda p: (not p["is_home"], p["title"].casefold(), p["slug"]))
    return {"pages": result, "total": len(result), "source": source, "warning": warning}


@router.get("/{key}")
def read_page(site_id: str, key: str, user: AuthUser, db: Session = Depends(get_db), refresh: bool = False):
    site = site_for(db, site_id)
    project, source, warning = read_project(db, site, refresh)
    return {**page_detail(find_page(project, key)), "source": source, "warning": warning}


def operation_result(operation, page=None):
    return {"id": operation.id, "status": operation.status, "error": operation.error,
            "requested_by": operation.requested_by, "updated_at": operation.updated_at,
            "page": page_detail(page) if page is not None else None}


def confirm(db, operation, remote, site):
    current = find_page(remote.project(), operation.page_key)
    if editable(current) == editable(operation.after_page):
        operation.status, operation.error = "confirmed", None
        if is_home(current):
            site.homepage_title = current.get("title") or ""
    else:
        operation.status, operation.error = "unknown", "Webdev пока не подтвердил изменения. Проверьте результат перед новой попыткой."
    db.commit()
    return operation_result(operation, current if operation.status == "confirmed" else None)


@router.get("/{key}/edits/{request_id}")
def check_edit(site_id: str, key: str, request_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    site = site_for(db, site_id)
    operation = db.scalar(select(models.ProjectPageEdit).where(models.ProjectPageEdit.id == str(request_id),
        models.ProjectPageEdit.site_id == site_id, models.ProjectPageEdit.page_key == key))
    if not operation:
        raise HTTPException(404, "Операция не найдена.")
    if operation.status not in {"pending", "unknown"}:
        return operation_result(operation)
    with remote_errors(), network_lock(db, site_id), Remote(db, site) as remote:
        return confirm(db, operation, remote, site)


@router.put("/{key}")
def save_page(site_id: str, key: str, payload: PageEdit, user: AuthUser, db: Session = Depends(get_db)):
    site = site_for(db, site_id)
    with remote_errors(), network_lock(db, site_id):
        operation = db.scalar(select(models.ProjectPageEdit).where(models.ProjectPageEdit.id == str(payload.request_id)))
        fingerprint = digest(payload.model_dump(mode="json"))
        if operation:
            if operation.site_id != site_id or operation.page_key != key or operation.fingerprint != fingerprint:
                raise HTTPException(409, "Идентификатор сохранения уже использован для других изменений.")
            return operation_result(operation)
        with Remote(db, site) as remote:
            current = find_page(remote.project(), key)
            if digest(current) != payload.revision:
                raise HTTPException(409, "Страница изменилась в Webdev. Скопируйте свои изменения и загрузите актуальную версию.")
            updated = {**deepcopy(current), "title": payload.title, "description": payload.description,
                       "content": payload.content, "updatedTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}
            operation = models.ProjectPageEdit(id=str(payload.request_id), site_id=site_id, page_key=key,
                requested_by=user["username"], fingerprint=fingerprint, before_page=current, after_page=updated,
                status="pending")
            db.add(operation)
            db.commit()  # Durable before the external write. Never retry an uncertain POST.
            page_id = updated["id"]
            outer_id = int(page_id) if str(page_id).isdigit() else page_id
            try:
                code, response = remote.request("POST", "/projects/update", {
                    "folder": site.name, "id": outer_id, "page": updated,
                    "initiator": get_settings().project_cache_username, "dateTime": updated["updatedTime"],
                })
                operation.response_status = code
                if isinstance(response, dict) and (response.get("success") is False or response.get("error")):
                    operation.status, operation.error = "failed", "Webdev отклонил сохранение. Проверьте страницу и повторите."
                    db.commit()
                    return operation_result(operation)
            except httpx.HTTPStatusError as error:
                operation.response_status = error.response.status_code
                operation.status = "failed" if error.response.status_code < 500 else "unknown"
                operation.error = f"Webdev вернул HTTP {error.response.status_code}. Проверьте результат перед повторным сохранением."
                db.commit()
                return operation_result(operation)
            except (httpx.RequestError, ValueError):
                operation.status, operation.error = "unknown", "Ответ Webdev не получен. Проверьте результат сохранения; повторная отправка не выполнялась."
                db.commit()
                return operation_result(operation)
            try:
                return confirm(db, operation, remote, site)
            except (httpx.HTTPError, ProjectCacheError, HTTPException):
                operation.status, operation.error = "unknown", "Изменения отправлены. Подтвердить результат пока не удалось."
                db.commit()
                return operation_result(operation)


class DraftContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: dict
    _valid_content = field_validator("content")(PageEdit.editor_document.__func__)


class AIContent(DraftContent):
    action: Literal["paragraphs", "headings", "emoji"]
    provider_id: str


def draft_result(draft):
    return {"id": draft.id, "action": draft.action, "status": draft.status, "error": draft.error,
            "input_content": draft.input_content, "result_content": draft.result_content, "created_at": draft.created_at}


@router.post("/{key}/interlink")
def generate_interlink(site_id: str, key: str, payload: DraftContent, user: AuthUser, db: Session = Depends(get_db)):
    from app.page_content_tools import interlink
    site = site_for(db, site_id)
    with remote_errors(), Remote(db, site) as remote:
        page = find_page(remote.project(), key)
    if is_home(page):
        raise HTTPException(422, "Перелинковка на главную доступна на внутренних страницах.")
    try:
        content, message, changed = interlink(payload.content, site.brand)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"content": content, "message": message, "changed": changed}


@router.post("/{key}/ai", status_code=202)
def generate_ai_draft(site_id: str, key: str, payload: AIContent, user: AuthUser, db: Session = Depends(get_db)):
    from app.page_content_tools import targets
    site = site_for(db, site_id)
    with remote_errors(), Remote(db, site) as remote:
        page = find_page(remote.project(), key)
    if not is_home(page):
        raise HTTPException(422, "Эта обработка доступна для главной страницы.")
    provider = db.get(models.AiProvider, payload.provider_id)
    if not provider or not provider.is_active or provider.provider_type != "gemini" or not provider.api_key:
        raise HTTPException(422, "Выберите активный Gemini-провайдер.")
    if not targets(payload.content, payload.action):
        raise HTTPException(422, "Нет подходящих блоков для выбранного действия.")
    row = models.ProjectPageDraft(site_id=site_id, page_key=key, requested_by=user["username"],
        provider_id=provider.id, action=payload.action, input_content=payload.content)
    db.add(row); db.flush()
    db.add(models.BackgroundJob(kind="project_page_ai", payload={"draft_id": row.id}))
    db.commit()
    return draft_result(row)


@router.get("/{key}/ai")
def list_ai_drafts(site_id: str, key: str, user: AuthUser, db: Session = Depends(get_db)):
    site_for(db, site_id)
    rows = db.scalars(select(models.ProjectPageDraft).where(models.ProjectPageDraft.site_id == site_id,
        models.ProjectPageDraft.page_key == key).order_by(models.ProjectPageDraft.created_at.desc()).limit(10)).all()
    return [{"id": r.id, "action": r.action, "status": r.status, "created_at": r.created_at} for r in rows]


@router.get("/{key}/ai/{draft_id}")
def read_ai_draft(site_id: str, key: str, draft_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site_for(db, site_id)
    row = db.scalar(select(models.ProjectPageDraft).where(models.ProjectPageDraft.id == draft_id,
        models.ProjectPageDraft.site_id == site_id, models.ProjectPageDraft.page_key == key))
    if not row:
        raise HTTPException(404, "Черновик не найден.")
    return draft_result(row)


@router.get("/{key}/history")
def page_history(site_id: str, key: str, user: AuthUser, db: Session = Depends(get_db)):
    site_for(db, site_id)
    rows = db.scalars(select(models.ProjectPageEdit).where(models.ProjectPageEdit.site_id == site_id,
        models.ProjectPageEdit.page_key == key, models.ProjectPageEdit.status == "confirmed")
        .order_by(models.ProjectPageEdit.created_at.desc()).limit(100)).all()
    return [{"id": r.id, "requested_by": r.requested_by, "created_at": r.created_at,
             "title": r.after_page.get("title") or "Без названия"} for r in rows]


@router.get("/{key}/history/{edit_id}")
def page_version(site_id: str, key: str, edit_id: UUID, user: AuthUser, db: Session = Depends(get_db), before: bool = False):
    site_for(db, site_id)
    row = db.scalar(select(models.ProjectPageEdit).where(models.ProjectPageEdit.id == str(edit_id),
        models.ProjectPageEdit.site_id == site_id, models.ProjectPageEdit.page_key == key,
        models.ProjectPageEdit.status == "confirmed"))
    if not row:
        raise HTTPException(404, "Версия не найдена.")
    return page_detail(row.before_page if before else row.after_page)
