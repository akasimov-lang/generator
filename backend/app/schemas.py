from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AiProviderCreate(BaseModel):
    name: str
    endpoint_url: str
    model: str = "default"
    api_key: str | None = None


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


class SectionCreate(BaseModel):
    external_id: str
    name: str
    path: str


class GenerationTaskCreate(BaseModel):
    title: str
    geo: str
    language: str
    topics: list[str] = Field(min_length=1)
    site_id: str | None = None
    section_id: str | None = None
    ai_provider_id: str | None = None
    payload_mode: Literal["site_default", "simple_page", "full_site"] = "site_default"
    target_words: int | None = None
    prompt_template: str | None = None
    shortcode: str | None = None
    include_toc: bool = True
    include_faq: bool = True


class ContentUpdate(BaseModel):
    generated_json: dict[str, Any]


class PublicationCampaignCreate(BaseModel):
    name: str
    site_id: str
    content_item_ids: list[str]
    start_at: datetime
    interval_minutes: int = 1440
    items_per_run: int = 1
