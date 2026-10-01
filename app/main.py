from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, places
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker

DESCRIPTION = """
Search places on the map of Ukraine. Results are GeoJSON.

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the Open Database License (ODbL).
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url, echo=settings.db_echo)
        app.state.sessionmaker = create_sessionmaker(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="geo-search", version="0.1.0", description=DESCRIPTION, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(places.router)
    return app


app = create_app()
