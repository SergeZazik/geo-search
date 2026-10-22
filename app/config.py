from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Empty values count as unset: docker compose passes OPENAI_API_KEY= when there is none.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+asyncpg://geo:geo@localhost:5433/geo"
    db_echo: bool = False

    # Plain-language search (POST /search) is off without a key.
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_timeout_s: float = 20

    # Cache of parsed queries; without Redis every query goes to the LLM.
    redis_url: str | None = None
    search_cache_ttl_s: int = 7 * 24 * 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
