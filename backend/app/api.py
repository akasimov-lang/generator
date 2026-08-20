import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db import get_db
from app.schemas import (
    AiProviderCreate,
    AiProviderResponse,
    AdminRequestLogResponse,
    CompetitorQueriesUpdate,
    CompetitorResearchResponse,
    ContentItemResponse,
    ContentUpdate,
    DuplicateSitesDeleteResponse,
    FavoriteSitesResponse,
    GenerationTaskCreate,
    GenerationTaskRegenerateAll,
    GenerationTaskResponse,
    GenerationTaskSectionUpdate,
    LoginRequest,
    MenuTemplateApplyResponse,
    MenuTemplateResponse,
    MenuLibraryItemCreate,
    MenuLibraryItemResponse,
    MenuLibraryItemUpdate,
    PasswordChange,
    PublicationCampaignResponse,
    PublicationCampaignReschedule,
    PublicationCampaignUpdate,
    PublicationContentResponse,
    PublicationLogResponse,
    PromptTemplateCreate,
    PromptGeneratedContentResponse,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    ProjectCacheSyncResponse,
    ProjectCacheSyncRequest,
    PublicationCampaignCreate,
    PublicationCampaignQueueResponse,
    SectionCreate,
    SectionAdoptResponse,
    SectionResponse,
    SectionUpdate,
    SectionsBulkCreate,
    SectionsBulkCreateResponse,
    SiteCreate,
    SiteOverviewResponse,
    SitePublicationCampaignCreate,
    SiteResponse,
    SiteStatusUpdate,
    TaskDetailsResponse,
    TokenResponse,
    TopicSuggestionsRequest,
    TopicSuggestionsResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.menu_templates import MENU_TEMPLATES
from app.project_cache import ProjectCacheError, fetch_project_cache, fetch_project_menu_capabilities, sync_project_cache
from app.security import AdminUser, AuthUser, create_token, hash_password, verify_password
from app.services import (
    BASE_PROMPT_TEMPLATE_NAME,
    approve_and_schedule_item,
    build_campaign_publication_bundle,
    build_competitor_brief_for_item,
    collect_competitor_serp_for_item,
    count_words,
    append_casino_rating_requirement,
    compose_prompt_with_base,
    create_generation_task,
    ensure_base_prompt_template,
    ensure_default_prompt_template,
    ensure_competitor_queries,
    fetch_competitor_pages_for_item,
    get_dashboard,
    generate_topic_suggestions,
    publish_item,
    refresh_campaign_status,
    regenerate_competitor_queries,
    replace_competitor_queries,
    schedule_campaign,
    reschedule_campaign,
    sync_project_menus,
    update_campaign_status,
    validate_content_for_publication,
    validate_ai_provider_key,
)
from app.worker import collect_competitor_research_job, generate_content_item_job, generate_task_content_job, publish_campaign_bundle_job, run_task_pipeline_job

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


def _add_site_menu_library_item(site: models.Site, payload: MenuLibraryItemCreate) -> dict[str, str]:
    item = payload.model_dump(exclude_none=True)
    current = site.menu_library if isinstance(site.menu_library, list) else []
    existing = next(
        (
            entry
            for entry in current
            if isinstance(entry, dict)
            and (entry.get("external_id") == item["external_id"] or entry.get("path") == item["path"])
        ),
        None,
    )
    if existing:
        return existing
    site.menu_library = [*current, item]
    return item


def _normalized_language(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-").split("-", 1)[0]


def _normalized_menu_path(value: str) -> str:
    path = value.strip().strip("/")
    return f"/{path}/" if path else "/"


def _cached_menu_item_matches(item: Any, payload: SectionCreate) -> bool:
    if isinstance(item, str):
        return item.strip().casefold() == payload.name.strip().casefold()
    if not isinstance(item, dict):
        return False
    item_path = next(
        (str(item.get(key)).strip() for key in ("path", "url", "href", "slug") if item.get(key)),
        "",
    )
    if item_path and _normalized_menu_path(item_path) == _normalized_menu_path(payload.path):
        return True
    item_id = str(item.get("external_id") or item.get("externalId") or item.get("id") or "").strip()
    if item_id and item_id.casefold() == payload.external_id.strip().casefold():
        return True
    item_name = str(item.get("title") or item.get("name") or item.get("label") or item.get("text") or "").strip()
    return bool(item_name and item_name.casefold() == payload.name.strip().casefold())


def _validate_task_topics(payload: GenerationTaskCreate) -> None:
    clean_topics = [topic.strip() for topic in payload.topics if topic.strip()]
    if not clean_topics:
        raise HTTPException(status_code=400, detail="Add at least one topic")
    if len(clean_topics) > 30:
        raise HTTPException(status_code=400, detail="A generation task can include up to 30 topics")


def _prompt_template_response(
    prompt: models.PromptTemplate,
    site: models.Site | None,
    used_by_projects: int,
    generated_texts_count: int = 0,
) -> dict:
    return {
        "id": prompt.id,
        "site_id": prompt.site_id,
        "name": prompt.name,
        "content": prompt.content,
        "is_default": bool(site and site.default_prompt_template_id == prompt.id),
        "used_by_projects": used_by_projects,
        "generated_texts_count": generated_texts_count,
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
    generated_rows = db.execute(
        select(models.ContentItem.generation_prompt_name, func.count(models.ContentItem.id))
        .where(
            models.ContentItem.generated_at.is_not(None),
            models.ContentItem.generation_prompt_name.is_not(None),
        )
        .group_by(models.ContentItem.generation_prompt_name)
    ).all()
    generated_counts = {prompt_name: count for prompt_name, count in generated_rows}
    rows = [
        _prompt_template_response(
            prompt,
            site,
            used_counts.get(prompt.id, 0),
            generated_counts.get(prompt.name, 0),
        )
        for prompt in prompts
    ]
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


@router.get("/me/favorite-sites", response_model=FavoriteSitesResponse)
def get_favorite_sites(user: AuthUser, db: Session = Depends(get_db)) -> dict[str, list[str]]:
    db_user = db.get(models.User, user["id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"site_ids": list(db_user.favorite_site_ids or [])}


@router.put("/me/favorite-sites/{site_id}", response_model=FavoriteSitesResponse)
def add_favorite_site(site_id: str, user: AuthUser, db: Session = Depends(get_db)) -> dict[str, list[str]]:
    db_user = db.get(models.User, user["id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not db.get(models.Site, site_id):
        raise HTTPException(status_code=404, detail="Site not found")
    favorite_site_ids = list(db_user.favorite_site_ids or [])
    if site_id not in favorite_site_ids:
        favorite_site_ids.append(site_id)
        db_user.favorite_site_ids = favorite_site_ids
        db.commit()
    return {"site_ids": favorite_site_ids}


@router.delete("/me/favorite-sites/{site_id}", response_model=FavoriteSitesResponse)
def remove_favorite_site(site_id: str, user: AuthUser, db: Session = Depends(get_db)) -> dict[str, list[str]]:
    db_user = db.get(models.User, user["id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    favorite_site_ids = [favorite_id for favorite_id in (db_user.favorite_site_ids or []) if favorite_id != site_id]
    db_user.favorite_site_ids = favorite_site_ids
    db.commit()
    return {"site_ids": favorite_site_ids}


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
def list_sites(user: AuthUser, db: Session = Depends(get_db)) -> Any:
    query = select(models.Site)
    if not user.get("is_admin"):
        query = query.where(models.Site.project_status.in_(["test", "working"]))
    return db.scalars(
        query.order_by(
            models.Site.is_test_project.desc(),
            models.Site.has_menu.desc(),
            models.Site.name.asc(),
        )
    ).all()


@router.get("/sites/cache/projects", response_model=list[SiteResponse])
def list_cached_projects(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    status_order = {"test": 0, "working": 1, "not_in_focus": 2, "duplicate": 3}
    sites = db.scalars(select(models.Site)).all()
    return sorted(sites, key=lambda site: (status_order.get(site.project_status, 3), not site.has_menu, site.name.lower()))


@router.post("/sites", response_model=SiteResponse)
def create_site(payload: SiteCreate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    site = models.Site(**payload.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.post("/sites/cache/sync", response_model=ProjectCacheSyncResponse)
def synchronize_project_cache(payload: ProjectCacheSyncRequest, _: AdminUser, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        names = list(dict.fromkeys(name.strip() for name in payload.names if name.strip()))
        return sync_project_cache(db, fetch_project_cache(names or None))
    except ProjectCacheError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.patch("/sites/{site_id}/status", response_model=SiteResponse)
def update_site_status(site_id: str, payload: SiteStatusUpdate, _: AdminUser, db: Session = Depends(get_db)) -> Any:
    site = _get_site_or_404(db, site_id)
    site.project_status = payload.project_status
    site.is_test_project = payload.project_status == "test"
    db.commit()
    db.refresh(site)
    return site


@router.delete("/sites/cache/duplicates", response_model=DuplicateSitesDeleteResponse)
def delete_duplicate_sites(_: AdminUser, db: Session = Depends(get_db)) -> dict[str, int]:
    duplicate_sites = db.scalars(select(models.Site).where(models.Site.project_status == "duplicate")).all()
    deleted_count = 0
    skipped_count = 0
    for site in duplicate_sites:
        has_related_data = any(
            db.scalar(select(func.count()).select_from(model).where(model.site_id == site.id))
            for model in (models.PromptTemplate, models.GenerationTask, models.ContentItem, models.PublicationCampaign)
        )
        if has_related_data:
            skipped_count += 1
            continue
        db.delete(site)
        deleted_count += 1
    db.commit()
    return {"deleted_count": deleted_count, "skipped_count": skipped_count}


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


@router.get("/menu-templates", response_model=list[MenuTemplateResponse])
def list_menu_templates(_: AuthUser, language: str = "") -> list[dict[str, Any]]:
    normalized_language = _normalized_language(language)
    return [
        template
        for template in MENU_TEMPLATES.values()
        if not normalized_language or template["language"] == normalized_language
    ]


@router.post(
    "/sites/{site_id}/menu-templates/{template_id}/apply",
    response_model=MenuTemplateApplyResponse,
)
def apply_menu_template(
    site_id: str,
    template_id: str,
    _: AuthUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    site = _get_site_or_404(db, site_id)
    template = MENU_TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Menu template not found")
    if _normalized_language(site.cache_language) != template["language"]:
        raise HTTPException(status_code=400, detail="This menu template is available only for DE projects")

    existing_sections = db.scalars(select(models.Section).where(models.Section.site_id == site_id)).all()
    existing_by_external_id = {
        section.external_id.casefold(): section
        for section in existing_sections
        if section.menu_type == "header"
    }
    existing_by_path = {
        _normalized_menu_path(section.path): section
        for section in existing_sections
        if section.menu_type == "header"
    }
    resolved_sections: dict[str, models.Section] = {}
    ordered_sections: list[models.Section] = []
    created_count = 0
    skipped_count = 0
    updated_count = 0

    current_library = [entry for entry in (site.menu_library or []) if isinstance(entry, dict)]
    for item in template["items"]:
        parent_external_id = item["parent_external_id"]
        parent = resolved_sections.get(parent_external_id) if parent_external_id else None
        section = existing_by_external_id.get(item["external_id"].casefold()) or existing_by_path.get(
            _normalized_menu_path(item["path"])
        )
        if section:
            expected_parent_id = parent.id if parent else None
            if section.parent_id != expected_parent_id:
                section.parent_id = expected_parent_id
                section.is_temporary_parent = False
                section.sync_status = "pending"
                section.synced_at = None
                updated_count += 1
                db.add(
                    models.PublicationLog(
                        endpoint_url=site.sections_endpoint or site.base_url,
                        request_payload={
                            "action": "menu_item_update",
                            "project_name": site.name,
                            "name": section.name,
                            "path": section.path,
                            "menu_type": "header",
                            "parent_id": expected_parent_id,
                            "template_id": template_id,
                        },
                        response_status=None,
                        response_body={"section_id": section.id, "synchronized": False},
                    )
                )
            else:
                skipped_count += 1
        else:
            section = models.Section(
                site_id=site_id,
                external_id=item["external_id"],
                name=item["name"],
                path=_normalized_menu_path(item["path"]),
                menu_type="header",
                parent_id=parent.id if parent else None,
                sync_status="pending",
            )
            db.add(section)
            db.flush()
            existing_by_external_id[section.external_id.casefold()] = section
            existing_by_path[_normalized_menu_path(section.path)] = section
            created_count += 1
            db.add(
                models.PublicationLog(
                    endpoint_url=site.sections_endpoint or site.base_url,
                    request_payload={
                        "action": "menu_item_create",
                        "project_name": site.name,
                        "name": section.name,
                        "external_id": section.external_id,
                        "path": section.path,
                        "menu_type": "header",
                        "parent_id": section.parent_id,
                        "template_id": template_id,
                    },
                    response_status=None,
                    response_body={"section_id": section.id, "synchronized": False},
                )
            )

        resolved_sections[item["external_id"]] = section
        ordered_sections.append(section)
        library_item = {
            "name": item["name"],
            "path": _normalized_menu_path(item["path"]),
            "external_id": item["external_id"],
            "parent_external_id": item["parent_external_id"],
            "template_id": template_id,
        }
        conflict_index = next(
            (
                index
                for index, entry in enumerate(current_library)
                if entry.get("external_id") == item["external_id"]
                or _normalized_menu_path(str(entry.get("path") or "")) == library_item["path"]
            ),
            None,
        )
        if conflict_index is None:
            current_library.append(library_item)
        else:
            current_library[conflict_index] = library_item

    site.menu_library = current_library
    db.commit()
    for section in ordered_sections:
        db.refresh(section)
    return {
        "template_id": template_id,
        "total_count": len(template["items"]),
        "created_count": created_count,
        "skipped_count": skipped_count,
        "updated_count": updated_count,
        "sections": ordered_sections,
    }


@router.get("/sites/{site_id}/sections", response_model=list[SectionResponse])
def list_sections(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    _get_site_or_404(db, site_id)
    return db.scalars(select(models.Section).where(models.Section.site_id == site_id).order_by(models.Section.name.asc())).all()


@router.get("/sites/{site_id}/menu-capabilities")
def get_site_menu_capabilities(site_id: str, _: AuthUser, db: Session = Depends(get_db), refresh: bool = False) -> dict[str, Any]:
    site = _get_site_or_404(db, site_id)
    if site.menu_capabilities_checked_at is None or refresh:
        if not site.cache_server_ip:
            try:
                projects = fetch_project_cache([site.name])
                project = next((item for item in projects if str(item.get("name") or "").strip() == site.name), None)
                if project:
                    site.cache_server_ip = str(
                        project.get("serverId")
                        or project.get("server_id")
                        or project.get("serverIp")
                        or project.get("server_ip")
                        or ""
                    ).strip() or None
                    db.commit()
            except ProjectCacheError as error:
                raise HTTPException(status_code=502, detail=str(error)) from error
        try:
            capabilities = fetch_project_menu_capabilities(site, force=True) if refresh else fetch_project_menu_capabilities(site)
        except ProjectCacheError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        site.header_menu_rendered = capabilities["header_menu_rendered"]
        site.header_menu_nested = capabilities["header_menu_nested"]
        site.footer_menu_rendered = capabilities["footer_menu_rendered"]
        site.footer_menu_nested = capabilities["footer_menu_nested"]
        site.menu_capabilities_checked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(site)
    return {
        "checked_at": site.menu_capabilities_checked_at,
        "header_menu_rendered": site.header_menu_rendered,
        "header_menu_nested": site.header_menu_nested,
        "footer_menu_rendered": site.footer_menu_rendered,
        "footer_menu_nested": site.footer_menu_nested,
    }


@router.post("/sites/{site_id}/sync-changes")
async def sync_site_changes(site_id: str, _: AuthUser, db: Session = Depends(get_db)) -> dict[str, Any]:
    site = _get_site_or_404(db, site_id)
    try:
        return await sync_project_menus(db, site)
    except ProjectCacheError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/sites/{site_id}/sections", response_model=SectionResponse)
def create_section(site_id: str, payload: SectionCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    site = _get_site_or_404(db, site_id)
    parent = None
    if payload.parent_id:
        parent = _get_section_for_site(db, site_id, payload.parent_id)
        if parent.menu_type != payload.menu_type:
            raise HTTPException(status_code=400, detail="Parent menu item must use the same menu type")
        parent.is_temporary_parent = False
    _add_site_menu_library_item(
        site,
        MenuLibraryItemCreate(
            name=payload.name,
            path=payload.path,
            external_id=payload.external_id,
        ),
    )
    section = models.Section(site_id=site_id, **payload.model_dump())
    db.add(section)
    db.flush()
    db.add(
        models.PublicationLog(
            endpoint_url=site.sections_endpoint or site.base_url,
            request_payload={"action": "menu_item_create", "project_name": site.name, **payload.model_dump()},
            response_status=None,
            response_body={"section_id": section.id, "synchronized": False},
        )
    )
    db.commit()
    db.refresh(section)
    return section


@router.post("/sites/{site_id}/sections/adopt", response_model=SectionAdoptResponse)
def adopt_cached_section(site_id: str, payload: SectionCreate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    """Create a local synchronized reference for a menu item that already exists in the project cache."""
    site = _get_site_or_404(db, site_id)
    cached_menu = site.default_menu if isinstance(site.default_menu, dict) else {}
    cached_items = cached_menu.get(payload.menu_type, [])
    if not isinstance(cached_items, list) or not any(_cached_menu_item_matches(item, payload) for item in cached_items):
        raise HTTPException(status_code=404, detail="Menu item was not found in the synchronized project menu")

    normalized_path = _normalized_menu_path(payload.path)
    existing = next(
        (
            section
            for section in db.scalars(select(models.Section).where(models.Section.site_id == site_id)).all()
            if section.menu_type == payload.menu_type
            and (
                section.external_id.casefold() == payload.external_id.strip().casefold()
                or _normalized_menu_path(section.path) == normalized_path
            )
        ),
        None,
    )
    if existing:
        return {"section": existing, "created": False}

    section = models.Section(
        site_id=site_id,
        external_id=payload.external_id.strip(),
        name=payload.name.strip(),
        path=normalized_path,
        menu_type=payload.menu_type,
        is_temporary_parent=True,
        sync_status="synced",
        synced_at=site.cache_synced_at or datetime.now(timezone.utc),
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return {"section": section, "created": True}


@router.delete("/sites/{site_id}/sections/{section_id}/adopt")
def release_adopted_section(site_id: str, section_id: str, _: AuthUser, db: Session = Depends(get_db)) -> dict[str, bool]:
    """Remove an unused local reference created only to prepare a nested menu item form."""
    _get_site_or_404(db, site_id)
    section = _get_section_for_site(db, site_id, section_id)
    task_count = db.scalar(select(func.count(models.GenerationTask.id)).where(models.GenerationTask.section_id == section.id)) or 0
    content_count = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.section_id == section.id)) or 0
    child_count = db.scalar(select(func.count(models.Section.id)).where(models.Section.parent_id == section.id)) or 0
    if not section.is_temporary_parent or task_count or content_count or child_count:
        raise HTTPException(status_code=409, detail="Временный родительский пункт уже используется и не может быть удалён")
    db.delete(section)
    db.commit()
    return {"deleted": True}


@router.patch("/sites/{site_id}/sections/{section_id}", response_model=SectionResponse)
def update_section(site_id: str, section_id: str, payload: SectionUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    site = _get_site_or_404(db, site_id)
    section = _get_section_for_site(db, site_id, section_id)
    old_name = section.name
    old_path = section.path
    section.name = payload.name.strip()
    path = payload.path.strip().strip("/")
    section.path = f"/{path}/" if path else "/"
    section.sync_status = "pending"
    section.synced_at = None
    current_library = site.menu_library if isinstance(site.menu_library, list) else []
    site.menu_library = [
        {
            **item,
            "name": section.name,
            "path": section.path,
        } if isinstance(item, dict) and item.get("external_id") == section.external_id else item
        for item in current_library
    ]
    db.add(
        models.PublicationLog(
            endpoint_url=site.sections_endpoint or site.base_url,
            request_payload={
                "action": "menu_item_update",
                "project_name": site.name,
                "name": section.name,
                "path": section.path,
                "menu_type": section.menu_type,
                "previous_name": old_name,
                "previous_path": old_path,
            },
            response_status=None,
            response_body={"section_id": section.id, "synchronized": False},
        )
    )
    db.commit()
    db.refresh(section)
    return section


@router.delete("/sites/{site_id}/sections/{section_id}")
def delete_section(site_id: str, section_id: str, _: AuthUser, db: Session = Depends(get_db)) -> dict[str, bool]:
    site = _get_site_or_404(db, site_id)
    section = _get_section_for_site(db, site_id, section_id)
    task_count = db.scalar(select(func.count(models.GenerationTask.id)).where(models.GenerationTask.section_id == section.id)) or 0
    content_count = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.section_id == section.id)) or 0
    child_count = db.scalar(select(func.count(models.Section.id)).where(models.Section.parent_id == section.id)) or 0
    if task_count or content_count or child_count:
        raise HTTPException(status_code=409, detail="Пункт используется в задачах, контенте или содержит дочерние пункты и не может быть удалён")
    db.delete(section)
    db.add(
        models.PublicationLog(
            endpoint_url=site.sections_endpoint or site.base_url,
            request_payload={
                "action": "menu_item_delete",
                "project_name": site.name,
                "name": section.name,
                "path": section.path,
                "menu_type": section.menu_type,
            },
            response_status=None,
            response_body={"section_id": section.id, "deleted_from_system": True},
        )
    )
    db.commit()
    return {"deleted": True}


@router.post("/sites/{site_id}/menu-library", response_model=MenuLibraryItemResponse)
def create_menu_library_item(site_id: str, payload: MenuLibraryItemCreate, _: AuthUser, db: Session = Depends(get_db)) -> dict[str, str]:
    site = _get_site_or_404(db, site_id)
    item = _add_site_menu_library_item(site, payload)
    db.commit()
    return item


@router.patch("/sites/{site_id}/menu-library/{external_id}", response_model=MenuLibraryItemResponse)
def update_menu_library_item(
    site_id: str,
    external_id: str,
    payload: MenuLibraryItemUpdate,
    _: AuthUser,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    site = _get_site_or_404(db, site_id)
    raw_path = payload.path.strip()
    path_without_edge_slashes = raw_path.strip("/")
    normalized_path = f"/{path_without_edge_slashes}/" if path_without_edge_slashes else "/"
    updated_item = {
        "name": payload.name.strip(),
        "path": normalized_path,
        "external_id": external_id,
        "russian_name": payload.russian_name.strip(),
    }
    current = [entry for entry in (site.menu_library or []) if isinstance(entry, dict)]
    existing_item = next((entry for entry in current if entry.get("external_id") == external_id), None)
    if existing_item and existing_item.get("parent_external_id"):
        updated_item["parent_external_id"] = existing_item["parent_external_id"]
    if existing_item and existing_item.get("template_id"):
        updated_item["template_id"] = existing_item["template_id"]
    conflicting = next(
        (
            entry
            for entry in current
            if entry.get("external_id") != external_id and entry.get("path") == normalized_path
        ),
        None,
    )
    if conflicting:
        raise HTTPException(status_code=409, detail="A menu library item with this URL already exists")
    replaced = False
    updated_library: list[dict[str, Any]] = []
    for entry in current:
        if entry.get("external_id") == external_id:
            if not replaced:
                updated_library.append(updated_item)
                replaced = True
            continue
        updated_library.append(entry)
    if not replaced:
        updated_library.append(updated_item)
    site.menu_library = updated_library
    db.commit()
    return updated_item


@router.post("/sites/{site_id}/sections/bulk", response_model=SectionsBulkCreateResponse)
def create_sections_bulk(site_id: str, payload: SectionsBulkCreate, _: AuthUser, db: Session = Depends(get_db)) -> dict[str, Any]:
    _get_site_or_404(db, site_id)
    existing_ids = set(
        db.scalars(select(models.Section.external_id).where(models.Section.site_id == site_id)).all()
    )
    created: list[models.Section] = []
    skipped_count = 0
    for item in payload.items:
        if item.external_id in existing_ids:
            skipped_count += 1
            continue
        section = models.Section(site_id=site_id, **item.model_dump())
        db.add(section)
        created.append(section)
        existing_ids.add(item.external_id)
    db.commit()
    for section in created:
        db.refresh(section)
    return {"created_count": len(created), "skipped_count": skipped_count, "sections": created}


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


@router.get("/prompt-templates/{prompt_id}/generated-content", response_model=list[PromptGeneratedContentResponse])
def list_prompt_generated_content(prompt_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    prompt = db.get(models.PromptTemplate, prompt_id)
    if not prompt or prompt.name == BASE_PROMPT_TEMPLATE_NAME:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    rows = db.execute(
        select(models.ContentItem, models.Site.name)
        .outerjoin(models.Site, models.Site.id == models.ContentItem.site_id)
        .where(
            models.ContentItem.generation_prompt_name == prompt.name,
            models.ContentItem.generated_at.is_not(None),
        )
        .order_by(models.ContentItem.generated_at.desc(), models.ContentItem.updated_at.desc())
    ).all()
    return [
        {
            "id": item.id,
            "task_id": item.task_id,
            "site_id": item.site_id,
            "site_name": site_name,
            "topic": item.topic,
            "slug": item.slug,
            "status": item.status,
            "word_count": item.word_count,
            "generation_prompt_name": item.generation_prompt_name,
            "include_casino_rating": item.include_casino_rating,
            "generated_at": item.generated_at,
            "updated_at": item.updated_at,
        }
        for item, site_name in rows
    ]


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


@router.post("/sites/{site_id}/topic-suggestions", response_model=TopicSuggestionsResponse)
def suggest_site_topics(site_id: str, payload: TopicSuggestionsRequest, _: AuthUser, db: Session = Depends(get_db)) -> dict[str, list[str]]:
    site = _get_site_or_404(db, site_id)
    provider = db.get(models.AiProvider, payload.ai_provider_id) if payload.ai_provider_id else db.scalar(
        select(models.AiProvider)
        .where(models.AiProvider.provider_type == "gemini", models.AiProvider.is_active.is_(True))
        .order_by(models.AiProvider.created_at.desc())
        .limit(1)
    )
    if not provider or provider.provider_type != "gemini" or not provider.is_active:
        raise HTTPException(status_code=400, detail="Select an active Gemini provider to generate topics")

    section_context = ""
    if payload.section_id:
        section = _get_section_for_site(db, site_id, payload.section_id)
        section_context = f"{section.name} · {section.path}"
    stored_topics = db.scalars(
        select(models.ContentItem.topic)
        .where(models.ContentItem.site_id == site_id)
        .order_by(models.ContentItem.created_at.desc())
    ).all()
    existing_topics = [*stored_topics, *payload.current_topics]
    try:
        topics = asyncio.run(
            generate_topic_suggestions(
                provider=provider,
                site=site,
                geo=payload.geo,
                language=payload.language,
                existing_topics=existing_topics,
                section_context=section_context,
            )
        )
    except Exception as exc:
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
    db.commit()
    return {"topics": topics}


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
    interval_minutes = {1: 1440, 2: 720, 3: 420}[payload.items_per_day]
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


@router.patch("/tasks/{task_id}/section", response_model=GenerationTaskResponse)
def update_task_section(task_id: str, payload: GenerationTaskSectionUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.section_id:
        if not task.site_id:
            raise HTTPException(status_code=400, detail="Task does not have a project")
        _get_section_for_site(db, task.site_id, payload.section_id)
    task.section_id = payload.section_id
    for item in task.items:
        if item.status not in {"scheduled", "retry_scheduled", "publishing", "published"}:
            item.section_id = payload.section_id
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


@router.post("/tasks/{task_id}/regenerate-all", response_model=GenerationTaskResponse)
def regenerate_all_task_content(
    task_id: str,
    payload: GenerationTaskRegenerateAll,
    _: AuthUser,
    db: Session = Depends(get_db),
) -> Any:
    task = db.get(models.GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.archived_at is not None:
        raise HTTPException(status_code=400, detail="Archived task must be restored before generation")

    locked_statuses = {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}
    mutable_items = [item for item in task.items if item.status not in locked_statuses]
    if not mutable_items:
        raise HTTPException(status_code=400, detail="Task has no content that can be regenerated")
    if any(item.status in {"generation_queued", "generating"} for item in mutable_items):
        raise HTTPException(status_code=409, detail="Task generation is already in progress")

    prompt_template = compose_prompt_with_base(db, payload.prompt_template)
    task.prompt_template_name = payload.prompt_template_name
    task.prompt_template = append_casino_rating_requirement(prompt_template, payload.include_casino_rating)
    task.include_toc = payload.include_toc
    task.include_faq = payload.include_faq
    task.collect_competitors = payload.collect_competitors
    task.include_casino_rating = payload.include_casino_rating
    task.status = "generating"

    for item in mutable_items:
        item.status = "generation_queued"
        item.generation_progress = 1
        item.generation_error = None
        if payload.collect_competitors:
            item.competitor_brief = None
            item.competitor_brief_text = None
            item.competitor_research_status = "queries_ready"
            item.competitor_research_progress = 0
            item.competitor_research_error = None

    db.commit()
    try:
        if payload.collect_competitors:
            run_task_pipeline_job.delay(task.id)
        else:
            generate_task_content_job.delay(task.id)
    except Exception as exc:
        task.status = "generation_failed"
        for item in mutable_items:
            item.status = "generation_failed"
            item.generation_error = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        raise HTTPException(status_code=502, detail="Failed to queue task regeneration") from exc

    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/start", response_model=GenerationTaskResponse)
def start_task_pipeline(task_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
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
        run_task_pipeline_job.delay(task.id)
    except Exception as exc:
        task.status = "generation_failed"
        for item in mutable_items:
            item.status = "generation_failed"
            item.generation_error = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        raise HTTPException(status_code=502, detail="Failed to queue task pipeline") from exc
    db.refresh(task)
    return task


@router.get("/content", response_model=list[ContentItemResponse])
def list_content(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.ContentItem).order_by(models.ContentItem.created_at.desc()).limit(200)).all()


@router.get("/publication-content", response_model=list[PublicationContentResponse])
def list_publication_content(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    rows = db.execute(
        select(
            models.ContentItem.id,
            models.ContentItem.task_id,
            models.ContentItem.site_id,
            models.ContentItem.topic,
            models.ContentItem.slug,
            models.ContentItem.status,
            models.ContentItem.word_count,
            models.ContentItem.include_casino_rating,
            models.ContentItem.generated_at,
            models.ContentItem.published_at,
            models.ContentItem.updated_at,
        )
        .where(models.ContentItem.site_id.is_not(None))
        .order_by(models.ContentItem.updated_at.desc())
    ).mappings().all()
    return [dict(row) for row in rows]


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

        # The generation tab displays the menu section stored on the parent
        # task. Keep it aligned with content assignments whenever the whole
        # task has one unambiguous section. Mixed assignments intentionally
        # clear the task-level value instead of showing a misleading option.
        task_section_ids = {task_item.section_id for task_item in item.task.items}
        item.task.section_id = task_section_ids.pop() if len(task_section_ids) == 1 else None

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


@router.post("/content/{content_id}/publish-immediately", response_model=ContentItemResponse)
async def publish_content_immediately(content_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    item = db.get(models.ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    if not item.site_id:
        raise HTTPException(status_code=400, detail="Select a project before publication")
    if not item.section_id:
        raise HTTPException(status_code=400, detail="Select a menu item before publication")
    site = _get_site_or_404(db, item.site_id)
    campaign_id = item.publication_campaign_id
    try:
        validate_content_for_publication(item)
        await publish_item(db, item, site)
        if item.status == "published":
            item.scheduled_at = None
            db.commit()
            refresh_campaign_status(db, campaign_id)
            db.commit()
        db.refresh(item)
        return item
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


@router.get("/publication-campaigns/{campaign_id}/queue", response_model=PublicationCampaignQueueResponse)
def get_campaign_queue(campaign_id: str, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    campaign = db.get(models.PublicationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Publication campaign not found")
    rows = db.execute(
        select(models.ContentItem, models.Section.name)
        .outerjoin(models.Section, models.Section.id == models.ContentItem.section_id)
        .where(models.ContentItem.publication_campaign_id == campaign_id)
        .order_by(models.ContentItem.scheduled_at.asc().nullslast(), models.ContentItem.created_at.asc())
    ).all()
    return {
        "campaign": campaign,
        "items": [
            {
                "id": item.id,
                "topic": item.topic,
                "slug": item.slug,
                "section_id": item.section_id,
                "section_name": section_name,
                "status": item.status,
                "word_count": item.word_count,
                "include_casino_rating": item.include_casino_rating,
                "scheduled_at": item.scheduled_at,
                "published_at": item.published_at,
            }
            for item, section_name in rows
        ],
    }


@router.patch("/publication-campaigns/{campaign_id}", response_model=PublicationCampaignResponse)
def update_campaign(campaign_id: str, payload: PublicationCampaignUpdate, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    campaign = db.get(models.PublicationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Publication campaign not found")
    try:
        return update_campaign_status(db, campaign, payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publication-campaigns/{campaign_id}/reschedule", response_model=PublicationCampaignResponse)
def reschedule_publication_campaign(campaign_id: str, payload: PublicationCampaignReschedule, _: AuthUser, db: Session = Depends(get_db)) -> Any:
    campaign = db.scalar(
        select(models.PublicationCampaign)
        .where(models.PublicationCampaign.id == campaign_id)
        .with_for_update()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Publication campaign not found")
    try:
        return reschedule_campaign(db, campaign, payload.items_per_day, timezone_offset_minutes=payload.timezone_offset_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publication-campaigns/{campaign_id}/publish-all")
def publish_all_campaign_items(campaign_id: str, user: AuthUser, db: Session = Depends(get_db)) -> dict[str, Any]:
    campaign = db.get(models.PublicationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания публикации не найдена")
    if campaign.status == "publishing_all":
        raise HTTPException(status_code=409, detail="Пакетная публикация этой кампании уже выполняется")
    site = db.get(models.Site, campaign.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Проект кампании не найден")

    items = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.publication_campaign_id == campaign.id)
        .where(models.ContentItem.status != "published")
        .order_by(models.ContentItem.scheduled_at.asc().nullslast(), models.ContentItem.created_at.asc())
    ).all()
    if not items:
        raise HTTPException(status_code=400, detail="В кампании нет текстов для публикации")

    endpoint = get_settings().bulk_publication_endpoint.strip()
    request_payload = build_campaign_publication_bundle(db, campaign, site, items, user)
    log = models.PublicationLog(
        content_item_id=items[0].id,
        endpoint_url=endpoint or "bulk-publication-endpoint-not-configured",
        request_payload=request_payload,
    )
    db.add(log)
    db.flush()

    if not endpoint:
        log.response_status = 503
        log.error_message = "Эндпоинт пакетной публикации пока не настроен"
        db.commit()
        raise HTTPException(status_code=503, detail="Эндпоинт пакетной публикации пока не настроен. Адрес можно добавить позже без изменения кампании.")

    previous_status = campaign.status
    campaign.status = "publishing_all"
    campaign.completed_at = None
    db.commit()
    try:
        publish_campaign_bundle_job.delay(campaign.id, log.id)
    except Exception as exc:
        campaign.status = previous_status
        log.error_message = f"Не удалось поставить пакетную публикацию в фоновую очередь: {exc}"[:1000]
        db.commit()
        raise HTTPException(status_code=503, detail="Не удалось запустить пакетную публикацию") from exc
    return {
        "status": "queued",
        "campaign_id": campaign.id,
        "log_id": log.id,
        "items_count": len(items),
    }


@router.get("/publication-logs", response_model=list[PublicationLogResponse])
def list_logs(_: AdminUser, db: Session = Depends(get_db)) -> Any:
    return db.scalars(select(models.PublicationLog).order_by(models.PublicationLog.created_at.desc()).limit(200)).all()


@router.get("/admin/request-logs", response_model=list[AdminRequestLogResponse])
def list_admin_request_logs(_: AdminUser, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    db.execute(delete(models.PublicationLog).where(models.PublicationLog.created_at < cutoff))
    db.commit()
    rows = db.execute(
        select(models.PublicationLog, models.ContentItem.topic, models.Site.name)
        .outerjoin(models.ContentItem, models.ContentItem.id == models.PublicationLog.content_item_id)
        .outerjoin(models.Site, models.Site.id == models.ContentItem.site_id)
        .where(models.PublicationLog.created_at >= cutoff)
        .order_by(models.PublicationLog.created_at.desc())
        .limit(200)
    ).all()
    result: list[dict[str, Any]] = []
    for log, topic, site_name in rows:
        payload = log.request_payload if isinstance(log.request_payload, dict) else {}
        action = payload.get("action")
        is_menu_create = action == "menu_item_create"
        is_menu_update = action == "menu_item_update"
        is_menu_delete = action == "menu_item_delete"
        is_menu_sync = action == "menu_sync"
        is_menu_confirmation = action == "menu_item_sync_confirmed"
        is_campaign_publish_all = action == "campaign_publish_all"
        requested_by = payload.get("requested_by") if isinstance(payload.get("requested_by"), dict) else {}
        project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
        successful = log.response_status is not None and 200 <= log.response_status < 300 and not log.error_message
        result.append(
            {
                "id": log.id,
                "created_at": log.created_at,
                "project_name": str(project.get("name") or payload.get("project_name") or site_name or "Не определён"),
                "actor_username": str(requested_by.get("username") or payload.get("username") or "").strip() or None,
                "action": "Публикация всей кампании" if is_campaign_publish_all else "Отправка меню" if is_menu_sync else "Добавление пункта меню" if is_menu_create else "Изменение пункта меню" if is_menu_update else "Удаление пункта меню" if is_menu_delete else "Синхронизация пункта меню" if is_menu_confirmation else "Публикация контента",
                "item_name": str(payload.get("campaign", {}).get("name") if is_campaign_publish_all and isinstance(payload.get("campaign"), dict) else payload.get("name") or topic or "").strip() or None,
                "method": "POST",
                "destination": log.endpoint_url,
                "result": "Успешно" if successful else "Ошибка" if log.error_message or (log.response_status or 0) >= 400 else "Ожидает ответа",
                "status_code": log.response_status,
            }
        )
    return result


@router.post("/publication/run-due")
def run_due_publication(_: AdminUser) -> dict:
    from app.worker import publish_due_items

    result = publish_due_items.delay()
    return {"task_id": result.id, "queued_at": datetime.now(timezone.utc)}
