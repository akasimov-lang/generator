import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import (
    AiProviderCreate,
    AiProviderResponse,
    CompetitorQueriesUpdate,
    CompetitorResearchResponse,
    ContentItemResponse,
    ContentUpdate,
    GenerationTaskCreate,
    GenerationTaskResponse,
    LoginRequest,
    PasswordChange,
    PublicationCampaignResponse,
    PublicationCampaignUpdate,
    PublicationLogResponse,
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    PublicationCampaignCreate,
    SectionCreate,
    SectionResponse,
    SiteCreate,
    SiteOverviewResponse,
    SitePublicationCampaignCreate,
    SiteResponse,
    TaskDetailsResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.security import AdminUser, AuthUser, create_token, hash_password, verify_password
from app.services import (
    BASE_PROMPT_TEMPLATE_NAME,
    approve_and_schedule_item,
    build_competitor_brief_for_item,
    collect_competitor_serp_for_item,
    count_words,
    create_generation_task,
    ensure_base_prompt_template,
    ensure_default_prompt_template,
    ensure_competitor_queries,
    fetch_competitor_pages_for_item,
    get_dashboard,
    regenerate_competitor_queries,
    replace_competitor_queries,
    schedule_campaign,
    update_campaign_status,
    validate_content_for_publication,
    validate_ai_provider_key,
)
from app.worker import collect_competitor_research_job, generate_content_item_job, generate_task_content_job

router = APIRouter()


def _active_admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(models.User).where(models.User.is_admin.is_(True), models.User.is_active.is_(True))) or 0


def _get_site_or_404(db: Session, site_id: str) -> models.Site:
    site = db.get(models.Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


def _get_section_for_site(db: Session, site_id: str, section_id: str) -> models.Section:
    section = db.get(models.Section, section_id)
    if not section or section.site_id != site_id:
        raise HTTPException(status_code=400, detail="Menu item does not belong to this site")
    return section


def _validate_task_topics(payload: GenerationTaskCreate) -> None:
    clean_topics = [topic.strip() for topic in payload.topics if topic.strip()]
    if not clean_topics:
        raise HTTPException(status_code=400, detail="Add at least one topic")
    if len(clean_topics) > 30:
        raise HTTPException(status_code=400, detail="A generation task can include up to 30 topics")


def _prompt_template_response(prompt: models.PromptTemplate, site: models.Site | None, used_by_projects: int) -> dict:
    return {
        "id": prompt.id,
        "site_id": prompt.site_id,
        "name": prompt.name,
        "content": prompt.content,
        "is_default": bool(site and site.default_prompt_template_id == prompt.id),
        "used_by_projects": used_by_projects,
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }


def _list_global_prompt_templates(db: Session, site: models.Site | None = None) -> list[dict]:
    prompts = db.scalars(
        select(models.PromptTemplate)
        .where(models.PromptTemplate.name != BASE_PROMPT_TEMPLATE_NAME)
        .order_by(models.PromptTemplate.created_at.asc())
    ).all()
    used_rows = db.execute(
        select(models.Site.default_prompt_template_id, func.count(models.Site.id))
        .where(models.Site.default_prompt_template_id.is_not(None))
        .group_by(models.Site.default_prompt_template_id)
    ).all()
    used_counts = {prompt_id: count for prompt_id, count in used_rows}
    rows = [_prompt_template_response(prompt, site, used_counts.get(prompt.id, 0)) for prompt in prompts]
    return sorted(rows, key=lambda row: (not row["is_default"], row["name"].lower()))


def _competitor_research_response(db: Session, item: models.ContentItem) -> dict:
    queries = db.scalars(
        select(models.CompetitorQuery)
        .where(models.CompetitorQuery.content_item_id == item.id)
        .order_by(models.CompetitorQuery.position.asc())
    ).all()
    results = db.scalars(
        select(models.CompetitorResult)
        .where(models.CompetitorResult.content_item_id == item.id)
        .order_by(models.CompetitorResult.query_text.asc(), models.CompetitorResult.position.asc())
    ).all()
    pages = db.scalars(
        select(models.CompetitorPage)
        .where(models.CompetitorPage.content_item_id == item.id)
        .order_by(models.CompetitorPage.created_at.desc())
    ).all()
    return {
        "content_item_id": item.id,
        "status": item.competitor_research_status,
        "progress": 100 if item.competitor_brief or item.competitor_research_status == "brief_ready" else item.competitor_research_progress,
        "error": item.competitor_research_error,
        "brief": item.competitor_brief,
        "queries": queries,
        "results": results,
        "pages": pages,
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(models.User).where(models.User.username == payload.username.strip()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_token(user.id, user.username, user.is_admin), user=user)


@router.get("/auth/me", response_model=UserResponse)
def current_user(user: AuthUser, db: Session = Depends(get_db)) -> Any:
    db_user = db.get(models.User, user["id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/me/password")
def change_password(payload: PasswordChange, user: AuthUser, db: Session = Depends(get_db)) -> dict:
    db_user = db.get(models.User, user["id"])
    if not db_user or not verify_password(payload.current_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    db_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"status": "ok"}


@router.get("/users", response_model=list[UserResponse])
def list_users(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.User).order_by(models.User.created_at.desc())).all()


@router.post("/users", response_model=UserResponse)
def create_user(payload: UserCreate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    existing = db.scalar(select(models.User).where(models.User.username == username))
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user = models.User(
        username=username,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, payload: UserUpdate, current_admin: AdminUser, db: Session = Depends(get_db)) -> Any:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.is_admin is not None and payload.is_admin != user.is_admin:
        if user.is_admin and not payload.is_admin and _active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last active admin")
        user.is_admin = payload.is_admin

    if payload.is_active is not None and payload.is_active != user.is_active:
        if user.id == current_admin["id"] and not payload.is_active:
            raise HTTPException(status_code=400, detail="Cannot disable your own account")
        if user.is_admin and not payload.is_active and _active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="Cannot disable the last active admin")
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user


@router.get("/dashboard")
def dashboard(_: AdminUser, db: Session = Depends(get_db)) -> dict:
    return get_dashboard(db)


@router.get("/ai-providers", response_model=list[AiProviderResponse])
def list_ai_providers(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.AiProvider).order_by(models.AiProvider.created_at.desc())).all()


@router.post("/ai-providers", response_model=AiProviderResponse)
def create_ai_provider(payload: AiProviderCreate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    provider_data = payload.model_dump(exclude={"api_login", "api_password"})
    if payload.provider_type == "dataforseo":
        if payload.api_login or payload.api_password:
            if not payload.api_login or not payload.api_password:
                raise HTTPException(status_code=400, detail="DataForSEO API login and API password are required")
            provider_data["api_key"] = f"{(payload.api_login or '').strip()}:{(payload.api_password or '').strip()}"
        if not provider_data.get("api_key"):
            raise HTTPException(status_code=400, detail="DataForSEO API login and API password are required")

    provider = models.AiProvider(**provider_data)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@router.post("/ai-providers/{provider_id}/validate", response_model=AiProviderResponse)
def validate_ai_provider(provider_id: str, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    provider = db.get(models.AiProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="AI provider not found")
    asyncio.run(validate_ai_provider_key(provider))
    db.commit()
    db.refresh(provider)
    return provider


@router.get("/sites", response_model=list[SiteResponse])
def list_sites(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.Site).order_by(models.Site.created_at.desc())).all()


@router.post("/sites", response_model=SiteResponse)
def create_site(payload: SiteCreate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    site = models.Site(**payload.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/sites/{site_id}/overview", response_model=SiteOverviewResponse)
def get_site_overview(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> dict:
    site = _get_site_or_404(db, site_id)
    status_rows = db.execute(
        select(models.ContentItem.status, func.count(models.ContentItem.id))
        .where(models.ContentItem.site_id == site_id)
        .group_by(models.ContentItem.status)
    ).all()
    status_counts = {status: count for status, count in status_rows}
    next_item = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.site_id == site_id)
        .where(models.ContentItem.status.in_(["scheduled", "retry_scheduled"]))
        .order_by(models.ContentItem.scheduled_at.asc())
        .limit(1)
    ).first()
    recent_content = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.site_id == site_id)
        .order_by(models.ContentItem.updated_at.desc())
        .limit(8)
    ).all()
    section_count = db.scalar(select(func.count(models.Section.id)).where(models.Section.site_id == site_id)) or 0
    task_count = db.scalar(
        select(func.count(models.GenerationTask.id))
        .where(models.GenerationTask.site_id == site_id, models.GenerationTask.archived_at.is_(None))
    ) or 0
    error_count = db.scalar(
        select(func.count(models.PublicationLog.id))
        .join(models.ContentItem, models.ContentItem.id == models.PublicationLog.content_item_id)
        .where(models.ContentItem.site_id == site_id)
        .where(models.PublicationLog.error_message.is_not(None))
    ) or 0

    return {
        "site": {
            "id": site.id,
            "name": site.name,
            "base_url": site.base_url,
            "payload_mode": site.payload_mode,
            "publication_endpoint": site.publication_endpoint,
        },
        "stats": {
            "tasks": task_count,
            "menu_items": section_count,
            "generated": status_counts.get("generated", 0),
            "approved": status_counts.get("approved", 0),
            "scheduled": status_counts.get("scheduled", 0) + status_counts.get("retry_scheduled", 0),
            "published": status_counts.get("published", 0),
            "failed": status_counts.get("publication_failed", 0) + status_counts.get("generation_failed", 0) + error_count,
            "next_publication_at": next_item.scheduled_at if next_item else None,
        },
        "recent_content": recent_content,
    }


@router.get("/sites/{site_id}/sections", response_model=list[SectionResponse])
def list_sections(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(select(models.Section).where(models.Section.site_id == site_id).order_by(models.Section.name.asc())).all()


@router.post("/sites/{site_id}/sections", response_model=SectionResponse)
def create_section(site_id: str, payload: SectionCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    section = models.Section(site_id=site_id, **payload.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.get("/sites/{site_id}/prompt-templates", response_model=list[PromptTemplateResponse])
def list_prompt_templates(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    site = _get_site_or_404(db, site_id)
    ensure_base_prompt_template(db)
    ensure_default_prompt_template(db, site)
    db.commit()
    return _list_global_prompt_templates(db, site)


@router.post("/sites/{site_id}/prompt-templates", response_model=PromptTemplateResponse)
def create_prompt_template(site_id: str, payload: PromptTemplateCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    site = _get_site_or_404(db, site_id)
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    if data["name"] == BASE_PROMPT_TEMPLATE_NAME:
        raise HTTPException(status_code=400, detail="Base prompt is managed separately")
    make_default = data.pop("is_default")
    prompt = models.PromptTemplate(site_id=site_id, is_default=False, **data)
    db.add(prompt)
    db.flush()
    if make_default:
        site.default_prompt_template_id = prompt.id
    db.commit()
    db.refresh(prompt)
    db.refresh(site)
    used_count = db.scalar(select(func.count(models.Site.id)).where(models.Site.default_prompt_template_id == prompt.id)) or 0
    return _prompt_template_response(prompt, site, used_count)


@router.get("/prompt-templates/base", response_model=PromptTemplateResponse)
def get_base_prompt_template(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    prompt = ensure_base_prompt_template(db)
    db.commit()
    db.refresh(prompt)
    return _prompt_template_response(prompt, None, 0)


@router.patch("/prompt-templates/base", response_model=PromptTemplateResponse)
def update_base_prompt_template(payload: PromptTemplateUpdate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    prompt = ensure_base_prompt_template(db)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name") and data["name"].strip() != BASE_PROMPT_TEMPLATE_NAME:
        raise HTTPException(status_code=400, detail="Base prompt name cannot be changed")
    if data.get("content") is not None:
        prompt.content = data["content"].strip()
    prompt.name = BASE_PROMPT_TEMPLATE_NAME
    prompt.site_id = None
    prompt.is_default = False
    db.commit()
    db.refresh(prompt)
    return _prompt_template_response(prompt, None, 0)


@router.patch("/prompt-templates/{prompt_id}", response_model=PromptTemplateResponse)
def update_prompt_template(prompt_id: str, payload: PromptTemplateUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    prompt = db.get(models.PromptTemplate, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if prompt.name == BASE_PROMPT_TEMPLATE_NAME:
        raise HTTPException(status_code=400, detail="Base prompt is managed separately")
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        data["name"] = data["name"].strip()
    if data.get("name") == BASE_PROMPT_TEMPLATE_NAME:
        raise HTTPException(status_code=400, detail="Base prompt is managed separately")
    site_id = data.pop("site_id", None)
    make_default = data.pop("is_default", None)
    site = _get_site_or_404(db, site_id) if site_id else None
    for key, value in data.items():
        setattr(prompt, key, value)
    if site and make_default is True:
        site.default_prompt_template_id = prompt.id
    elif site and make_default is False and site.default_prompt_template_id == prompt.id:
        site.default_prompt_template_id = None
    db.commit()
    db.refresh(prompt)
    if site:
        db.refresh(site)
    used_count = db.scalar(select(func.count(models.Site.id)).where(models.Site.default_prompt_template_id == prompt.id)) or 0
    return _prompt_template_response(prompt, site, used_count)


@router.delete("/prompt-templates/{prompt_id}")
def delete_prompt_template(prompt_id: str, _: AdminUser, db: Session = Depends(get_db)) -> dict:
    prompt = db.get(models.PromptTemplate, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if prompt.name == BASE_PROMPT_TEMPLATE_NAME:
        raise HTTPException(status_code=400, detail="Base prompt cannot be deleted")
    used_by_projects = db.scalar(select(func.count(models.Site.id)).where(models.Site.default_prompt_template_id == prompt.id)) or 0
    if used_by_projects:
        raise HTTPException(status_code=400, detail="Cannot delete a prompt that is used by one or more projects")
    prompts_count = db.scalar(
        select(func.count(models.PromptTemplate.id)).where(models.PromptTemplate.name != BASE_PROMPT_TEMPLATE_NAME)
    ) or 0
    if prompts_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last prompt template")
    db.delete(prompt)
    db.commit()
    return {"status": "ok"}


@router.get("/sites/{site_id}/tasks", response_model=list[GenerationTaskResponse])
def list_site_tasks(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(
        select(models.GenerationTask)
        .where(models.GenerationTask.site_id == site_id, models.GenerationTask.archived_at.is_(None))
        .order_by(models.GenerationTask.created_at.desc())
    ).all()


@router.post("/sites/{site_id}/tasks", response_model=GenerationTaskResponse)
def create_site_task(site_id: str, payload: GenerationTaskCreate, user: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    _validate_task_topics(payload)
    if payload.section_id:
        _get_section_for_site(db, site_id, payload.section_id)
    data = payload.model_dump()
    data["site_id"] = site_id
    return create_generation_task(db, GenerationTaskCreate(**data), created_by_user_id=user["id"])


@router.get("/sites/{site_id}/content", response_model=list[ContentItemResponse])
def list_site_content(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(select(models.ContentItem).where(models.ContentItem.site_id == site_id).order_by(models.ContentItem.updated_at.desc()).limit(300)).all()


@router.get("/sites/{site_id}/publication-logs", response_model=list[PublicationLogResponse])
def list_site_logs(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    content_ids = select(models.ContentItem.id).where(models.ContentItem.site_id == site_id)
    return db.scalars(
        select(models.PublicationLog)
        .where(models.PublicationLog.content_item_id.in_(content_ids))
        .order_by(models.PublicationLog.created_at.desc())
        .limit(200)
    ).all()


@router.post("/sites/{site_id}/publication-campaigns", response_model=PublicationCampaignResponse)
def create_site_campaign(site_id: str, payload: SitePublicationCampaignCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    if not payload.content_item_ids:
        raise HTTPException(status_code=400, detail="Campaign requires at least one content item")
    approved_count = db.scalar(
        select(func.count(models.ContentItem.id))
        .where(models.ContentItem.site_id == site_id)
        .where(models.ContentItem.id.in_(payload.content_item_ids))
        .where(models.ContentItem.status == "approved")
    ) or 0
    if approved_count != len(payload.content_item_ids):
        raise HTTPException(status_code=400, detail="Campaign can include only approved content from the selected site")
    interval_minutes = max(1, 1440 // payload.items_per_day)
    campaign_payload = PublicationCampaignCreate(
        name=payload.name,
        site_id=site_id,
        content_item_ids=payload.content_item_ids,
        start_at=payload.start_at,
        interval_minutes=interval_minutes,
        items_per_run=1,
    )
    try:
        return schedule_campaign(db, campaign_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sites/{site_id}/publication-campaigns", response_model=list[PublicationCampaignResponse])
def list_site_campaigns(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(
        select(models.PublicationCampaign)
        .where(models.PublicationCampaign.site_id == site_id)
        .order_by(models.PublicationCampaign.created_at.desc())
    ).all()


@router.get("/tasks", response_model=list[GenerationTaskResponse])
def list_tasks(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(
        select(models.GenerationTask)
        .where(models.GenerationTask.archived_at.is_(None))
        .order_by(models.GenerationTask.created_at.desc())
    ).all()


@router.get("/tasks-archive", response_model=list[GenerationTaskResponse])
def list_archived_tasks(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(
        select(models.GenerationTask)
        .where(models.GenerationTask.archived_at.is_not(None))
        .order_by(models.GenerationTask.archived_at.desc())
    ).all()


@router.post("/tasks", response_model=GenerationTaskResponse)
def create_task(payload: GenerationTaskCreate, user: AdminUser, db: Session = Depends(get_db)) -> Any:
    _validate_task_topics(payload)
    return create_generation_task(db, payload, created_by_user_id=user["id"])


@router.delete("/tasks/{task_id}")
def archive_task(task_id: str, user: AdminUser, db: Session = Depends(get_db)) -> dict:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.archived_at is None:
        task.archived_at = datetime.now(timezone.utc)
        task.archived_by_user_id = user["id"]
        db.commit()
    return {"status": "archived"}


@router.post("/tasks/{task_id}/restore", response_model=GenerationTaskResponse)
def restore_task(task_id: str, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.archived_at = None
    task.archived_by_user_id = None
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks/{task_id}", response_model=TaskDetailsResponse)
def get_task(task_id: str, user: AuthUser, db: Session = Depends(get_db)) -> dict:
    task = db.get(models.GenerationTask, task_id)
    if not task or (task.archived_at is not None and not user["is_admin"]):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task, "items": task.items}


@router.get("/tasks/{task_id}/competitor-research", response_model=list[CompetitorResearchResponse])
def get_task_competitor_research(task_id: str, user: AuthUser, db: Session = Depends(get_db)) -> Any:
    task = db.get(models.GenerationTask, task_id)
    if not task or (task.archived_at is not None and not user["is_admin"]):
        raise HTTPException(status_code=404, detail="Task not found")
    return [_competitor_research_response(db, item) for item in task.items]


@router.post("/tasks/{task_id}/generate", response_model=GenerationTaskResponse)
def generate_task(task_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.archived_at is not None:
        raise HTTPException(status_code=400, detail="Archived task must be restored before generation")
    mutable_items = [item for item in task.items if item.status not in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}]
    if not mutable_items:
        raise HTTPException(status_code=400, detail="Task has no content that can be generated")
    if any(item.status in {"generation_queued", "generating"} for item in mutable_items):
        return task
    task.status = "generating"
    for item in mutable_items:
        item.status = "generation_queued"
        item.generation_progress = 1
        item.generation_error = None
    db.commit()
    try:
        generate_task_content_job.delay(task.id)
    except Exception as exc:
        task.status = "generation_failed"
        for item in mutable_items:
            item.status = "generation_failed"
            item.generation_error = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        raise HTTPException(status_code=502, detail="Failed to queue content generation") from exc
    db.refresh(task)
    return task


@router.get("/content", response_model=list[ContentItemResponse])
def list_content(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.ContentItem).order_by(models.ContentItem.created_at.desc()).limit(200)).all()


@router.get("/content/{content_id}", response_model=ContentItemResponse)
def get_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    return item


@router.get("/content/{content_id}/competitor-research", response_model=CompetitorResearchResponse)
def get_content_competitor_research(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    task = db.get(models.GenerationTask, item.task_id)
    if task:
        ensure_competitor_queries(db, item, task.geo, task.language)
        db.commit()
        db.refresh(item)
    return _competitor_research_response(db, item)


@router.put("/content/{content_id}/competitor-queries", response_model=CompetitorResearchResponse)
def update_content_competitor_queries(content_id: str, payload: CompetitorQueriesUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    try:
        replace_competitor_queries(db, item, payload.queries)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(item)
    return _competitor_research_response(db, item)


@router.post("/content/{content_id}/competitor-queries/regenerate", response_model=CompetitorResearchResponse)
def regenerate_content_competitor_queries(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    task = db.get(models.GenerationTask, item.task_id)
    if not task:
        raise HTTPException(status_code=400, detail="Generation task not found")
    regenerate_competitor_queries(db, item, task.geo, task.language)
    db.commit()
    db.refresh(item)
    return _competitor_research_response(db, item)


@router.post("/content/{content_id}/competitor-collect", response_model=CompetitorResearchResponse)
def collect_content_competitors(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.competitor_research_status in {"queued", "collecting_serp", "fetching_pages"}:
        return _competitor_research_response(db, item)
    item.competitor_research_status = "queued"
    item.competitor_research_progress = 1
    item.competitor_research_error = None
    db.commit()
    try:
        collect_competitor_research_job.delay(item.id)
    except Exception as exc:
        item.competitor_research_status = "research_failed"
        item.competitor_research_error = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=502, detail="Failed to queue competitor research") from exc
    db.refresh(item)
    return _competitor_research_response(db, item)


@router.post("/content/{content_id}/competitor-serp", response_model=CompetitorResearchResponse)
def collect_content_competitor_serp(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    try:
        asyncio.run(collect_competitor_serp_for_item(db, item))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
    db.refresh(item)
    return _competitor_research_response(db, item)


@router.post("/content/{content_id}/competitor-pages", response_model=CompetitorResearchResponse)
def fetch_content_competitor_pages(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    try:
        asyncio.run(fetch_competitor_pages_for_item(db, item))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
    db.refresh(item)
    return _competitor_research_response(db, item)


@router.post("/content/{content_id}/competitor-brief", response_model=CompetitorResearchResponse)
def build_content_competitor_brief(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    try:
        build_competitor_brief_for_item(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(item)
    return _competitor_research_response(db, item)


@router.post("/content/{content_id}/generate", response_model=ContentItemResponse)
def generate_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.status in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}:
        raise HTTPException(status_code=400, detail=f"Content in status '{item.status}' cannot be regenerated")
    if item.status in {"generation_queued", "generating"}:
        return item
    item.status = "generation_queued"
    item.generation_progress = 1
    item.generation_error = None
    db.commit()
    try:
        generate_content_item_job.delay(item.id)
    except Exception as exc:
        item.status = "generation_failed"
        item.generation_error = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        raise HTTPException(status_code=502, detail="Failed to queue content generation") from exc
    db.refresh(item)
    return item


@router.patch("/content/{content_id}", response_model=ContentItemResponse)
def update_content(content_id: str, payload: ContentUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.status in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}:
        raise HTTPException(status_code=400, detail=f"Content in status '{item.status}' cannot be edited")

    if "section_id" in payload.model_fields_set:
        if payload.section_id:
            if not item.site_id:
                raise HTTPException(status_code=400, detail="Content item has no site")
            _get_section_for_site(db, item.site_id, payload.section_id)
        item.section_id = payload.section_id

    if "generated_json" in payload.model_fields_set:
        if payload.generated_json is None:
            raise HTTPException(status_code=400, detail="generated_json cannot be null")
        item.generated_json = payload.generated_json
        item.word_count = count_words(payload.generated_json)

    if item.status in {"draft", "generated", "approved", "rejected", "scheduled", "publication_failed"}:
        item.status = "generated"
    db.commit()
    db.refresh(item)
    return item


@router.delete("/content/{content_id}")
def delete_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> dict:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.status in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}:
        raise HTTPException(status_code=400, detail="Scheduled or published content cannot be deleted")

    task = db.get(models.GenerationTask, item.task_id)
    db.execute(delete(models.CompetitorPage).where(models.CompetitorPage.content_item_id == item.id))
    db.execute(delete(models.CompetitorResult).where(models.CompetitorResult.content_item_id == item.id))
    db.execute(delete(models.CompetitorQuery).where(models.CompetitorQuery.content_item_id == item.id))
    db.execute(delete(models.PublicationLog).where(models.PublicationLog.content_item_id == item.id))
    db.delete(item)
    db.flush()
    if task:
        task.topics_count = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.task_id == task.id)) or 0
        if task.topics_count == 0:
            task.status = "empty"
    db.commit()
    return {"status": "ok"}


@router.post("/content/{content_id}/approve", response_model=ContentItemResponse)
def approve_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.status not in {"generated", "rejected", "approved"}:
        raise HTTPException(status_code=400, detail=f"Content in status '{item.status}' cannot be approved")
    if item.site_id and not item.section_id:
        raise HTTPException(status_code=400, detail="Select a menu item before approval")
    if item.site_id and item.section_id:
        _get_section_for_site(db, item.site_id, item.section_id)
    try:
        validate_content_for_publication(item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    item.status = "approved"
    db.commit()
    db.refresh(item)
    return item


@router.post("/content/{content_id}/publish-now", response_model=PublicationCampaignResponse)
def publish_content_now(content_id: str, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    try:
        return approve_and_schedule_item(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/content/{content_id}/reject", response_model=ContentItemResponse)
def reject_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.status not in {"generated", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail=f"Content in status '{item.status}' cannot be rejected")
    item.status = "rejected"
    db.commit()
    db.refresh(item)
    return item


@router.post("/publication-campaigns", response_model=PublicationCampaignResponse)
def create_campaign(payload: PublicationCampaignCreate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    try:
        return schedule_campaign(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publication-campaigns", response_model=list[PublicationCampaignResponse])
def list_campaigns(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.PublicationCampaign).order_by(models.PublicationCampaign.created_at.desc())).all()


@router.patch("/publication-campaigns/{campaign_id}", response_model=PublicationCampaignResponse)
def update_campaign(campaign_id: str, payload: PublicationCampaignUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    campaign = db.get(models.PublicationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Publication campaign not found")
    try:
        return update_campaign_status(db, campaign, payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publication-logs", response_model=list[PublicationLogResponse])
def list_logs(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.PublicationLog).order_by(models.PublicationLog.created_at.desc()).limit(200)).all()


@router.post("/publication/run-due")
def run_due_publication(_: AdminUser) -> dict:
    from app.worker import publish_due_items

    result = publish_due_items.delay()
    return {"task_id": result.id, "queued_at": datetime.now(timezone.utc)}
