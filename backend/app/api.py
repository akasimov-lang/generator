from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db import get_db
from app.schemas import (
    AiProviderCreate,
    ContentUpdate,
    GenerationTaskCreate,
    LoginRequest,
    PublicationCampaignCreate,
    SectionCreate,
    SiteCreate,
    TokenResponse,
)
from app.security import AuthUser, create_token
from app.services import count_words, create_generation_task, generate_task_items, get_dashboard, schedule_campaign

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if payload.username != settings.admin_username or payload.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_token(payload.username))


@router.get("/dashboard")
def dashboard(_: AuthUser, db: Session = Depends(get_db)) -> dict:
    return get_dashboard(db)


@router.get("/ai-providers")
def list_ai_providers(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.AiProvider).order_by(models.AiProvider.created_at.desc())).all()


@router.post("/ai-providers")
def create_ai_provider(payload: AiProviderCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    provider = models.AiProvider(**payload.model_dump())
    db.add(provider)
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


@router.get("/sites/{site_id}/sections")
def list_sections(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.Section).where(models.Section.site_id == site_id).order_by(models.Section.name.asc())).all()


@router.post("/sites/{site_id}/sections")
def create_section(site_id: str, payload: SectionCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    site = db.get(models.Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    section = models.Section(site_id=site_id, **payload.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.get("/tasks")
def list_tasks(_: AuthUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.GenerationTask).order_by(models.GenerationTask.created_at.desc())).all()


@router.post("/tasks")
def create_task(payload: GenerationTaskCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
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
    item.generated_json = payload.generated_json
    item.word_count = count_words(payload.generated_json)
    item.status = "generated"
    db.commit()
    db.refresh(item)
    return item


@router.post("/content/{content_id}/approve")
def approve_content(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
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
