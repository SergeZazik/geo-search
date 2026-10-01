from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://geo:geo@localhost:5433/geo"
    db_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
