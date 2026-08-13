from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8)
    is_admin: bool = False


class UserUpdate(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class FavoriteSitesResponse(BaseModel):
    site_ids: list[str]


class AiProviderCreate(BaseModel):
    name: str
    endpoint_url: str
    model: str = "default"
    api_key: str | None = None
    api_login: str | None = None
    api_password: str | None = None
    provider_type: Literal["custom", "gemini", "dataforseo"] = "custom"


class AiProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    provider_type: str
    endpoint_url: str
    model: str
    prompt_tokens_used: int
    completion_tokens_used: int
    total_tokens_used: int
    last_used_at: datetime | None
    validation_status: str
    validation_message: str | None
    validated_at: datetime | None
    is_active: bool
    created_at: datetime


class SiteCreate(BaseModel):
    name: str
    base_url: str
    publication_endpoint: str
    sections_endpoint: str | None = None
    api_token: str | None = None
    payload_mode: Literal["simple_page", "full_site"] = "simple_page"
    editor_version: str = "2.31.0"
    default_menu: dict[str, Any] = Field(default_factory=lambda: {"header": [], "footer": []})
    default_banners: list[str] = Field(default_factory=list)
    showcase_payload: dict[str, Any] | None = None


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str
    publication_endpoint: str
    payload_mode: str
    editor_version: str
    default_menu: dict[str, Any]
    menu_library: list[dict[str, Any]]
    default_banners: list[str]
    showcase_payload: dict[str, Any] | None
    default_prompt_template_id: str | None
    external_project_id: str | None
    cache_canon: str | None
    cache_language: str | None
    cache_geo: str | None
    homepage_title: str | None
    internal_pages_count: int
    domains_count: int
    cache_domains: list[str]
    cache_server_ip: str | None
    project_status: str
    is_test_project: bool
    has_menu: bool
    cache_synced_at: datetime | None
    menu_capabilities_checked_at: datetime | None
    header_menu_rendered: bool | None
    header_menu_nested: bool | None
    footer_menu_rendered: bool | None
    footer_menu_nested: bool | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectCacheItemResponse(BaseModel):
    external_project_id: str
    name: str
    canon: str | None
    language: str | None
    geo: str | None
    homepage_title: str | None
    internal_pages_count: int
    domains_count: int
    domains: list[str]
    has_menu: bool
    is_working_project: bool


class ProjectCacheSyncResponse(BaseModel):
    cache_count: int
    matched_count: int
    created_count: int
    updated_count: int
    confirmed_sections_count: int = 0
    projects: list[ProjectCacheItemResponse]


class ProjectCacheSyncRequest(BaseModel):
    names: list[str] = Field(default_factory=list, max_length=200)


class SiteStatusUpdate(BaseModel):
    project_status: Literal["test", "working", "not_in_focus", "duplicate"]


class DuplicateSitesDeleteResponse(BaseModel):
    deleted_count: int
    skipped_count: int


class SectionCreate(BaseModel):
    external_id: str
    name: str
    path: str
    menu_type: Literal["header", "footer"] = "header"
    parent_id: str | None = None


class SectionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=240)


class MenuLibraryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=240)
    external_id: str = Field(min_length=1, max_length=160)
    russian_name: str = Field(default="", max_length=160)


class MenuLibraryItemResponse(MenuLibraryItemCreate):
    pass


class MenuLibraryItemUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=240)
    russian_name: str = Field(default="", max_length=160)


class SectionsBulkCreate(BaseModel):
    items: list[SectionCreate] = Field(min_length=1, max_length=10)


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    external_id: str
    name: str
    path: str
    menu_type: str
    parent_id: str | None
    is_temporary_parent: bool
    sync_status: str
    synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SectionAdoptResponse(BaseModel):
    section: SectionResponse
    created: bool


class SectionsBulkCreateResponse(BaseModel):
    created_count: int
    skipped_count: int
    sections: list[SectionResponse]


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    content: str = Field(min_length=20)
    is_default: bool = False


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    content: str | None = Field(default=None, min_length=20)
    is_default: bool | None = None
    site_id: str | None = None


class PromptTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str | None
    name: str
    content: str
    is_default: bool
    used_by_projects: int = 0
    generated_texts_count: int = 0
    created_at: datetime
    updated_at: datetime


class PromptGeneratedContentResponse(BaseModel):
    id: str
    task_id: str
    site_id: str | None
    site_name: str | None
    topic: str
    slug: str
    status: str
    word_count: int
    generation_prompt_name: str | None
    generated_at: datetime | None
    updated_at: datetime


class PublicationContentResponse(BaseModel):
    id: str
    task_id: str
    site_id: str
    topic: str
    slug: str
    status: str
    word_count: int
    generated_at: datetime | None
    published_at: datetime | None
    updated_at: datetime


class GenerationTaskCreate(BaseModel):
    title: str | None = Field(default=None, max_length=180)
    geo: str
    language: str
    topics: list[str] = Field(min_length=1, max_length=30)
    site_id: str | None = None
    section_id: str | None = None
    ai_provider_id: str | None = None
    payload_mode: Literal["site_default", "simple_page", "full_site"] = "site_default"
    target_words: int | None = Field(default=2000, ge=300, le=8000)
    prompt_template_name: str | None = Field(default=None, max_length=160)
    prompt_template: str | None = None
    shortcode: str | None = None
    include_toc: bool = True
    include_faq: bool = True
    collect_competitors: bool = False
    save_as_draft: bool = False


class GenerationTaskSectionUpdate(BaseModel):
    section_id: str | None = None


class GenerationTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_by_user_id: str | None = None
    created_by_username: str | None = None
    site_id: str | None
    section_id: str | None
    ai_provider_id: str | None
    geo: str
    language: str
    status: str
    payload_mode: str
    topics_count: int
    target_words: int | None
    prompt_template_name: str | None
    prompt_template: str | None
    collect_competitors: bool
    archived_at: datetime | None = None
    archived_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ContentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    site_id: str | None
    publication_campaign_id: str | None
    section_id: str | None
    topic: str
    slug: str
    generated_json: dict[str, Any]
    status: str
    word_count: int
    generation_prompt_name: str | None
    generated_at: datetime | None
    generation_progress: int = 0
    generation_error: str | None = None
    competitor_research_status: str
    competitor_research_progress: int = 0
    competitor_research_error: str | None = None
    competitor_brief: dict[str, Any] | None
    idempotency_key: str
    scheduled_at: datetime | None
    published_at: datetime | None
    published_url: str | None
    created_at: datetime
    updated_at: datetime


class SiteOverviewSiteResponse(BaseModel):
    id: str
    name: str
    base_url: str
    payload_mode: str
    publication_endpoint: str


class SiteOverviewStatsResponse(BaseModel):
    tasks: int
    menu_items: int
    generated: int
    approved: int
    scheduled: int
    published: int
    failed: int
    next_publication_at: datetime | None


class SiteOverviewResponse(BaseModel):
    site: SiteOverviewSiteResponse
    stats: SiteOverviewStatsResponse
    recent_content: list[ContentItemResponse]


class TaskDetailsResponse(BaseModel):
    task: GenerationTaskResponse
    items: list[ContentItemResponse]


class CompetitorQueriesUpdate(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=5)


class CompetitorQueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_item_id: str
    query: str
    position: int
    status: str
    result_count: int
    created_at: datetime
    updated_at: datetime


class CompetitorResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_item_id: str
    query_id: str | None
    query_text: str
    position: int
    url: str
    normalized_url: str
    title: str | None
    snippet: str | None
    source_provider: str
    status: str
    created_at: datetime
    updated_at: datetime


class CompetitorPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_item_id: str
    competitor_result_id: str
    url: str
    http_status: int | None
    title: str | None
    h1: str | None
    meta_description: str | None
    headings: list[Any]
    text_content: str | None
    tables: list[Any]
    lists: list[Any]
    faq: list[Any]
    word_count: int
    error_message: str | None
    fetched_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompetitorResearchResponse(BaseModel):
    content_item_id: str
    status: str
    progress: int = 0
    error: str | None = None
    brief: dict[str, Any] | None
    queries: list[CompetitorQueryResponse]
    results: list[CompetitorResultResponse]
    pages: list[CompetitorPageResponse]


class ContentUpdate(BaseModel):
    generated_json: dict[str, Any] | None = None
    section_id: str | None = None


class PublicationCampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    site_id: str
    content_item_ids: list[str] = Field(min_length=1)
    start_at: datetime
    interval_minutes: int = Field(default=1440, ge=1)
    items_per_run: int = Field(default=1, ge=1, le=100)


class PublicationCampaignUpdate(BaseModel):
    action: Literal["pause", "resume", "stop"]


class PublicationCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    site_id: str
    status: str
    interval_minutes: int
    items_per_run: int
    start_at: datetime
    created_at: datetime
    updated_at: datetime


class SitePublicationCampaignCreate(BaseModel):
    name: str
    content_item_ids: list[str]
    start_at: datetime
    items_per_day: int = Field(default=1, ge=1, le=24)


class PublicationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_item_id: str | None
    endpoint_url: str
    request_payload: dict[str, Any] | None
    response_status: int | None
    response_body: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AdminRequestLogResponse(BaseModel):
    id: str
    created_at: datetime
    project_name: str
    action: str
    item_name: str | None
    method: str
    destination: str
    result: str
