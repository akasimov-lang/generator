from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import (
    AiProviderCreate,
    ContentUpdate,
    GenerationTaskCreate,
    LoginRequest,
    PasswordChange,
    PublicationCampaignCreate,
    SectionCreate,
    SiteCreate,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.security import AdminUser, AuthUser, create_token, hash_password, verify_password
from app.services import count_words, create_generation_task, generate_task_items, get_dashboard, schedule_campaign

router = APIRouter()


def _active_admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(models.User).where(models.User.is_admin.is_(True), models.User.is_active.is_(True))) or 0


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
