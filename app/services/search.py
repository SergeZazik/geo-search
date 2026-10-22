"""Plain-language search: parse the query into a filter, resolve names, query places."""

from collections.abc import Sequence

from app.repositories.admin_areas import AdminAreaRepository, AreaMatch
from app.repositories.places import NearbyPlaceHit, PlaceHit, PlaceMatch, PlaceRepository
from app.repositories.streets import StreetRepository
from app.schemas.search import SearchMatches, SearchPlaceProperties, SearchResult
from app.services.places import place_properties, to_feature
from app.services.query_parser import QueryParser

DEFAULT_RADIUS_M = 500
# Streets with an equally good name are all used; more than this is not a landmark.
MAX_STREETS = 10


class NotFoundError(Exception):
    """A city or a landmark from the query is not in the data."""


class SearchService:
    def __init__(
        self,
        parser: QueryParser,
        places: PlaceRepository,
        streets: StreetRepository,
        areas: AdminAreaRepository,
    ) -> None:
        self.parser = parser
        self.places = places
        self.streets = streets
        self.areas = areas

    async def search(self, query: str, limit: int) -> SearchResult:
        search_filter = await self.parser.parse(query)
        kinds, min_area_m2 = search_filter.kinds, search_filter.min_area_m2

        area = await self._city(search_filter.city) if search_filter.city else None
        area_id = area.id if area else None

        hits: Sequence[PlaceHit]
        near: list[str] = []
        radius_m = None
        if search_filter.near_place:
            radius_m = search_filter.radius_m or DEFAULT_RADIUS_M
            landmark = await self._landmark(search_filter.near_place, area_id)
            if isinstance(landmark, PlaceMatch):
                near = [landmark.place.name or search_filter.near_place]
                hits = await self.places.near(
                    landmark.lat, landmark.lon, radius_m, kinds, limit, min_area_m2=min_area_m2
                )
            else:
                near = landmark
                hits = await self.places.near_street(
                    landmark, radius_m, kinds, limit, area_id=area_id, min_area_m2=min_area_m2
                )
        else:
            hits = await self.places.find(kinds, limit, area_id=area_id, min_area_m2=min_area_m2)

        matched = SearchMatches(
            city=area.name if area else None, near_place=near, radius_m=radius_m
        )
        return SearchResult(
            filter=search_filter,
            matched=matched,
            features=[to_feature(hit, _properties(hit)) for hit in hits],
        )

    async def _city(self, name: str) -> AreaMatch:
        matches = await self.areas.match(name, limit=1)
        if not matches:
            raise NotFoundError(f"No city matches {name!r}")
        return matches[0]

    async def _landmark(self, name: str, area_id: int | None) -> PlaceMatch | list[str]:
        """The best match among places and streets; a street wins a tie.

        A generic word such as "набережна" fits several streets equally well, and
        there is no telling which one the user meant, so all of them are returned.
        """
        place = await self.places.match(name, area_id)
        streets = await self.streets.match(name, MAX_STREETS, area_id)
        if place and (not streets or place.similarity > streets[0].similarity):
            return place
        if streets:
            return [street.name for street in streets if street.similarity == streets[0].similarity]
        raise NotFoundError(f"No place or street matches {name!r}")


def _properties(hit: PlaceHit) -> SearchPlaceProperties:
    distance_m = round(hit.distance_m, 1) if isinstance(hit, NearbyPlaceHit) else None
    return SearchPlaceProperties(**place_properties(hit.place).model_dump(), distance_m=distance_m)
