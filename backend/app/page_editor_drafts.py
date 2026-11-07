"""User-owned editor snapshots, saved before any request to Webdev."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.security import AuthUser

router = APIRouter()
ACTION = "manual_save"


class EditorDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(max_length=2000)
    description: str = Field(max_length=10000)
    content: dict

    @field_validator("content")
    @classmethod
    def valid_document(cls, content):
        from app.project_pages import PageEdit
        return PageEdit.editor_document(content)


def accessible_site(db, site_id, user):
    from app.project_pages import site_for
    if user.get("allowed_site_ids") is not None and site_id not in user["allowed_site_ids"]:
        raise HTTPException(404, "Проект недоступен.")
    return site_for(db, site_id)


def result(row, db):
    from app.project_pages import digest, operation_result
    operation = db.get(models.ProjectPageEdit, row.id)
    fingerprint = digest({"request_id": row.id, **(row.input_metadata or {}), "content": row.input_content})
    if operation and (operation.site_id != row.site_id or operation.page_key != row.page_key
                      or operation.requested_by != row.requested_by or operation.fingerprint != fingerprint):
        operation = None
    from app.page_save_jobs import matching_job, result as job_result
    job = matching_job(db, row.site_id, row.page_key, row.id)
    queued = None
    if job and job.payload["actor"] == row.requested_by:
        request = job.payload["request"]
        if all(request.get(k) == v for k, v in {**(row.input_metadata or {}), "content": row.input_content}.items()):
            queued = job_result(job)
    return {"id": row.id, "status": row.status, **(row.input_metadata or {}),
            "content": row.input_content, "created_at": row.created_at, "updated_at": row.updated_at,
            "operation": queued or (operation_result(operation) if operation else None)}


@router.put("/{key}/draft")
def save_editor_draft(site_id: str, key: str, payload: EditorDraft, user: AuthUser,
                      db: Session = Depends(get_db)):
    accessible_site(db, site_id, user)
    metadata = {"revision": payload.revision, "title": payload.title, "description": payload.description}
    from app.project_pages import digest
    operation = db.get(models.ProjectPageEdit, str(payload.request_id))
    if operation and (operation.site_id != site_id or operation.page_key != key
                      or operation.requested_by != user["username"]
                      or operation.fingerprint != digest(payload.model_dump(mode="json"))):
        raise HTTPException(409, "Идентификатор сохранения уже использован для других изменений.")

    def existing(row):
        if (row.site_id != site_id or row.page_key != key or row.requested_by != user["username"]
                or row.action != ACTION or row.input_content != payload.content or row.input_metadata != metadata):
            raise HTTPException(409, "Идентификатор черновика уже использован для других изменений.")
        return result(row, db)

    row = db.get(models.ProjectPageDraft, str(payload.request_id))
    if row:
        return existing(row)
    # Immutable snapshots make retries idempotent and keep concurrent tabs from
    # replacing each other's contents. No Webdev connection is needed here.
    row = models.ProjectPageDraft(id=str(payload.request_id), site_id=site_id, page_key=key,
                                 requested_by=user["username"], action=ACTION, status="ready",
                                 input_content=payload.content, input_metadata=metadata)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.get(models.ProjectPageDraft, str(payload.request_id))
        if row is None:
            raise
        return existing(row)
    return result(row, db)


@router.get("/{key}/draft")
def read_editor_draft(site_id: str, key: str, user: AuthUser, db: Session = Depends(get_db)):
    accessible_site(db, site_id, user)
    row = db.scalar(select(models.ProjectPageDraft).where(
        models.ProjectPageDraft.site_id == site_id, models.ProjectPageDraft.page_key == key,
        models.ProjectPageDraft.requested_by == user["username"], models.ProjectPageDraft.action == ACTION,
    ).order_by(models.ProjectPageDraft.created_at.desc(), models.ProjectPageDraft.id.desc()).limit(1))
    if row is None or row.status != "ready":
        return None
    snapshot = result(row, db)
    # Do not restore an older draft after the newest version was published.
    if snapshot["operation"] and snapshot["operation"]["status"] == "confirmed":
        return None
    return snapshot


@router.delete("/{key}/draft/{request_id}")
def discard_editor_draft(site_id: str, key: str, request_id: UUID, user: AuthUser,
                         db: Session = Depends(get_db)):
    accessible_site(db, site_id, user)
    row = db.get(models.ProjectPageDraft, str(request_id))
    if row is None or row.site_id != site_id or row.page_key != key or row.requested_by != user["username"] or row.action != ACTION:
        raise HTTPException(404, "Черновик не найден.")
    row.status = "discarded"
    db.commit()
    return {"id": row.id, "status": row.status}
