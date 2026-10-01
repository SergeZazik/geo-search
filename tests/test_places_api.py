from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import CENTER_LAT, CENTER_LON

# Covers the sample city; the Kyiv cafe (node/8) is outside.
CITY_BBOX = "35.03,48.45,35.06,48.48"


def ids(body: dict[str, Any]) -> list[str]:
    return [feature["id"] for feature in body["features"]]


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_bbox_returns_places_inside_as_geojson(client: AsyncClient) -> None:
    response = await client.get("/places", params={"bbox": CITY_BBOX})

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert sorted(ids(body)) == [
        "node/1",
        "node/2",
        "node/3",
        "node/5",
        "relation/300",
        "way/100",
        "way/200",
    ]


async def test_bbox_feature_shape(client: AsyncClient) -> None:
    # A tight box around the cafe at the center point.
    bbox = (
        f"{CENTER_LON - 0.0001},{CENTER_LAT - 0.0001},{CENTER_LON + 0.0001},{CENTER_LAT + 0.0001}"
    )
    response = await client.get("/places", params={"bbox": bbox})

    [feature] = response.json()["features"]
    assert feature["id"] == "node/1"
    assert feature["geometry"] == {"type": "Point", "coordinates": [CENTER_LON, CENTER_LAT]}
    properties = feature["properties"]
    assert properties["category"] == "amenity"
    assert properties["kind"] == "cafe"
    assert properties["name"] == "Кава Тест"
    assert properties["names"] == {"uk": "Кава Тест", "en": "Test Coffee", "ru": "Кофе Тест"}
    assert properties["osm_url"] == "https://www.openstreetmap.org/node/1"
    assert properties["tags"]["cuisine"] == "coffee_shop"
    assert properties["area_m2"] is None


async def test_bbox_filters_by_type(client: AsyncClient) -> None:
    cafes = await client.get("/places", params={"bbox": CITY_BBOX, "type": "cafe"})
    assert sorted(ids(cafes.json())) == ["node/1", "node/2"]

    several = await client.get("/places", params={"bbox": CITY_BBOX, "type": ["cafe", "park"]})
    assert sorted(ids(several.json())) == ["node/1", "node/2", "way/100"]


async def test_bbox_respects_limit(client: AsyncClient) -> None:
    response = await client.get("/places", params={"bbox": CITY_BBOX, "limit": 2})
    assert len(response.json()["features"]) == 2


async def test_polygons_have_area(client: AsyncClient) -> None:
    response = await client.get("/places", params={"bbox": CITY_BBOX, "type": "park"})
    [park] = response.json()["features"]
    assert park["properties"]["area_m2"] == pytest.approx(40_000, rel=0.01)


@pytest.mark.parametrize(
    "bbox",
    [
        "35.03,48.45,35.06",  # three numbers
        "a,b,c,d",
        "35.06,48.45,35.03,48.48",  # min_lon > max_lon
        "35.03,91,35.06,92",  # latitude out of range
    ],
)
async def test_bbox_rejects_invalid_values(client: AsyncClient, bbox: str) -> None:
    response = await client.get("/places", params={"bbox": bbox})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid bbox")


async def test_near_returns_places_within_radius_nearest_first(client: AsyncClient) -> None:
    response = await client.get(
        "/places/near", params={"lat": CENTER_LAT, "lon": CENTER_LON, "radius": 500}
    )

    assert response.status_code == 200
    features = response.json()["features"]
    assert [f["id"] for f in features] == ["node/1", "node/5", "node/3"]
    distances = [f["properties"]["distance_m"] for f in features]
    assert distances[0] == 0
    assert distances[1] == pytest.approx(134, abs=2)
    assert distances[2] == pytest.approx(303, abs=2)


async def test_near_radius_grows_the_result(client: AsyncClient) -> None:
    response = await client.get(
        "/places/near", params={"lat": CENTER_LAT, "lon": CENTER_LON, "radius": 1_100}
    )
    features = response.json()["features"]
    assert len(features) == 7
    distances = [f["properties"]["distance_m"] for f in features]
    assert distances == sorted(distances)
    far_cafe = next(f for f in features if f["id"] == "node/2")
    assert far_cafe["properties"]["distance_m"] == pytest.approx(1_001, abs=3)


async def test_near_filters_by_type(client: AsyncClient) -> None:
    response = await client.get(
        "/places/near",
        params={"lat": CENTER_LAT, "lon": CENTER_LON, "radius": 2_000, "type": "cafe"},
    )
    assert ids(response.json()) == ["node/1", "node/2"]


@pytest.mark.parametrize(
    "params",
    [
        {"lat": 91, "lon": CENTER_LON},
        {"lat": CENTER_LAT, "lon": 181},
        {"lat": CENTER_LAT, "lon": CENTER_LON, "radius": 0},
        {"lat": CENTER_LAT, "lon": CENTER_LON, "radius": 50_001},
        {"lat": CENTER_LAT, "lon": CENTER_LON, "limit": 1_001},
        {"lon": CENTER_LON},
    ],
)
async def test_near_rejects_invalid_params(client: AsyncClient, params: dict[str, float]) -> None:
    response = await client.get("/places/near", params=params)
    assert response.status_code == 422
