from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI
from redis.asyncio import Redis

from app.api import health, places, search
from app.cache import FilterCache
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.services.query_parser import QueryParser

DESCRIPTION = """
Search places on the map of Ukraine. Results are GeoJSON.

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the Open Database License (ODbL).
"""


def create_app(settings: Settings | None = None, *, openai: AsyncOpenAI | None = None) -> FastAPI:
    """Build the app. `openai` replaces the client built from the settings (in tests)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url, echo=settings.db_echo)
        app.state.sessionmaker = create_sessionmaker(engine)

        llm = openai
        if llm is None and settings.openai_api_key:
            llm = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=settings.openai_timeout_s,
            )
        # Short timeouts: a stuck cache must not hold up a search.
        redis = (
            Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
            if settings.redis_url
            else None
        )
        cache = FilterCache(redis, settings.search_cache_ttl_s) if redis else None
        app.state.query_parser = QueryParser(llm, settings.openai_model, cache) if llm else None

        yield

        await engine.dispose()
        if redis:
            await redis.aclose()
        if llm:
            await llm.close()

    app = FastAPI(title="geo-search", version="0.1.0", description=DESCRIPTION, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(places.router)
    app.include_router(search.router)
    return app


app = create_app()
