from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.models import Place
from app.repositories.admin_areas import area_geom
from app.repositories.names import name_matches, name_similarity
from app.repositories.streets import street_segments
from app.schemas.places import BBox

SRID = 4326

NAME_COLUMNS = (Place.name, Place.name_uk, Place.name_en, Place.name_ru)


@dataclass(frozen=True, slots=True)
class PlaceHit:
    place: Place
    lon: float
    lat: float


@dataclass(frozen=True, slots=True)
class NearbyPlaceHit(PlaceHit):
    distance_m: float


@dataclass(frozen=True, slots=True)
class PlaceMatch(PlaceHit):
    similarity: float


def _select_places(
    kinds: Sequence[str], *extra: ColumnElement[Any], min_area_m2: float | None = None
) -> Select[Any]:
    # The full shape can be a large multipolygon; responses only need the point.
    query = select(Place, func.ST_X(Place.location), func.ST_Y(Place.location), *extra).options(
        defer(Place.geom), defer(Place.location)
    )
    if kinds:
        query = query.where(Place.kind.in_(kinds))
    if min_area_m2 is not None:
        query = query.where(Place.area_m2 >= min_area_m2)
    return query


def _in_area(area_id: int) -> ColumnElement[bool]:
    return func.ST_Intersects(Place.location, area_geom(area_id))


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
    def find_query(
        kinds: Sequence[str],
        limit: int,
        *,
        area_id: int | None = None,
        min_area_m2: float | None = None,
    ) -> Select[Any]:
        """Places by type and size, inside an admin area if one is given."""
        query = _select_places(kinds, min_area_m2=min_area_m2)
        if area_id is not None:
            query = query.where(_in_area(area_id))
        return query.order_by(Place.id).limit(limit)

    @staticmethod
    def near_query(
        lat: float,
        lon: float,
        radius_m: float,
        kinds: Sequence[str],
        limit: int,
        *,
        min_area_m2: float | None = None,
    ) -> Select[Any]:
        # geography(location) is the expression ix_places_location_geog is built on;
        # any other spelling of the cast and the planner falls back to a full scan.
        location = func.geography(Place.location)
        center = func.geography(func.ST_SetSRID(func.ST_MakePoint(lon, lat), SRID))
        distance = func.ST_Distance(location, center)
        return (
            _select_places(kinds, distance, min_area_m2=min_area_m2)
            .where(func.ST_DWithin(location, center, radius_m))
            .order_by(distance, Place.id)
            .limit(limit)
        )

    @staticmethod
    def near_street_query(
        streets: Sequence[str],
        radius_m: float,
        kinds: Sequence[str],
        limit: int,
        *,
        area_id: int | None = None,
        min_area_m2: float | None = None,
    ) -> Select[Any]:
        # A street is many ways with one name: a place matches if it is near any of
        # them, and its distance is to the nearest one. Several names work the same way.
        segments = street_segments(streets, area_id).subquery()
        location = func.geography(Place.location)
        line = func.geography(segments.c.geom)
        distance = func.min(func.ST_Distance(location, line))
        return (
            _select_places(kinds, distance, min_area_m2=min_area_m2)
            .join(segments, func.ST_DWithin(location, line, radius_m))
            .group_by(Place.id)
            .order_by(distance, Place.id)
            .limit(limit)
        )

    @staticmethod
    def match_query(phrase: str, area_id: int | None = None) -> Select[Any]:
        """The place whose name matches the phrase best, e.g. a landmark to search around."""
        similarity = name_similarity(phrase, NAME_COLUMNS)
        query = _select_places([], similarity).where(name_matches(phrase, NAME_COLUMNS))
        if area_id is not None:
            query = query.where(_in_area(area_id))
        # Equally good names (a chain of shops): the largest object, a park before a kiosk.
        largest = Place.area_m2.desc().nulls_last()
        return query.order_by(similarity.desc(), largest, Place.id).limit(1)

    async def in_bbox(self, bbox: BBox, kinds: Sequence[str], limit: int) -> list[PlaceHit]:
        result = await self.session.execute(self.in_bbox_query(bbox, kinds, limit))
        return [PlaceHit(place, lon, lat) for place, lon, lat in result]

    async def near(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        kinds: Sequence[str],
        limit: int,
        *,
        min_area_m2: float | None = None,
    ) -> list[NearbyPlaceHit]:
        query = self.near_query(lat, lon, radius_m, kinds, limit, min_area_m2=min_area_m2)
        result = await self.session.execute(query)
        return [NearbyPlaceHit(place, x, y, distance) for place, x, y, distance in result]

    async def near_street(
        self,
        streets: Sequence[str],
        radius_m: float,
        kinds: Sequence[str],
        limit: int,
        *,
        area_id: int | None = None,
        min_area_m2: float | None = None,
    ) -> list[NearbyPlaceHit]:
        query = self.near_street_query(
            streets, radius_m, kinds, limit, area_id=area_id, min_area_m2=min_area_m2
        )
        result = await self.session.execute(query)
        return [NearbyPlaceHit(place, x, y, distance) for place, x, y, distance in result]

    async def find(
        self,
        kinds: Sequence[str],
        limit: int,
        *,
        area_id: int | None = None,
        min_area_m2: float | None = None,
    ) -> list[PlaceHit]:
        query = self.find_query(kinds, limit, area_id=area_id, min_area_m2=min_area_m2)
        result = await self.session.execute(query)
        return [PlaceHit(place, lon, lat) for place, lon, lat in result]

    async def match(self, phrase: str, area_id: int | None = None) -> PlaceMatch | None:
        row = (await self.session.execute(self.match_query(phrase, area_id))).first()
        return PlaceMatch(*row) if row else None
