from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_public_url: str = "http://91.199.133.86"
    secret_key: str = Field(default="change-this-secret-before-production")
    admin_username: str = "admin"
    admin_password: str = "change-this-password"
    project_cache_url: str = "https://o59s9a012jd.com"
    project_cache_username: str = ""
    project_cache_password: str = ""
    alfan_url: str = "slf-hostesting.com"
    bulk_publication_endpoint: str = ""

    database_url: str = "postgresql+psycopg2://generator:generator@postgres:5432/generator"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    backend_cors_origins: str = "http://91.199.133.86,http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
