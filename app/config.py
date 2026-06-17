from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kvk_api_key: str | None = Field(default=None, alias="KVK_API_KEY")
    kvk_api_base_url: str = Field(
        default="https://api.kvk.nl/api/v1", alias="KVK_API_BASE_URL"
    )
    http_timeout_seconds: float = Field(default=10.0, alias="HTTP_TIMEOUT_SECONDS")
    user_agent: str = Field(
        default="AresisLeadEnrichment/0.1 (+https://aresis.nl)",
        alias="USER_AGENT",
    )
    max_pages_per_domain: int = Field(default=6, alias="MAX_PAGES_PER_DOMAIN")
    domains_monitor_api_token: str | None = Field(
        default=None, alias="DOMAINS_MONITOR_API_TOKEN"
    )
    snapshot_database_path: str = Field(
        default="/data/leadsgen.db", alias="SNAPSHOT_DATABASE_PATH"
    )
    snapshot_output_dir: str = Field(default="/data/exports", alias="SNAPSHOT_OUTPUT_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
