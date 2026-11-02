from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import article_images as images, models
from app.db import get_db
from app.security import AdminUser, AuthUser

router = APIRouter(prefix="/article-images", tags=["Article images"])


class ImageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    model: str = images.DEFAULT_MODEL
    provider_id: str = ""
    include_logo: bool = True


@router.get("/settings")
def settings(user: AuthUser, db: Session = Depends(get_db)):
    return {**images.configuration(db), "models": images.MODELS}


@router.put("/settings")
def save_settings(payload: ImageConfig, user: AdminUser, db: Session = Depends(get_db)):
    if payload.model not in images.MODELS:
        raise HTTPException(422, "Выберите модель изображений из списка.")
    if payload.enabled:
        try:
            images.provider_for(db, payload.model_dump())
        except ValueError as error:
            raise HTTPException(422, str(error))
    row = db.get(models.AutoReglueConfig, images.CONFIG_KEY)
    if not row:
        row = models.AutoReglueConfig(key=images.CONFIG_KEY)
        db.add(row)
    row.value = payload.model_dump()
    db.commit()
    return {**images.configuration(db), "models": images.MODELS}


@router.get("/media/{asset_id}.webp")
def media(asset_id: UUID, request: Request, db: Session = Depends(get_db)):
    # Public articles load only immutable raster bytes, without an admin token.
    asset = db.get(models.ArticleImage, str(asset_id))
    if not asset or asset.status != "ready" or not asset.sha256:
        raise HTTPException(404, "Изображение не найдено.")
    headers = {"Cache-Control": "public, max-age=31536000, immutable", "ETag": f'"{asset.sha256}"',
               "X-Content-Type-Options": "nosniff"}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(content=asset.image_data, media_type="image/webp", headers=headers)


@router.post("/content/{content_id}/retry", status_code=202)
def retry(content_id: UUID, user: AuthUser, db: Session = Depends(get_db)):
    item = db.scalar(select(models.ContentItem).where(models.ContentItem.id == str(content_id)).with_for_update())
    if not item:
        raise HTTPException(404, "Текст не найден.")
    if item.status not in {"generated", "generation_failed", "draft"}:
        raise HTTPException(409, "Дождитесь завершения текущей операции. Опубликованные тексты не изменяются.")
    if not images.configuration(db)["enabled"]:
        raise HTTPException(422, "Включите генерацию изображений в API Providers.")
    if not str(item.slug or "").strip("/") or not item.generated_json.get("pages"):
        raise HTTPException(422, "Изображение можно создать для готового текста внутренней страницы.")
    state = (item.generated_json.get("generation_meta") or {}).get("article_image") or {}
    if state.get("status") == "ready":
        return {"content_id": item.id, "status": "ready"}
    item.status, item.generation_error = "generating", None
    db.add(models.BackgroundJob(kind="article_image", payload={"content_id": item.id}))
    db.commit()
    return {"content_id": item.id, "status": "queued"}
