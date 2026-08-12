import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AiProvider(Base, TimestampMixin):
    __tablename__ = "ai_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), default="custom")
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    api_key: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), default="unchecked")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Site(Base, TimestampMixin):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    publication_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    sections_endpoint: Mapped[str] = mapped_column(Text, nullable=True)
    api_token: Mapped[str] = mapped_column(Text, nullable=True)
    payload_mode: Mapped[str] = mapped_column(String(40), default="simple_page")
    editor_version: Mapped[str] = mapped_column(String(40), default="2.31.0")
    default_menu: Mapped[dict] = mapped_column(JSON, default=lambda: {"header": [], "footer": []})
    default_banners: Mapped[list] = mapped_column(JSON, default=list)
    showcase_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    default_prompt_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    external_project_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    cache_canon: Mapped[str | None] = mapped_column(Text, nullable=True)
    homepage_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_pages_count: Mapped[int] = mapped_column(Integer, default=0)
    domains_count: Mapped[int] = mapped_column(Integer, default=0)
    project_status: Mapped[str] = mapped_column(String(32), default="working", index=True)
    is_test_project: Mapped[bool] = mapped_column(Boolean, default=False)
    has_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sections: Mapped[list["Section"]] = relationship(back_populates="site", cascade="all, delete-orphan")


class Section(Base, TimestampMixin):
    __tablename__ = "sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    path: Mapped[str] = mapped_column(String(240), nullable=False)
    menu_type: Mapped[str] = mapped_column(String(20), nullable=False, default="header", server_default="header")

    site: Mapped[Site] = relationship(back_populates="sections")


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class GenerationTask(Base, TimestampMixin):
    __tablename__ = "generation_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    section_id: Mapped[str | None] = mapped_column(ForeignKey("sections.id"), nullable=True)
    ai_provider_id: Mapped[str | None] = mapped_column(ForeignKey("ai_providers.id"), nullable=True)
    geo: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="created")
    payload_mode: Mapped[str] = mapped_column(String(40), default="site_default")
    topics_count: Mapped[int] = mapped_column(Integer, default=0)
    target_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_template_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    collect_competitors: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archived_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    items: Mapped[list["ContentItem"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    @property
    def created_by_username(self) -> str | None:
        return self.created_by.username if self.created_by else None


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    publication_campaign_id: Mapped[str | None] = mapped_column(ForeignKey("publication_campaigns.id"), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(240), nullable=False)
    generated_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    section_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    generation_prompt_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generation_progress: Mapped[int] = mapped_column(Integer, default=0)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_research_status: Mapped[str] = mapped_column(String(40), default="not_requested")
    competitor_research_progress: Mapped[int] = mapped_column(Integer, default=0)
    competitor_research_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    competitor_brief_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[GenerationTask] = relationship(back_populates="items")


class CompetitorQuery(Base, TimestampMixin):
    __tablename__ = "competitor_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    result_count: Mapped[int] = mapped_column(Integer, default=0)


class CompetitorResult(Base, TimestampMixin):
    __tablename__ = "competitor_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"), nullable=False, index=True)
    query_id: Mapped[str | None] = mapped_column(ForeignKey("competitor_queries.id"), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_provider: Mapped[str] = mapped_column(String(80), default="dataforseo")
    status: Mapped[str] = mapped_column(String(40), default="discovered")


class CompetitorPage(Base, TimestampMixin):
    __tablename__ = "competitor_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"), nullable=False, index=True)
    competitor_result_id: Mapped[str] = mapped_column(ForeignKey("competitor_results.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    headings: Mapped[list] = mapped_column(JSON, default=list)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tables: Mapped[list] = mapped_column(JSON, default=list)
    lists: Mapped[list] = mapped_column(JSON, default=list)
    faq: Mapped[list] = mapped_column(JSON, default=list)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublicationCampaign(Base, TimestampMixin):
    __tablename__ = "publication_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="created")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    items_per_run: Mapped[int] = mapped_column(Integer, default=1)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PublicationLog(Base, TimestampMixin):
    __tablename__ = "publication_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_item_id: Mapped[str | None] = mapped_column(ForeignKey("content_items.id"), nullable=True)
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
