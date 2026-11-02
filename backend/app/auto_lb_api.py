from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Annotated, Literal

from app import models, auto_lb
from app.db import get_db
from app.security import AuthUser

router = APIRouter(prefix="/sites/{site_id}/auto-lb", tags=["AutoLB"])


class GenerateRequest(BaseModel):
    kind: Literal["anchors", "topics"]
    unique_anchor_count: int = Field(default=auto_lb.DEFAULT_UNIQUE_ANCHORS, ge=1, le=auto_lb.ANCHOR_OUTPUT_LINES, strict=True)


def get_site(db, site_id, lock=False):
    query = select(models.Site).where(models.Site.id == site_id)
    site = db.scalar(query.with_for_update() if lock else query)
    if site is None:
        raise HTTPException(404, "Проект не найден или нет доступа.")
    return site


@router.get("")
def state(site_id: str, user: AuthUser, db: Session = Depends(get_db),
          unique_anchor_count: Annotated[int, Query(ge=1, le=auto_lb.ANCHOR_OUTPUT_LINES)] = auto_lb.DEFAULT_UNIQUE_ANCHORS):
    site = get_site(db, site_id)
    error, context = None, None
    try:
        context = auto_lb.project_context(site)
    except ValueError as exc:
        error = str(exc)
    rows = db.scalars(select(models.AutoLbGeneration).where(models.AutoLbGeneration.site_id == site_id)
                      .order_by(models.AutoLbGeneration.created_at.desc()).limit(40)).all()
    provider = db.scalar(select(models.AiProvider).where(models.AiProvider.provider_type == "gemini",
                         models.AiProvider.is_active.is_(True)).order_by(models.AiProvider.created_at.desc()).limit(1))
    return {"context": context, "context_error": error, "provider_ready": bool(provider and provider.api_key),
            "anchor_count": None if context and context.get("unlimited_anchors") else auto_lb.ANCHOR_OUTPUT_LINES, "topic_count": auto_lb.OUTPUT_LINES,
            "topic_text": "\n".join(auto_lb.topic_lines(db, site_id, context)),
            "prompts": {k: auto_lb.build_prompt(k, {**context, "unique_anchor_count": unique_anchor_count})
                        for k in ("anchors", "topics")} if context else {},
            "generations": [auto_lb.serialize(row) for row in rows]}


@router.post("", status_code=202)
def create(site_id: str, payload: GenerateRequest, user: AuthUser, db: Session = Depends(get_db)):
    site = get_site(db, site_id, lock=True)
    try:
        context = auto_lb.project_context(site)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if payload.kind == "anchors" and not context.get("unlimited_anchors"):
        context["unique_anchor_count"] = payload.unique_anchor_count
        context["output_count"] = auto_lb.ANCHOR_OUTPUT_LINES
    existing = db.scalar(select(models.AutoLbGeneration).where(
        models.AutoLbGeneration.site_id == site_id, models.AutoLbGeneration.kind == payload.kind,
        models.AutoLbGeneration.status.in_(["queued", "running"])))
    if existing:
        return auto_lb.serialize(existing)
    provider = db.scalar(select(models.AiProvider).where(models.AiProvider.provider_type == "gemini",
                         models.AiProvider.is_active.is_(True)).order_by(models.AiProvider.created_at.desc()).limit(1))
    if not provider or not provider.api_key:
        raise HTTPException(422, "Настройте активный Gemini с API-ключом в разделе API Providers.")
    row = models.AutoLbGeneration(site_id=site_id, created_by_user_id=user["id"], provider_id=provider.id,
                                  kind=payload.kind, context=context, prompt=auto_lb.build_prompt(payload.kind, context))
    db.add(row)
    db.flush()
    db.add(models.BackgroundJob(kind="auto_lb", payload={"generation_id": row.id}))
    db.commit()
    return auto_lb.serialize(row)
