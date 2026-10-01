"""The API's queries must be able to use the GIST indexes.

The sample table is tiny, so the planner would pick a sequential scan anyway.
Disabling sequential scans makes it use an index if one matches the query,
which catches a query expression drifting away from the index definition.
"""

from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.repositories.places import PlaceRepository
from app.schemas.places import BBox
from tests.conftest import CENTER_LAT, CENTER_LON


async def explain(engine: AsyncEngine, query: Select[Any]) -> str:
    sql = query.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
    async with engine.connect() as conn:
        await conn.execute(text("SET enable_seqscan = off"))
        rows = await conn.execute(text(f"EXPLAIN {sql}"))
        return "\n".join(row[0] for row in rows)


async def test_bbox_query_uses_geometry_index(api_engine: AsyncEngine) -> None:
    bbox = BBox(min_lon=35.03, min_lat=48.45, max_lon=35.06, max_lat=48.48)
    plan = await explain(api_engine, PlaceRepository.in_bbox_query(bbox, [], 100))
    assert "ix_places_location " in plan + " "
    assert "ix_places_location_geog" not in plan


async def test_near_query_uses_geography_index(api_engine: AsyncEngine) -> None:
    # No type filter: on a tiny table the planner may prefer the btree on kind.
    query = PlaceRepository.near_query(CENTER_LAT, CENTER_LON, 500, [], 100)
    plan = await explain(api_engine, query)
    assert "ix_places_location_geog" in plan
