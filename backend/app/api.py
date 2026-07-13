import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import (
    AiProviderCreate,
    AiProviderResponse,
    ContentUpdate,
    GenerationTaskCreate,
    LoginRequest,
    PasswordChange,
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    PublicationCampaignCreate,
    SectionCreate,
    SiteCreate,
    SitePublicationCampaignCreate,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.security import AdminUser, AuthUser, create_token, hash_password, verify_password
from app.services import count_words, create_generation_task, ensure_default_prompt_template, generate_task_items, get_dashboard, schedule_campaign, validate_ai_provider_key

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
def dashboard(_: AuthUser, db: Session = Depends(get_db)) -> dict:
    return get_dashboard(db)


@router.get("/ai-providers", response_model=list[AiProviderResponse])
def list_ai_providers(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.AiProvider).order_by(models.AiProvider.created_at.desc())).all()


@router.post("/ai-providers", response_model=AiProviderResponse)
def create_ai_provider(payload: AiProviderCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    provider = models.AiProvider(**payload.model_dump())
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


@router.get("/sites")
def list_sites(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.Site).order_by(models.Site.created_at.desc())).all()


@router.post("/sites")
def create_site(payload: SiteCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    site = models.Site(**payload.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/sites/{site_id}/overview")
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
    task_count = db.scalar(select(func.count(models.GenerationTask.id)).where(models.GenerationTask.site_id == site_id)) or 0
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


@router.get("/sites/{site_id}/sections")
def list_sections(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(select(models.Section).where(models.Section.site_id == site_id).order_by(models.Section.name.asc())).all()


@router.post("/sites/{site_id}/sections")
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
    ensure_default_prompt_template(db, site)
    db.commit()
    return db.scalars(
        select(models.PromptTemplate)
        .where(models.PromptTemplate.site_id == site_id)
        .order_by(models.PromptTemplate.is_default.desc(), models.PromptTemplate.created_at.asc())
    ).all()


@router.post("/sites/{site_id}/prompt-templates", response_model=PromptTemplateResponse)
def create_prompt_template(site_id: str, payload: PromptTemplateCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    if payload.is_default:
        db.query(models.PromptTemplate).filter(models.PromptTemplate.site_id == site_id).update({"is_default": False})
    prompt = models.PromptTemplate(site_id=site_id, **payload.model_dump())
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.patch("/prompt-templates/{prompt_id}", response_model=PromptTemplateResponse)
def update_prompt_template(prompt_id: str, payload: PromptTemplateUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    prompt = db.get(models.PromptTemplate, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default") is True:
        db.query(models.PromptTemplate).filter(models.PromptTemplate.site_id == prompt.site_id, models.PromptTemplate.id != prompt.id).update({"is_default": False})
    for key, value in data.items():
        setattr(prompt, key, value)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("/sites/{site_id}/tasks")
def list_site_tasks(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(select(models.GenerationTask).where(models.GenerationTask.site_id == site_id).order_by(models.GenerationTask.created_at.desc())).all()


@router.post("/sites/{site_id}/tasks")
def create_site_task(site_id: str, payload: GenerationTaskCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    _validate_task_topics(payload)
    if payload.section_id:
        _get_section_for_site(db, site_id, payload.section_id)
    data = payload.model_dump()
    data["site_id"] = site_id
    return create_generation_task(db, GenerationTaskCreate(**data))


@router.get("/sites/{site_id}/content")
def list_site_content(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(select(models.ContentItem).where(models.ContentItem.site_id == site_id).order_by(models.ContentItem.updated_at.desc()).limit(300)).all()


@router.get("/sites/{site_id}/publication-logs")
def list_site_logs(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    content_ids = select(models.ContentItem.id).where(models.ContentItem.site_id == site_id)
    return db.scalars(
        select(models.PublicationLog)
        .where(models.PublicationLog.content_item_id.in_(content_ids))
        .order_by(models.PublicationLog.created_at.desc())
        .limit(200)
    ).all()


@router.post("/sites/{site_id}/publication-campaigns")
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
    return schedule_campaign(db, campaign_payload)


@router.get("/tasks")
def list_tasks(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.GenerationTask).order_by(models.GenerationTask.created_at.desc())).all()


@router.post("/tasks")
def create_task(payload: GenerationTaskCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _validate_task_topics(payload)
    return create_generation_task(db, payload)


@router.get("/tasks/{task_id}")
def get_task(task_id: str, _: AuthUser, db: Session = Depends(get_db)) -> dict:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task, "items": task.items}


@router.post("/tasks/{task_id}/generate")
def generate_task(task_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return generate_task_items(db, task)


@router.get("/content")
def list_content(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.ContentItem).order_by(models.ContentItem.created_at.desc()).limit(200)).all()


@router.get("/content/{content_id}")
def get_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    return item


@router.patch("/content/{content_id}")
def update_content(content_id: str, payload: ContentUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

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


@router.post("/content/{content_id}/approve")
def approve_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if item.site_id and not item.section_id:
        raise HTTPException(status_code=400, detail="Select a menu item before approval")
    item.status = "approved"
    db.commit()
    db.refresh(item)
    return item


@router.post("/content/{content_id}/reject")
def reject_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    item.status = "rejected"
    db.commit()
    db.refresh(item)
    return item


@router.post("/publication-campaigns")
def create_campaign(payload: PublicationCampaignCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    return schedule_campaign(db, payload)


@router.get("/publication-campaigns")
def list_campaigns(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.PublicationCampaign).order_by(models.PublicationCampaign.created_at.desc())).all()


@router.get("/publication-logs")
def list_logs(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.PublicationLog).order_by(models.PublicationLog.created_at.desc()).limit(200)).all()


@router.post("/publication/run-due")
def run_due_publication(_: AuthUser) -> dict:
    from app.worker import publish_due_items

    result = publish_due_items.delay()
    return {"task_id": result.id, "queued_at": datetime.now(timezone.utc)}
