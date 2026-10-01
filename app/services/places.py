from collections.abc import Sequence

from app.models import Place
from app.repositories.places import PlaceHit, PlaceRepository
from app.schemas.geojson import Feature, Point
from app.schemas.places import (
    BBox,
    NearbyPlaceCollection,
    NearbyPlaceProperties,
    PlaceCollection,
    PlaceProperties,
)

# OSM stores coordinates with 7 decimal places (~1 cm).
COORDINATE_PRECISION = 7


class PlaceService:
    def __init__(self, repository: PlaceRepository) -> None:
        self.repository = repository

    async def in_bbox(self, bbox: BBox, kinds: Sequence[str], limit: int) -> PlaceCollection:
        hits = await self.repository.in_bbox(bbox, kinds, limit)
        return PlaceCollection(features=[_feature(hit, _properties(hit.place)) for hit in hits])

    async def near(
        self, lat: float, lon: float, radius_m: float, kinds: Sequence[str], limit: int
    ) -> NearbyPlaceCollection:
        hits = await self.repository.near(lat, lon, radius_m, kinds, limit)
        return NearbyPlaceCollection(
            features=[
                _feature(
                    hit,
                    NearbyPlaceProperties(
                        **_properties(hit.place).model_dump(),
                        distance_m=round(hit.distance_m, 1),
                    ),
                )
                for hit in hits
            ]
        )


def _feature[P: PlaceProperties](hit: PlaceHit, properties: P) -> Feature[P]:
    return Feature[P](
        id=f"{hit.place.osm_type}/{hit.place.osm_id}",
        geometry=Point(
            coordinates=(
                round(hit.lon, COORDINATE_PRECISION),
                round(hit.lat, COORDINATE_PRECISION),
            )
        ),
        properties=properties,
    )


def _properties(place: Place) -> PlaceProperties:
    localized = {"uk": place.name_uk, "en": place.name_en, "ru": place.name_ru}
    return PlaceProperties(
        osm_type=place.osm_type,
        osm_id=place.osm_id,
        osm_url=f"https://www.openstreetmap.org/{place.osm_type}/{place.osm_id}",
        category=place.category,
        kind=place.kind,
        name=place.name,
        names={lang: name for lang, name in localized.items() if name},
        area_m2=round(place.area_m2, 1) if place.area_m2 is not None else None,
        tags=place.tags,
    )
