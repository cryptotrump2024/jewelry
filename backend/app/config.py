from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jewelry:jewelry@localhost:5432/jewelry"
    redis_url: str = "redis://localhost:6379/0"
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_api_key: str = ""
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "jewelry-media"

    # Single-tenant MVP: requests that match no tenant domain fall back to this
    # tenant. SaaS later resolves strictly by domain.
    default_tenant_slug: str = "default"

    # Bearer token protecting /admin endpoints. Empty = auth disabled (local
    # dev only) — set it in every deployed environment. Proper staff accounts
    # (users table, roles) replace this at SaaS time.
    admin_api_token: str = ""

    environment: str = "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
