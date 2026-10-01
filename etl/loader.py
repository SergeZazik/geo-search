"""Load OSM records into PostGIS in batches.

Each batch is a single INSERT ... SELECT FROM unnest(...) statement with
ON CONFLICT DO UPDATE, so re-running an import updates rows in place instead
of duplicating them. PostGIS derives the representative point and the area
from the source geometry on the way in.
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from etl.osm import AdminAreaRecord, OsmRecord, PlaceRecord

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 5_000

UPSERT_PLACES = text("""
    INSERT INTO places AS p (
        osm_type, osm_id, category, kind, name, name_uk, name_en, name_ru, tags,
        geom, location, area_m2, updated_at
    )
    SELECT
        r.osm_type, r.osm_id, r.category, r.kind, r.name, r.name_uk, r.name_en, r.name_ru,
        r.tags::jsonb,
        g.geom,
        ST_PointOnSurface(g.geom),
        CASE WHEN ST_Dimension(g.geom) = 2 THEN ST_Area(g.geom::geography) END,
        now()
    FROM unnest(
        CAST(:osm_type AS text[]), CAST(:osm_id AS bigint[]),
        CAST(:category AS text[]), CAST(:kind AS text[]),
        CAST(:name AS text[]), CAST(:name_uk AS text[]),
        CAST(:name_en AS text[]), CAST(:name_ru AS text[]),
        CAST(:tags AS text[]), CAST(:wkb AS bytea[])
    ) AS r(osm_type, osm_id, category, kind, name, name_uk, name_en, name_ru, tags, wkb)
    CROSS JOIN LATERAL (
        SELECT CASE
            WHEN ST_Dimension(src) = 2
                THEN ST_Multi(ST_CollectionExtract(ST_MakeValid(src), 3))
            ELSE src
        END AS geom
        FROM ST_GeomFromWKB(r.wkb, 4326) AS src
    ) AS g
    WHERE NOT ST_IsEmpty(g.geom)
    ON CONFLICT (osm_type, osm_id) DO UPDATE SET
        category = EXCLUDED.category,
        kind = EXCLUDED.kind,
        name = EXCLUDED.name,
        name_uk = EXCLUDED.name_uk,
        name_en = EXCLUDED.name_en,
        name_ru = EXCLUDED.name_ru,
        tags = EXCLUDED.tags,
        geom = EXCLUDED.geom,
        location = EXCLUDED.location,
        area_m2 = EXCLUDED.area_m2,
        updated_at = EXCLUDED.updated_at
""")

UPSERT_ADMIN_AREAS = text("""
    INSERT INTO admin_areas AS a (
        osm_type, osm_id, admin_level, name, name_uk, name_en, name_ru, geom, updated_at
    )
    SELECT
        r.osm_type, r.osm_id, r.admin_level, r.name, r.name_uk, r.name_en, r.name_ru,
        g.geom,
        now()
    FROM unnest(
        CAST(:osm_type AS text[]), CAST(:osm_id AS bigint[]),
        CAST(:admin_level AS smallint[]),
        CAST(:name AS text[]), CAST(:name_uk AS text[]),
        CAST(:name_en AS text[]), CAST(:name_ru AS text[]),
        CAST(:wkb AS bytea[])
    ) AS r(osm_type, osm_id, admin_level, name, name_uk, name_en, name_ru, wkb)
    CROSS JOIN LATERAL (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromWKB(r.wkb, 4326)), 3))
            AS geom
    ) AS g
    WHERE NOT ST_IsEmpty(g.geom)
    ON CONFLICT (osm_type, osm_id) DO UPDATE SET
        admin_level = EXCLUDED.admin_level,
        name = EXCLUDED.name,
        name_uk = EXCLUDED.name_uk,
        name_en = EXCLUDED.name_en,
        name_ru = EXCLUDED.name_ru,
        geom = EXCLUDED.geom,
        updated_at = EXCLUDED.updated_at
""")


@dataclass
class LoadStats:
    places: int = 0
    admin_areas: int = 0


type RecordKey = tuple[str, int]


async def load_records(
    records: Iterable[OsmRecord],
    engine: AsyncEngine,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> LoadStats:
    stats = LoadStats()
    # Keyed by OSM id: a batch must not contain the same row twice,
    # or ON CONFLICT DO UPDATE fails.
    places: dict[RecordKey, PlaceRecord] = {}
    admin_areas: dict[RecordKey, AdminAreaRecord] = {}

    async with engine.connect() as conn:
        for record in records:
            if isinstance(record, PlaceRecord):
                places[record.osm_type, record.osm_id] = record
                if len(places) >= batch_size:
                    stats.places += await _upsert_places(conn, places.values())
                    places.clear()
                    logger.info("Places loaded: %d", stats.places)
            else:
                admin_areas[record.osm_type, record.osm_id] = record
                if len(admin_areas) >= batch_size:
                    stats.admin_areas += await _upsert_admin_areas(conn, admin_areas.values())
                    admin_areas.clear()

        if places:
            stats.places += await _upsert_places(conn, places.values())
        if admin_areas:
            stats.admin_areas += await _upsert_admin_areas(conn, admin_areas.values())

    logger.info("Done: %d places, %d admin areas", stats.places, stats.admin_areas)
    return stats


async def _upsert_places(conn: AsyncConnection, batch: Iterable[PlaceRecord]) -> int:
    rows = list(batch)
    result = await conn.execute(
        UPSERT_PLACES,
        {
            "osm_type": [r.osm_type for r in rows],
            "osm_id": [r.osm_id for r in rows],
            "category": [r.category for r in rows],
            "kind": [r.kind for r in rows],
            "name": [r.names.name for r in rows],
            "name_uk": [r.names.uk for r in rows],
            "name_en": [r.names.en for r in rows],
            "name_ru": [r.names.ru for r in rows],
            "tags": [json.dumps(r.tags, ensure_ascii=False) for r in rows],
            "wkb": [r.wkb for r in rows],
        },
    )
    await conn.commit()
    return result.rowcount


async def _upsert_admin_areas(conn: AsyncConnection, batch: Iterable[AdminAreaRecord]) -> int:
    rows = list(batch)
    result = await conn.execute(
        UPSERT_ADMIN_AREAS,
        {
            "osm_type": [r.osm_type for r in rows],
            "osm_id": [r.osm_id for r in rows],
            "admin_level": [r.admin_level for r in rows],
            "name": [r.names.name for r in rows],
            "name_uk": [r.names.uk for r in rows],
            "name_en": [r.names.en for r in rows],
            "name_ru": [r.names.ru for r in rows],
            "wkb": [r.wkb for r in rows],
        },
    )
    await conn.commit()
    return result.rowcount
