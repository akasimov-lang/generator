from datetime import datetime
from typing import Any

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
    target_words: int | None = None
    prompt_template: str | None = None


class ContentUpdate(BaseModel):
    generated_json: dict[str, Any]


class PublicationCampaignCreate(BaseModel):
    name: str
    site_id: str
    content_item_ids: list[str]
    start_at: datetime
    interval_minutes: int = 1440
    items_per_run: int = 1

