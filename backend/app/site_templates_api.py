"""Template drafts are independent of Webdev projects and never publish remotely."""
import base64
from datetime import datetime, timezone
import json
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from app import models
from app.db import get_db
from app.security import AuthUser
from app.site_templates import TemplateRequest, TemplateEdit, build_archive, render
from app.template_design import art_svg, PALETTES
from pydantic import BaseModel, Field
from app.template_sources import excerpt, MAX_HTML

router = APIRouter(prefix="/site-templates", tags=["Site templates"])


def get_template(db, template_id):
    row = db.scalar(select(models.SiteTemplate).where(models.SiteTemplate.id == template_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Шаблон не найден")
    return row


def summary(row):
    return {"id": row.id, "brand": row.brand, "geo": row.geo, "language": row.language,
            "status": row.status, "phase": row.phase, "error": row.error,
            "revision": row.revision, "created_at": row.created_at, "updated_at": row.updated_at}


def detail(row):
    return {**summary(row), "request": row.request_data, "document": row.document, "html": row.html}


def enqueue(db, row, *, audit=False, stage="design"):
    db.add(models.BackgroundJob(kind="site_template", payload={"template_id": row.id, "audit": audit, "stage": stage}))
    row.status, row.phase, row.error = "queued", "В очереди", None
    db.commit()


@router.get("")
def list_templates(user: AuthUser, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.SiteTemplate).options(defer(models.SiteTemplate.document),
        defer(models.SiteTemplate.html), defer(models.SiteTemplate.request_data))
        .order_by(models.SiteTemplate.created_at.desc())).all()
    return [summary(row) for row in rows]


@router.post("", status_code=202)
def create_template(payload: TemplateRequest, user: AuthUser, db: Session = Depends(get_db)):
    provider = db.get(models.AiProvider, payload.ai_provider_id)
    if not provider or not provider.is_active or provider.provider_type != "gemini" or not provider.api_key:
        raise HTTPException(422, "Добавьте активный Gemini-провайдер с API-ключом в разделе API Providers")
    if payload.collect_competitors:
        from app.services import get_dataforseo_provider
        try:
            get_dataforseo_provider(db)
        except ValueError:
            raise HTTPException(422, "Для анализа выдачи нужен DataForSEO. Подключите его или отключите поиск конкурентов.")
    row = models.SiteTemplate(created_by_user_id=user["id"], brand=payload.brand,
        geo=payload.geo.upper(), language=payload.language, request_data=payload.model_dump())
    db.add(row)
    db.flush()
    enqueue(db, row, stage="content")
    return detail(row)


@router.get("/{template_id}")
def read_template(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    return detail(get_template(db, template_id))


class SourceDraft(BaseModel):
    html: str = Field(default="", max_length=MAX_HTML)
    url: str = Field(default="", max_length=2000)
    revision: int = Field(default=0, ge=0)


def source_detail(source):
    return {"id": source.id, "url": source.url, "html": source.google_html or "",
            "capture": source.capture, "revision": source.capture.get("revision", 0),
            "updated_at": source.updated_at}


def editable_sources(row):
    if row.status in {"queued", "generating"}:
        raise HTTPException(409, "Дождитесь завершения текущего этапа перед изменением источников.")


def save_source(db, row, source, payload):
    if len(payload.html.encode("utf-8")) > MAX_HTML:
        raise HTTPException(413, "HTML превышает 2 МБ")
    url = payload.url.strip()
    if url:
        try:
            parsed = TemplateRequest(brand=row.brand, geo=row.geo, ai_provider_id=row.request_data["ai_provider_id"], competitors=url).competitor_urls()
            if len(parsed) != 1: raise ValueError()
            url = parsed[0]
        except ValueError:
            raise HTTPException(422, "Укажите один HTTP(S)-адрес конкурента или оставьте адрес пустым.")
    if source.capture.get("revision", 0) != payload.revision:
        raise HTTPException(409, "HTML изменён в другой вкладке. Скопируйте свою версию и обновите страницу.")
    source.url, source.google_html = url, payload.html
    capture = {**source.capture, "source": "google_manual", "revision": payload.revision + 1,
               "saved_at": datetime.now(timezone.utc).isoformat(), "status": "empty", "error": None}
    if payload.html.strip():
        try:
            excerpt(payload.html)
            capture["status"] = "google_ready"
        except ValueError as error:
            capture["status"], capture["error"] = "invalid_html", str(error)
    source.capture = capture
    document = dict(row.document or {})
    document["sources_changed"] = True
    if document.get("research"):
        document["research"] = {**document["research"], "analysis": None}
    row.document = document
    db.commit()
    return source_detail(source)


@router.get("/{template_id}/sources")
def list_sources(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    get_template(db, template_id)
    return [source_detail(source) for source in db.scalars(select(models.TemplateSource).where(
        models.TemplateSource.template_id == template_id).order_by(models.TemplateSource.created_at)).all()]


@router.post("/{template_id}/sources", status_code=201)
def add_source(template_id: str, payload: SourceDraft, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id); editable_sources(row)
    sources = db.scalars(select(models.TemplateSource.id).where(models.TemplateSource.template_id == template_id)).all()
    if len(sources) >= 30: raise HTTPException(422, "Можно добавить до 30 конкурентов")
    source = models.TemplateSource(template_id=template_id, url="", capture={})
    db.add(source); db.flush()
    return save_source(db, row, source, payload)


@router.put("/{template_id}/sources/{source_id}")
def update_source(template_id: str, source_id: str, payload: SourceDraft, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id); editable_sources(row)
    source = db.scalar(select(models.TemplateSource).where(models.TemplateSource.id == source_id,
                      models.TemplateSource.template_id == template_id).with_for_update())
    if not source: raise HTTPException(404, "Источник не найден")
    return save_source(db, row, source, payload)


@router.post("/{template_id}/generate-content", status_code=202)
def generate_content(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id); editable_sources(row)
    sources = db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id == template_id)).all()
    entries = []
    for source in sources:
        if not source.google_html: continue
        try:
            evidence = excerpt(source.google_html)
        except ValueError:
            continue
        entries.append({"url": source.url, "source_id": source.id, "position": len(entries) + 1,
                        "origin": "google", "status": "fetched", **evidence})
    if not entries:
        raise HTTPException(422, "Сначала добавьте HTML из Google хотя бы для одного конкурента.")
    row.document = {"research": {"query": "HTML конкурентов из Google", "sources": entries}, "pipeline": {"stage": "content"}}
    row.html = None
    enqueue(db, row, stage="content")
    return detail(row)


@router.post("/{template_id}/generate-design", status_code=202)
def generate_design(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id)
    if row.status != "content_ready" or not (row.document or {}).get("content"):
        raise HTTPException(409, "Сначала завершите генерацию текста")
    if row.document.get("sources_changed"):
        raise HTTPException(409, "Источники изменились. Сначала обновите текст по сохранённому HTML.")
    enqueue(db, row, stage="design")
    return detail(row)


@router.post("/{template_id}/retry", status_code=202)
def retry_template(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id)
    if row.status != "failed":
        raise HTTPException(409, "Повтор доступен после ошибки генерации")
    enqueue(db, row, audit=bool((row.document or {}).get("edited") and (row.document or {}).get("design")),
            stage="design" if (row.document or {}).get("design") else "content")
    return detail(row)


@router.put("/{template_id}", status_code=202)
def edit_template(template_id: str, payload: TemplateEdit, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id)
    if row.status == "content_ready":
        if payload.revision != row.revision:
            raise HTTPException(409, "Текст изменён в другой вкладке. Обновите страницу.")
        row.document = {**row.document, "content": payload.content.model_dump(), "menu": [item.model_dump() for item in payload.menu]}
        row.revision += 1
        db.commit()
        return detail(row)
    if row.status not in {"ready", "failed"} or not (row.document or {}).get("design"):
        raise HTTPException(409, "Дождитесь завершения генерации")
    if payload.revision != row.revision:
        raise HTTPException(409, "Шаблон изменён в другой вкладке. Откройте его заново перед редактированием.")
    document = {**row.document, "content": payload.content.model_dump(),
                "menu": [item.model_dump() for item in payload.menu], "edited": True, "design_status": "planned"}
    try:
        html = render(row, document)
    except ValueError as error:
        raise HTTPException(422, str(error))
    row.document, row.html = document, html
    row.revision += 1
    enqueue(db, row, audit=True)
    return detail(row)


def assets(row):
    design = row.document["design"]
    accent = PALETTES[design["palette"]][5 if design["hero"] == "feature_billboard" else 4]
    result = {"assets/hero.svg": art_svg(row.document["design"]["visual_style"]).replace("currentColor", accent)}
    from app.template_phones import frame_svg, FRAMES
    media = row.document.get("brand_media") or {}
    for i, screen in enumerate(media.get("screens", [])):
        frame = media.get("frames", [FRAMES[0][0]] * len(media["screens"]))[i]
        result[f"assets/phone-{i+1}.svg"] = frame_svg(frame, screen)
    if media.get("logo"):
        result["assets/brand-logo.png"] = base64.b64decode(media["logo"].split(",", 1)[1])
    from app.template_asset_library import exported_assets
    result.update(exported_assets(row.document))
    return result


def downloadable_html(row):
    inline = art_svg(row.document["design"]["visual_style"])
    html = row.html.replace(inline, '<img src="assets/hero.svg" alt="" width="600" height="400" decoding="async">').replace(
        ".art svg{", ".art img{object-fit:contain;").replace(".composition-art svg{", ".composition-art img{")
    if row.document.get("generated_css"):
        html = row.html  # Preserve the generated currentColor instead of a preset palette.
    for path, image in assets(row).items():
        if path.startswith("assets/phone-"):
            encoded = "data:image/svg+xml;base64," + base64.b64encode(image.encode()).decode()
            html = html.replace(encoded, path)
    logo = (row.document.get("brand_media") or {}).get("logo")
    if logo:
        html = html.replace(logo, "assets/brand-logo.png")
    from app.template_asset_library import externalize
    return externalize(html, row.document)


@router.get("/{template_id}/download/{kind}")
def download(template_id: str, kind: str, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id)
    if row.status != "ready":
        raise HTTPException(409, "Скачивание доступно после прохождения проверок")
    if kind == "html":
        data, filename, mime = downloadable_html(row).encode(), "index.html", "text/html;charset=utf-8"
    elif kind == "images":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, image in assets(row).items():
                archive.writestr(path, image)
        data, filename, mime = output.getvalue(), "images.zip", "application/zip"
    elif kind == "bundle":
        # Self-contained HTML plus editable document and audit screenshots.
        data, filename, mime = build_archive(row), "template.zip", "application/zip"
    else:
        raise HTTPException(404, "Неизвестный формат скачивания")
    return {"filename": filename, "mime": mime, "base64": base64.b64encode(data).decode()}
