from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.api.deps import PlaceServiceDep
from app.schemas.places import BBox, NearbyPlaceCollection, PlaceCollection

router = APIRouter(prefix="/places", tags=["places"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 1_000
MAX_RADIUS_M = 50_000

KindsQuery = Annotated[
    list[str] | None,
    Query(
        alias="type",
        description="OSM tag value to filter by, e.g. cafe, park, pharmacy. Repeat for several.",
    ),
]
LimitQuery = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


def parse_bbox(raw: str) -> BBox:
    try:
        return BBox.parse(raw)
    except (ValueError, ValidationError) as exc:
        detail = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Invalid bbox: {detail}"
        ) from exc


@router.get("", summary="Places inside a bounding box")
async def places_in_bbox(
    service: PlaceServiceDep,
    bbox: Annotated[
        str,
        Query(
            description="min_lon,min_lat,max_lon,max_lat (WGS 84)",
            examples=["35.02,48.45,35.07,48.48"],
        ),
    ],
    kinds: KindsQuery = None,
    limit: LimitQuery = DEFAULT_LIMIT,
) -> PlaceCollection:
    return await service.in_bbox(parse_bbox(bbox), kinds or [], limit)


@router.get("/near", summary="Places within a radius, nearest first")
async def places_near(
    service: PlaceServiceDep,
    lat: Annotated[float, Query(ge=-90, le=90, examples=[48.4647])],
    lon: Annotated[float, Query(ge=-180, le=180, examples=[35.0462])],
    radius: Annotated[float, Query(gt=0, le=MAX_RADIUS_M, description="Meters")] = 500,
    kinds: KindsQuery = None,
    limit: LimitQuery = DEFAULT_LIMIT,
) -> NearbyPlaceCollection:
    return await service.near(lat, lon, radius, kinds or [], limit)
