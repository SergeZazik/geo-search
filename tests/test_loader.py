import struct

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import AdminArea, Place
from etl.cli import load_file
from etl.loader import load_records
from etl.osm import Names, PlaceRecord
from tests.conftest import SAMPLE_OSM

# Little-endian WKB for POINT(35.05 48.47)
POINT_WKB = struct.pack("<BIdd", 1, 1, 35.05, 48.47)


def make_place(osm_id: int, name: str) -> PlaceRecord:
    return PlaceRecord(
        osm_type="node",
        osm_id=osm_id,
        category="amenity",
        kind="cafe",
        names=Names(name=name, uk=None, en=None, ru=None),
        tags={"amenity": "cafe", "name": name},
        wkb=POINT_WKB,
    )


async def count(engine: AsyncEngine, model: type[Place] | type[AdminArea]) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(select(func.count()).select_from(model))).scalar_one()


async def test_loads_sample_file(etl_engine: AsyncEngine, etl_database_url: str) -> None:
    stats = await load_file(SAMPLE_OSM, etl_database_url)

    assert (stats.places, stats.admin_areas) == (8, 1)
    assert await count(etl_engine, Place) == 8
    assert await count(etl_engine, AdminArea) == 1


async def test_reloading_updates_rows_instead_of_duplicating(
    etl_engine: AsyncEngine, etl_database_url: str
) -> None:
    await load_file(SAMPLE_OSM, etl_database_url)
    await load_file(SAMPLE_OSM, etl_database_url)

    assert await count(etl_engine, Place) == 8
    assert await count(etl_engine, AdminArea) == 1


async def test_upsert_overwrites_changed_attributes(etl_engine: AsyncEngine) -> None:
    await load_records([make_place(1, "Old name")], etl_engine)
    await load_records([make_place(1, "New name")], etl_engine)

    async with etl_engine.connect() as conn:
        names = (await conn.execute(select(Place.name))).scalars().all()
    assert names == ["New name"]


async def test_duplicates_within_a_batch_keep_the_last_record(etl_engine: AsyncEngine) -> None:
    records = [make_place(1, "First"), make_place(2, "Other"), make_place(1, "Last")]

    await load_records(records, etl_engine, batch_size=10)

    async with etl_engine.connect() as conn:
        names = (await conn.execute(select(Place.name).order_by(Place.osm_id))).scalars().all()
    assert names == ["Last", "Other"]


async def test_small_batches_load_everything(etl_engine: AsyncEngine) -> None:
    records = [make_place(i, f"Cafe {i}") for i in range(1, 8)]

    stats = await load_records(records, etl_engine, batch_size=3)

    assert stats.places == 7
    assert await count(etl_engine, Place) == 7


async def test_derives_location_and_area_from_geometry(
    etl_engine: AsyncEngine, etl_database_url: str
) -> None:
    await load_file(SAMPLE_OSM, etl_database_url)

    async with etl_engine.connect() as conn:
        park = (
            await conn.execute(
                text("""
                    SELECT GeometryType(geom) AS geom_type, area_m2,
                           ST_Contains(geom, location) AS inside
                    FROM places WHERE osm_type = 'way' AND osm_id = 100
                """)
            )
        ).one()
        cafe_area = (
            await conn.execute(
                select(Place.area_m2).where(Place.osm_type == "node", Place.osm_id == 1)
            )
        ).scalar_one()

    assert park.geom_type == "MULTIPOLYGON"
    assert park.area_m2 == pytest.approx(40_000, rel=0.01)  # 200 x 200 m
    assert park.inside
    assert cafe_area is None
