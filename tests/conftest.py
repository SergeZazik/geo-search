"""Test fixtures.

Database tests run against a real PostGIS in a throwaway container
(testcontainers), migrated with Alembic and loaded through the real ETL from
a small synthetic OSM file. Docker must be running.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.config import Settings
from app.db import create_engine
from app.main import create_app
from etl.cli import load_file

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_OSM = ROOT / "tests" / "fixtures" / "sample.osm"
POSTGIS_IMAGE = os.environ.get("POSTGIS_IMAGE", "imresamu/postgis:16-3.5")

# Center point of the fixture data (see tests/fixtures/sample.osm).
CENTER_LAT, CENTER_LON = 48.4650, 35.0450


@pytest.fixture(scope="session")
def postgis() -> Iterator[PostgresContainer]:
    with PostgresContainer(
        POSTGIS_IMAGE, username="geo", password="geo", dbname="geo", driver="asyncpg"
    ) as container:
        yield container


def alembic_config(database_url: str) -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config


def migrate(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


async def create_database(postgis: PostgresContainer, name: str) -> str:
    """Create a migrated database in the container and return its URL."""
    url = make_url(postgis.get_connection_url())
    admin = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()

    database_url = url.set(database=name).render_as_string(hide_password=False)
    # Alembic's env.py runs its own event loop, so keep it off this one.
    await asyncio.to_thread(migrate, database_url)
    return database_url


@pytest.fixture(scope="session")
async def api_database_url(postgis: PostgresContainer) -> str:
    """Database with the sample data loaded once, shared by read-only API tests."""
    database_url = await create_database(postgis, "api")
    await load_file(SAMPLE_OSM, database_url)
    return database_url


@pytest.fixture(scope="session")
async def api_engine(api_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(api_database_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def client(api_database_url: str) -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(database_url=api_database_url))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@pytest.fixture(scope="session")
async def etl_database_url(postgis: PostgresContainer) -> str:
    return await create_database(postgis, "etl")


@pytest.fixture
async def etl_engine(etl_database_url: str) -> AsyncIterator[AsyncEngine]:
    """Engine for an empty database that each ETL test can write to."""
    engine = create_engine(etl_database_url)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE places, admin_areas"))
    yield engine
    await engine.dispose()
