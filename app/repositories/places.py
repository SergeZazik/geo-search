from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.models import Place
from app.repositories.streets import street_segments
from app.schemas.places import BBox

SRID = 4326


@dataclass(frozen=True, slots=True)
class PlaceHit:
    place: Place
    lon: float
    lat: float


@dataclass(frozen=True, slots=True)
class NearbyPlaceHit(PlaceHit):
    distance_m: float


def _select_places(kinds: Sequence[str], *extra: ColumnElement[Any]) -> Select[Any]:
    # The full shape can be a large multipolygon; responses only need the point.
    query = select(Place, func.ST_X(Place.location), func.ST_Y(Place.location), *extra).options(
        defer(Place.geom), defer(Place.location)
    )
    if kinds:
        query = query.where(Place.kind.in_(kinds))
    return query


class PlaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def in_bbox_query(bbox: BBox, kinds: Sequence[str], limit: int) -> Select[Any]:
        envelope = func.ST_MakeEnvelope(
            bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat, SRID
        )
        return (
            _select_places(kinds)
            .where(func.ST_Intersects(Place.location, envelope))
            .order_by(Place.id)
            .limit(limit)
        )

    @staticmethod
    def near_query(
        lat: float, lon: float, radius_m: float, kinds: Sequence[str], limit: int
    ) -> Select[Any]:
        # geography(location) is the expression ix_places_location_geog is built on;
        # any other spelling of the cast and the planner falls back to a full scan.
        location = func.geography(Place.location)
        center = func.geography(func.ST_SetSRID(func.ST_MakePoint(lon, lat), SRID))
        distance = func.ST_Distance(location, center)
        return (
            _select_places(kinds, distance)
            .where(func.ST_DWithin(location, center, radius_m))
            .order_by(distance, Place.id)
            .limit(limit)
        )

    @staticmethod
    def near_street_query(
        street: str,
        radius_m: float,
        kinds: Sequence[str],
        limit: int,
        area_id: int | None = None,
    ) -> Select[Any]:
        # A street is many ways with one name: a place matches if it is near any of
        # them, and its distance is to the nearest one.
        segments = street_segments(street, area_id).subquery()
        location = func.geography(Place.location)
        line = func.geography(segments.c.geom)
        distance = func.min(func.ST_Distance(location, line))
        return (
            _select_places(kinds, distance)
            .join(segments, func.ST_DWithin(location, line, radius_m))
            .group_by(Place.id)
            .order_by(distance, Place.id)
            .limit(limit)
        )

    async def in_bbox(self, bbox: BBox, kinds: Sequence[str], limit: int) -> list[PlaceHit]:
        result = await self.session.execute(self.in_bbox_query(bbox, kinds, limit))
        return [PlaceHit(place, lon, lat) for place, lon, lat in result]

    async def near(
        self, lat: float, lon: float, radius_m: float, kinds: Sequence[str], limit: int
    ) -> list[NearbyPlaceHit]:
        result = await self.session.execute(self.near_query(lat, lon, radius_m, kinds, limit))
        return [NearbyPlaceHit(place, x, y, distance) for place, x, y, distance in result]

    async def near_street(
        self,
        street: str,
        radius_m: float,
        kinds: Sequence[str],
        limit: int,
        area_id: int | None = None,
    ) -> list[NearbyPlaceHit]:
        query = self.near_street_query(street, radius_m, kinds, limit, area_id)
        result = await self.session.execute(query)
        return [NearbyPlaceHit(place, x, y, distance) for place, x, y, distance in result]
