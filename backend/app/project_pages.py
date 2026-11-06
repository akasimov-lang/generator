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
    slug: str | None = Field(default=None, max_length=240)

    @field_validator("slug")
    @classmethod
    def page_path(cls, value):
        if value is None: return value
        from urllib.parse import urlsplit, unquote
        value = value.strip()
        parsed = urlsplit(value)
        if not value.startswith("/") or value.startswith("//") or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in value or any(x in {".", ".."} for x in unquote(value).split("/")):
            raise ValueError("Укажите относительный URL страницы без протокола и параметров.")
        return value

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


def shortcode_catalog(project):
    definitions=project.get('shortcodes')
    known={str(row.get('name') or '').removesuffix('.hbs') for row in definitions or [] if isinstance(row,dict)} if isinstance(definitions,list) else set()
    uses={};used_pages={}
    for page in pages(project):
        content=page.get('content')
        blocks=content.get('blocks',[]) if isinstance(content,dict) else []
        for block in blocks if isinstance(blocks,list) else []:
            if not isinstance(block,dict) or block.get('type')!='shortcode':continue
            data=block.get('data')
            value=data.get('shortcode') if isinstance(data,dict) else data
            if not isinstance(value,str) or not value.strip():continue
            name=value.strip().removesuffix('.hbs')
            uses[name]=uses.get(name,0)+1
            used_pages.setdefault(name,set()).add(page_key(page))
    return [{'name':name,'uses_on_site':uses.get(name,0),'pages_count':len(used_pages.get(name,[])),
             'defined':name in known if isinstance(definitions,list) else None}
            for name in sorted((known|set(uses))-{''})]


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


@router.get("/interlinking")
def interlinking(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site = site_for(db, site_id)
    if user.get("allowed_site_ids") is not None and site_id not in user["allowed_site_ids"]:
        raise HTTPException(404, "Проект недоступен.")
    from app.project_interlinking import interlinking_status
    project, source, warning = read_project(db, site, refresh=True)
    result = interlinking_status(project, (project.get("settings") or {}).get("canon") or site.cache_canon or site.base_url)
    if site.site_type == "general" or not site.site_type and (not site.brand or site.brand.strip().casefold() == "общие ключи"):
        from app.showcase_brands import showcase_brands
        result["showcase"] = showcase_brands(project)
    if warning:
        result.update(complete=False, message="Не удалось подтвердить актуальную перелинковку в Webdev.")
    return {**result, "source": source, "warning": warning,
            "checked_at": datetime.now(timezone.utc).isoformat()}


class GenerationAnchorsEdit(BaseModel):
    anchors: str | list[str]


@router.get("/generation-anchors")
def generation_anchors(site_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site = site_for(db, site_id)
    if user.get("allowed_site_ids") is not None and site_id not in user["allowed_site_ids"]:
        raise HTTPException(404, "Проект недоступен.")
    from app.generation_anchors import settings
    return settings(db, site)


@router.put("/generation-anchors")
def edit_generation_anchors(site_id: str, payload: GenerationAnchorsEdit, user: AuthUser, db: Session = Depends(get_db)):
    site = site_for(db, site_id)
    if user.get("allowed_site_ids") is not None and site_id not in user["allowed_site_ids"]:
        raise HTTPException(404, "Проект недоступен.")
    from app.generation_anchors import save_settings
    try:
        return save_settings(db, site, payload.anchors)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/{key}")
def read_page(site_id: str, key: str, user: AuthUser, db: Session = Depends(get_db), refresh: bool = False):
    site = site_for(db, site_id)
    project, source, warning = read_project(db, site, refresh)
    return {**page_detail(find_page(project, key)), "source": source, "warning": warning,
            "shortcodes": shortcode_catalog(project)}


def operation_result(operation, page=None):
    if page is None and operation.status == "confirmed":
        page = operation.after_page
    return {"id": operation.id, "status": operation.status, "error": operation.error,
            "requested_by": operation.requested_by, "updated_at": operation.updated_at,
            "page": page_detail(page) if page is not None else None}


def confirm(db, operation, remote, site):
    project = remote.project()
    if operation.before_page.get("slug") != operation.after_page.get("slug"):
        matches = [page for page in pages(project) if str(page.get("id")) == str(operation.after_page.get("id"))]
        if len(matches) != 1:
            raise HTTPException(409, "Не удалось однозначно подтвердить страницу после изменения URL.")
        current = matches[0]
    else:
        current = find_page(project, operation.page_key)
    if (editable(current) == editable(operation.after_page)
            and current.get("slug") == operation.after_page.get("slug")
            and current.get("updatedTime") == operation.after_page.get("updatedTime")
            and current.get("publishedTime") == operation.after_page.get("publishedTime")):
        operation.status, operation.error = "confirmed", None
        from app.project_page_autolink import saved_page
        saved_page(db, site, current)
        old_slug = operation.before_page.get("slug")
        if old_slug != current.get("slug"):
            from app import network_sitemap
            network_sitemap.queue(db, site, operation.id, operation.requested_by, manual=True)
            for item in db.scalars(select(models.ContentItem).where(models.ContentItem.site_id == site.id, models.ContentItem.slug == old_slug)):
                item.slug = current["slug"]
                if item.published_url:
                    from urllib.parse import urlsplit, urlunsplit
                    url = urlsplit(item.published_url)
                    item.published_url = urlunsplit((url.scheme,url.netloc,current["slug"],"",""))
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
            project = remote.project()
            current = find_page(project, key)
            if digest(current) != payload.revision:
                raise HTTPException(409, "Страница изменилась в Webdev. Скопируйте свои изменения и загрузите актуальную версию.")
            next_slug = payload.slug if payload.slug is not None else current.get("slug")
            if next_slug != current.get("slug"):
                if is_home(current) or next_slug in {"", "/"}:
                    raise HTTPException(409, "Адрес главной страницы нельзя менять здесь.")
                if any(str(page.get("slug") or "/").rstrip("/") == next_slug.rstrip("/") and str(page.get("id")) != str(current["id"]) for page in pages(project)):
                    raise HTTPException(409, "Страница с таким URL уже существует.")
            if next_slug == current.get("slug") and editable(current) == {"title": payload.title, "description": payload.description, "content": payload.content}:
                # A retry or an unchanged form is not a content update. Keep both
                # remote dates and record the request without another Webdev write.
                operation = models.ProjectPageEdit(id=str(payload.request_id), site_id=site_id, page_key=key,
                    requested_by=user["username"], fingerprint=fingerprint, before_page=current,
                    after_page=deepcopy(current), status="confirmed")
                db.add(operation)
                db.commit()
                return operation_result(operation, current)
            from app.page_backups import ensure_backup, PageBackupError
            try:
                ensure_backup(db, remote, site, project, current,
                              actor=user["username"], operation=f"save:{payload.request_id}",
                              defer_verification=bool(db.info.get('pilot_defer_backup')))
            except PageBackupError as error:
                raise HTTPException(502, str(error)) from error
            # A backup can take time. Never overwrite a concurrent external edit.
            latest = find_page(remote.project(), key)
            if digest(latest) != payload.revision:
                raise HTTPException(409, "Страница изменилась во время создания бекапа. Загрузите актуальную версию.")
            updated = {**deepcopy(current), "slug": next_slug, "title": payload.title, "description": payload.description,
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
    action: Literal["paragraphs", "headings", "emoji", "append_1", "append_2", "append_3", "meta_headings", "full_title_h1", "full_title_headings", "trim_50", "trim_99"]
    provider_id: str | None = None
    title: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=10000)


def draft_result(draft):
    return {"id": draft.id, "action": draft.action, "status": draft.status, "error": draft.error,
            "input_content": draft.input_content, "result_content": draft.result_content, "input_metadata":draft.input_metadata, "result_metadata":draft.result_metadata, "created_at": draft.created_at}


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
    from app.page_content_tools import targets, validate_heading_scope
    site = site_for(db, site_id)
    with remote_errors(), Remote(db, site) as remote:
        project = remote.project()
        page = find_page(project, key)
    if not is_home(page):
        raise HTTPException(422, "Эта обработка доступна для главной страницы.")
    provider = db.get(models.AiProvider, payload.provider_id) if payload.provider_id else None
    if payload.action not in {"trim_50","trim_99"} and (not provider or not provider.is_active or provider.provider_type != "gemini" or not provider.api_key):
        raise HTTPException(422, "Выберите активный Gemini-провайдер.")
    try:
        eligible = targets(payload.content, "headings" if payload.action=="meta_headings" else payload.action)
        mode = validate_heading_scope(project, key, payload.content, payload.action)
        if mode and not (payload.title if payload.title is not None else page.get('title') or '').strip():
            raise ValueError('Для полного переписывания нужен исходный Title страницы.')
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not eligible and payload.action!="meta_headings":
        raise HTTPException(422, "Нет подходящих блоков для выбранного действия.")
    row = models.ProjectPageDraft(site_id=site_id, page_key=key, requested_by=user["username"],
        provider_id=provider.id if provider else None, action=payload.action, input_content=payload.content,
        input_metadata={"title": payload.title if payload.title is not None else page.get("title") or "",
                        "description":payload.description if payload.description is not None else page.get("description") or "",
                        **({'title_rewrite_mode': mode} if mode else {})})
    db.add(row); db.flush()
    if payload.action in {'headings','meta_headings','full_title_h1','full_title_headings'}:
        from app import short_h1
        from app.full_heading_rewrite import all_targets
        if sum(item['level']==1 for item in all_targets(payload.content))==1:short_h1.select_for_draft(row)
    db.add(models.BackgroundJob(kind="project_page_ai", payload={"draft_id": row.id}))
    db.commit()
    return draft_result(row)


@router.get("/{key}/ai")
def list_ai_drafts(site_id: str, key: str, user: AuthUser, db: Session = Depends(get_db)):
    site_for(db, site_id)
    rows = db.scalars(select(models.ProjectPageDraft).where(models.ProjectPageDraft.site_id == site_id,
        models.ProjectPageDraft.page_key == key,
        models.ProjectPageDraft.action != "manual_save").order_by(models.ProjectPageDraft.created_at.desc()).limit(10)).all()
    return [{"id": r.id, "action": r.action, "status": r.status, "created_at": r.created_at} for r in rows]


@router.get("/{key}/ai/{draft_id}")
def read_ai_draft(site_id: str, key: str, draft_id: str, user: AuthUser, db: Session = Depends(get_db)):
    site_for(db, site_id)
    row = db.scalar(select(models.ProjectPageDraft).where(models.ProjectPageDraft.id == draft_id,
        models.ProjectPageDraft.site_id == site_id, models.ProjectPageDraft.page_key == key,
        models.ProjectPageDraft.action != "manual_save"))
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


from app.page_editor_drafts import router as editor_drafts_router
router.include_router(editor_drafts_router)
