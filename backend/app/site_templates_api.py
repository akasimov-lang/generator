"""Template drafts are independent of Webdev projects and never publish remotely."""
import base64
from datetime import datetime, timezone
import json
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from app.source_upload import extract_source_document, MAX_UPLOAD
from sqlalchemy import select, func
from sqlalchemy.orm import Session, defer

from app import models
from app.db import get_db
from app.security import AuthUser
from app.site_templates import TemplateRequest, TemplateEdit, build_archive, render
from app.template_design import art_svg, PALETTES
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID
from app.template_sources import excerpt, MAX_HTML

router = APIRouter(prefix="/site-templates", tags=["Site templates"])


def get_template(db, template_id):
    row = db.scalar(select(models.SiteTemplate).where(models.SiteTemplate.id == template_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Шаблон не найден")
    return row


def summary(row, competitors=None, has_html=False):
    return {"id": row.id, "brand": row.brand, "geo": row.geo, "language": row.language,
            "status": row.status, "phase": row.phase, "error": row.error,
            "revision": row.revision, "created_at": row.created_at, "updated_at": row.updated_at,
            "competitors": competitors or [], "has_html": has_html}


def detail(row):
    return {**summary(row,has_html=bool(row.html)), "request": row.request_data, "document": row.document, "html": row.html}


def save_collection(db, user, brand, geo, language, sources, provider_id=''):
    from app.template_knowledge_library import competitor_identity
    if not provider_id:
        provider_id=db.scalar(select(models.AiProvider.id).where(models.AiProvider.provider_type=='gemini',
            models.AiProvider.is_active.is_(True)).order_by(models.AiProvider.created_at)) or ''
    row=models.SiteTemplate(created_by_user_id=user['id'],brand=brand,geo=geo or 'PL',language=language or 'pl',
        status='sources_ready',phase='Конкуренты сохранены',request_data={
            'brand':brand,'geo':geo or 'PL','language':language or 'pl','ai_provider_id':provider_id,
            'collect_competitors':False,'uniqueness_scope':'brand_geo'})
    db.add(row);db.flush()
    collected=[]
    for source in sources:
        identity=competitor_identity(source.google_html,source.url)
        copied=models.TemplateSource(template_id=row.id,url=identity['url'],google_html=source.google_html,
            capture={**(getattr(source,'capture',None) or {}),'source':'manual_html','status':'google_ready','revision':0})
        db.add(copied);db.flush()
        collected.append({'source_id':copied.id,'url':identity['url'],'title':identity['title'],
            'origin':'manual','position':len(collected)+1,'status':'google_ready'})
    row.document={'research':{'sources':collected,'search_complete':True},'pipeline':{'stage':'research'}}
    return row


def enqueue(db, row, *, audit=False, stage="design"):
    from app.template_knowledge_library import remember_template_sources
    remember_template_sources(db, row)
    db.add(models.BackgroundJob(kind="site_template", payload={"template_id": row.id, "audit": audit, "stage": stage}))
    row.document = {**(row.document or {}), "pipeline": {**((row.document or {}).get("pipeline") or {}), "stage": stage}}
    row.status, row.phase, row.error = "queued", {"research": "Этап 1/3 · сбор конкурентов в очереди", "content": "Этап 2/3 · контент в очереди", "design": "Этап 3/3 · HTML в очереди"}[stage], None
    db.commit()


@router.get("")
def list_templates(user: AuthUser, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.SiteTemplate).options(defer(models.SiteTemplate.document),
        defer(models.SiteTemplate.html), defer(models.SiteTemplate.request_data))
        .order_by(models.SiteTemplate.created_at.desc())).all()
    from app.template_knowledge_library import competitor_identity
    sources={row.id:[] for row in rows}
    if sources:
        # Fetch only the head of saved HTML, not megabytes of article bodies.
        for template_id,url,capture,head in db.execute(select(models.TemplateSource.template_id,
            models.TemplateSource.url,models.TemplateSource.capture,func.substr(models.TemplateSource.google_html,1,64000))
            .where(models.TemplateSource.template_id.in_(sources),models.TemplateSource.google_html.is_not(None),models.TemplateSource.google_html!='')
            .order_by(models.TemplateSource.created_at)):
            if (capture or {}).get('status') not in {'google_ready','parsed'}:continue
            identity=competitor_identity(head,url)
            if identity not in sources[template_id]:sources[template_id].append(identity)
    generated=set(db.scalars(select(models.SiteTemplate.id).where(models.SiteTemplate.html.is_not(None),models.SiteTemplate.html!='')))
    return [summary(row,sources[row.id],row.id in generated) for row in rows]


class SourceDraftRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    revision: int = Field(ge=0)


class CreateTemplateRequest(TemplateRequest):
    brand: str = Field(default="Онлайн казино", min_length=1, max_length=160)

    @field_validator("brand", mode="before")
    @classmethod
    def generic_brand(cls, value):
        if isinstance(value, str) and value.strip().casefold() in {"", "общие ключи"}:
            return "Онлайн казино"
        return value

    source_drafts: list[SourceDraftRef] = Field(default_factory=list, max_length=10)


@router.post("", status_code=202)
def create_template(payload: CreateTemplateRequest, user: AuthUser, db: Session = Depends(get_db)):
    provider = db.get(models.AiProvider, payload.ai_provider_id)
    if not provider or not provider.is_active or provider.provider_type != "gemini" or not provider.api_key:
        raise HTTPException(422, "Добавьте активный Gemini-провайдер с API-ключом в разделе API Providers")
    if payload.collect_competitors:
        from app.services import get_dataforseo_provider
        try:
            get_dataforseo_provider(db)
        except ValueError:
            raise HTTPException(422, "Для анализа выдачи нужен DataForSEO. Подключите его или отключите поиск конкурентов.")
    lock_draft_owner(db, user)
    drafts = []
    if len({ref.id for ref in payload.source_drafts}) != len(payload.source_drafts):
        raise HTTPException(422, "Один черновик конкурента указан дважды.")
    for ref in payload.source_drafts:
        source = get_source_draft(db, user, str(ref.id))
        if source.capture.get("revision", 0) != ref.revision:
            raise HTTPException(409, "HTML конкурента изменился. Обновите форму перед созданием задачи.")
        drafts.append(source)
    row = models.SiteTemplate(created_by_user_id=user["id"], brand=payload.brand,
        geo=payload.geo.upper(), language=payload.language, request_data=payload.model_dump(exclude={"source_drafts"}))
    db.add(row)
    db.flush()
    entries = []
    for draft in drafts:
        if draft.google_html.strip() or draft.url.strip():
            source = models.TemplateSource(template_id=row.id, url=draft.url,
                google_html=draft.google_html, capture={**draft.capture, "revision": 0})
            db.add(source); db.flush()
            entries.append({"url": source.url, "title": source.url, "source_id": source.id,
                "position": len(entries) + 1, "origin": "manual_html"})
        db.delete(draft)
    if entries:
        seen = {item["url"] for item in entries if item["url"]}
        for url in payload.competitor_urls():
            if url not in seen and len(entries) < 30:
                entries.append({"url": url, "title": url, "position": len(entries) + 1, "origin": "manual"})
                seen.add(url)
        row.document = {"research": {"sources": entries, "search_complete": not payload.collect_competitors}}
    from app.template_knowledge import attach_sources
    attach_sources(db, row)
    enqueue(db, row, stage="research")
    return detail(row)


class SourceDraft(BaseModel):
    html: str = Field(default="", max_length=MAX_HTML)
    url: str = Field(default="", max_length=2000)
    revision: int = Field(default=0, ge=0)


class KnowledgeUpload(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    brand: str = Field(min_length=1,max_length=160)
    geo: str = Field(default='',max_length=2)
    html: str = Field(min_length=1,max_length=MAX_HTML)
    url: str = Field(default='',max_length=2000)
    filename: str = Field(default='',max_length=255)


class SaveCompetitorsRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    brand:str=Field(min_length=1,max_length=160)
    geo:str=Field(default='',max_length=2)
    language:str=Field(default='',max_length=40)
    ai_provider_id:str=Field(default='',max_length=36)
    source_drafts:list[SourceDraftRef]=Field(min_length=1,max_length=10)


@router.get('/knowledge/history')
def competitor_history(user:AuthUser,db:Session=Depends(get_db)):
    from app.template_knowledge_library import entries, listing, competitor_identity
    rows=entries(db)
    # Existing imported examples and new uploads share one history.
    return {'count':len(rows),'sources':rows,'scopes':listing(db)['scopes']}


@router.get('/knowledge/examples/{example_id}')
def competitor_example(example_id:str,user:AuthUser,db:Session=Depends(get_db)):
    from app.template_knowledge_library import entries
    # IDs are matched against the catalog; never accept an arbitrary file path.
    source=next((source for source in entries(db,html=True) if source['id']==example_id),None)
    if not source:raise HTTPException(404,'Пример не найден.')
    return source


@router.post('/knowledge/save-drafts',status_code=201)
def save_competitor_drafts(payload:SaveCompetitorsRequest,user:AuthUser,db:Session=Depends(get_db)):
    from app.template_knowledge_library import save, scope, competitor_identity
    lock_draft_owner(db,user)
    if len({ref.id for ref in payload.source_drafts})!=len(payload.source_drafts):
        raise HTTPException(422,'Один HTML указан дважды.')
    drafts=[]
    for ref in payload.source_drafts:
        source=get_source_draft(db,user,str(ref.id))
        if source.capture.get('revision',0)!=ref.revision:
            raise HTTPException(409,'HTML конкурента изменился. Обновите форму перед сохранением.')
        if source.capture.get('status')!='google_ready' or not (source.google_html or '').strip():
            raise HTTPException(422,'Добавьте корректный HTML главной страницы конкурента.')
        drafts.append(source)
    try:
        name,_,country=scope(payload.brand,payload.geo)
        saved=[save(db,name,country,source.google_html,source.url,'Загруженный конкурент.html',user['id'],
            commit=False,allow_missing_general_url=True) for source in drafts]
        collection=save_collection(db,user,name,payload.geo,payload.language,drafts,payload.ai_provider_id)
        for source in drafts:db.delete(source)
        db.commit()
    except ValueError as error:
        db.rollback();raise HTTPException(422,str(error))
    return {'brand':name,'geo':country,'saved':sum(not source['duplicate'] for source in saved),
            'duplicates':sum(source['duplicate'] for source in saved),'sources':saved,'collection':detail(collection)}


@router.get('/knowledge')
def knowledge_library(user: AuthUser, brand: str | None = None, geo: str = '', db: Session = Depends(get_db)):
    from app.template_knowledge_library import listing
    try:return listing(db,brand,geo)
    except ValueError as error:raise HTTPException(422,str(error))


@router.post('/knowledge',status_code=201)
def upload_knowledge(payload: KnowledgeUpload,user: AuthUser,db: Session = Depends(get_db)):
    from app.template_knowledge_library import save, listing
    try:
        source=save(db,payload.brand,payload.geo,payload.html,payload.url,payload.filename,user['id'],commit=False)
        if not source['duplicate']:
            from types import SimpleNamespace
            stored=db.get(models.TemplateKnowledgeExample,source['id'])
            languages={'CZ':'cs','PL':'pl','DE':'de','AT':'de','FR':'fr','ES':'es','IT':'it','PT':'pt'}
            save_collection(db,user,source['brand'],payload.geo,languages.get(payload.geo.upper(),'en'),
                [SimpleNamespace(url=stored.url,google_html=stored.html,capture={})])
        db.commit()
        return {'source':source,**listing(db,payload.brand,payload.geo)}
    except ValueError as error:
        db.rollback();raise HTTPException(422,str(error))


def suggested_brand(html):
    from html.parser import HTMLParser

    class Metadata(HTMLParser):
        def __init__(self):
            super().__init__()
            self.site_name = ""
            self.title = []
            self.in_title = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "title":
                self.in_title = True
            if tag == "meta" and (attrs.get("property") or attrs.get("name") or "").lower() in {"og:site_name", "application-name"}:
                self.site_name = self.site_name or attrs.get("content", "")

        def handle_endtag(self, tag):
            if tag == "title":
                self.in_title = False

        def handle_data(self, data):
            if self.in_title:
                self.title.append(data)

    parser = Metadata()
    parser.feed(html or "")
    from app.site_brands import detect_brand, GENERAL
    from types import SimpleNamespace
    # Several casino brands or generic search terms describe a generic site.
    title = " ".join(parser.title)
    brand = detect_brand(SimpleNamespace(homepage_title=title or parser.site_name, name="", cache_canon=""))
    if brand != GENERAL:
        return brand
    return "Онлайн казино"


def source_detail(source):
    from app.template_knowledge_library import competitor_identity
    identity = competitor_identity(source.google_html or "", source.url or "")
    return {"id": source.id, "url": source.url, "html": source.google_html or "",
            "suggested_brand": suggested_brand(source.google_html),
            "capture": source.capture, "revision": source.capture.get("revision", 0),
            "created_at": source.created_at, "title": identity["title"], "display_url": identity["url"],
            "updated_at": source.updated_at}


def lock_draft_owner(db, user):
    db.scalar(select(models.User.id).where(models.User.id == user["id"]).with_for_update())


def get_source_draft(db, user, source_id):
    source = db.scalar(select(models.TemplateSourceDraft).where(models.TemplateSourceDraft.id == source_id,
        models.TemplateSourceDraft.user_id == user["id"]).with_for_update())
    if not source:
        raise HTTPException(404, "Черновик не найден. Возможно, он уже добавлен в созданную задачу.")
    return source


@router.post("/source-document")
async def read_source_document(request: Request, user: AuthUser, extension: str):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(422, "Файл превышает 2 МБ. Выберите файл меньшего размера.")
    try:
        html = await run_in_threadpool(extract_source_document, bytes(data), extension.lower())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"html": html}


@router.get("/source-drafts")
def list_source_drafts(user: AuthUser, db: Session = Depends(get_db)):
    return [source_detail(row) for row in db.scalars(select(models.TemplateSourceDraft).where(
        models.TemplateSourceDraft.user_id == user["id"]).order_by(models.TemplateSourceDraft.created_at)).all()]


@router.post("/source-drafts", status_code=201)
def create_source_draft(payload: SourceDraft, user: AuthUser, db: Session = Depends(get_db)):
    lock_draft_owner(db, user)
    ids = db.scalars(select(models.TemplateSourceDraft.id).where(models.TemplateSourceDraft.user_id == user["id"])).all()
    if len(ids) >= 10:
        raise HTTPException(422, "Можно добавить до 10 HTML конкурентов.")
    source = models.TemplateSourceDraft(user_id=user["id"], url="", google_html="", capture={})
    db.add(source); db.flush()
    return save_source(db, None, source, payload)


@router.put("/source-drafts/{source_id}")
def update_source_draft(source_id: str, payload: SourceDraft, user: AuthUser, db: Session = Depends(get_db)):
    lock_draft_owner(db, user)
    return save_source(db, None, get_source_draft(db, user, source_id), payload)


@router.delete("/source-drafts/{source_id}")
def delete_source_draft(source_id: str, revision: int, user: AuthUser, db: Session = Depends(get_db)):
    lock_draft_owner(db, user)
    source = get_source_draft(db, user, source_id)
    if source.capture.get("revision", 0) != revision:
        raise HTTPException(409, "HTML изменён в другой вкладке. Обновите список.")
    db.delete(source)
    db.commit()
    return {"deleted": True}


@router.get("/{template_id}")
def read_template(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    return detail(get_template(db, template_id))


def editable_sources(row):
    if row.status in {"queued", "generating"}:
        raise HTTPException(409, "Дождитесь завершения текущего этапа перед изменением источников.")


def save_source(db, row, source, payload):
    if len(payload.html.encode("utf-8")) > MAX_HTML:
        raise HTTPException(413, "HTML превышает 2 МБ")
    url = payload.url.strip()
    if url:
        try:
            parsed = TemplateRequest(brand="Draft", geo="DE", ai_provider_id="draft", competitors=url).competitor_urls()
            if len(parsed) != 1: raise ValueError()
            url = parsed[0]
        except ValueError:
            raise HTTPException(422, "Укажите один HTTP(S)-адрес конкурента или оставьте адрес пустым.")
    if source.capture.get("revision", 0) != payload.revision:
        raise HTTPException(409, "HTML изменён в другой вкладке. Скопируйте свою версию и обновите страницу.")
    source.url, source.google_html = url, payload.html
    capture = {**source.capture, "source": "manual_html", "revision": payload.revision + 1,
               "saved_at": datetime.now(timezone.utc).isoformat(), "status": "empty", "error": None}
    if payload.html.strip():
        try:
            excerpt(payload.html)
            capture["status"] = "google_ready"
        except ValueError as error:
            capture["status"], capture["error"] = "invalid_html", str(error)
    source.capture = capture
    if row is not None:
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
    if len(sources) >= 10: raise HTTPException(422, "Можно добавить до 10 HTML конкурентов")
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


@router.delete("/{template_id}/sources/{source_id}")
def delete_source(template_id: str, source_id: str, revision: int, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id)
    editable_sources(row)
    source = db.scalar(select(models.TemplateSource).where(models.TemplateSource.id == source_id,
                       models.TemplateSource.template_id == template_id).with_for_update())
    if not source:
        raise HTTPException(404, "Источник не найден")
    if source.capture.get("revision", 0) != revision:
        raise HTTPException(409, "HTML изменён в другой вкладке. Обновите список.")
    document = dict(row.document or {})
    document["sources_changed"] = True
    if document.get("research"):
        document["research"] = {**document["research"], "analysis": None,
            "sources": [item for item in document["research"].get("sources", []) if item.get("source_id") != source_id]}
    row.document = document
    db.delete(source)
    db.commit()
    return {"deleted": True}


@router.post("/{template_id}/generate-content", status_code=202)
def generate_content(template_id: str, user: AuthUser, db: Session = Depends(get_db)):
    row = get_template(db, template_id); editable_sources(row)
    if not row.request_data.get('ai_provider_id'):
        provider=db.scalar(select(models.AiProvider).where(models.AiProvider.provider_type=='gemini',models.AiProvider.is_active.is_(True)))
        if not provider or not provider.api_key:raise HTTPException(422,'Подключите Gemini в API Providers перед генерацией шаблона.')
        row.request_data={**row.request_data,'ai_provider_id':provider.id}
    from app.template_knowledge import attach_sources, source_excerpt
    attach_sources(db, row)
    sources = db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id == template_id)).all()
    entries = []
    for source in sources:
        if not source.google_html: continue
        try:
            evidence = source_excerpt(source)
        except ValueError:
            continue
        entries.append({"url": source.url, "source_id": source.id, "position": len(entries) + 1,
                        "origin": "knowledge_base" if source.capture.get("knowledge_id") else "google",
                        "status": "fetched", **evidence})
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
            stage=((row.document or {}).get("pipeline") or {}).get("stage") or ("design" if (row.document or {}).get("design") else "content"))
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


from app.template_bundle import assets, downloadable_html


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
