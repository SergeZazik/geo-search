"""Finding a city or a landmark by name, and places by type and size inside a city.

See tests/fixtures/sample.osm: the sample city (relation 400) with a small
village of the same name (way 950), and Kyiv mapped as a place=city multipolygon
(relation 900).
"""

from collections.abc import AsyncIterator, Sequence

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import AdminArea
from app.repositories.admin_areas import AdminAreaRepository
from app.repositories.places import PlaceHit, PlaceRepository


@pytest.fixture
async def session(api_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(api_engine) as session:
        yield session


async def area_id(session: AsyncSession, osm_id: int) -> int:
    query = select(AdminArea.id).where(AdminArea.osm_type == "relation", AdminArea.osm_id == osm_id)
    return (await session.execute(query)).scalar_one()


def ids(hits: Sequence[PlaceHit]) -> list[str]:
    return [f"{hit.place.osm_type}/{hit.place.osm_id}" for hit in hits]


@pytest.mark.parametrize("phrase", ["Київ", "Киев", "Kyiv"])
async def test_finds_city_by_name_in_any_language(session: AsyncSession, phrase: str) -> None:
    [match] = await AdminAreaRepository(session).match(phrase, limit=5)
    assert (match.name, match.place) == ("Київ", "city")
    assert match.id == await area_id(session, 900)


async def test_city_comes_before_a_smaller_namesake(session: AsyncSession) -> None:
    matches = await AdminAreaRepository(session).match("Тестоград", limit=5)
    assert [(match.name, match.place) for match in matches] == [
        ("Тестоград", "city"),
        ("Тестоград", "village"),
    ]
    assert matches[0].similarity == matches[1].similarity


async def test_unknown_city_finds_nothing(session: AsyncSession) -> None:
    assert await AdminAreaRepository(session).match("Харків", limit=5) == []


@pytest.mark.parametrize("phrase", ["Кава Тест", "Кофе Тест", "test coffee"])
async def test_finds_place_by_name_in_any_language(session: AsyncSession, phrase: str) -> None:
    match = await PlaceRepository(session).match(phrase)
    assert match is not None
    assert ids([match]) == ["node/1"]
    assert (match.lon, match.lat) == pytest.approx((35.0450, 48.4650))


async def test_finds_place_inside_city(session: AsyncSession) -> None:
    # Three cafes have "кава" in the name, one of them in Kyiv.
    match = await PlaceRepository(session).match("кава", area_id=await area_id(session, 900))
    assert match is not None
    assert ids([match]) == ["node/8"]


async def test_unknown_place_finds_nothing(session: AsyncSession) -> None:
    assert await PlaceRepository(session).match("Оперний театр") is None


async def test_finds_places_by_type_inside_city(session: AsyncSession) -> None:
    repository = PlaceRepository(session)
    city = await repository.find(["cafe"], 100, area_id=await area_id(session, 400))
    kyiv = await repository.find(["cafe"], 100, area_id=await area_id(session, 900))
    assert ids(city) == ["node/1", "node/2"]
    assert ids(kyiv) == ["node/8"]


async def test_finds_places_by_minimum_area(session: AsyncSession) -> None:
    # The park is 4 ha, the garden 1 ha, points have no area.
    hits = await PlaceRepository(session).find([], 100, min_area_m2=20_000)
    assert ids(hits) == ["way/100"]


async def test_places_near_a_point_by_minimum_area(session: AsyncSession) -> None:
    hits = await PlaceRepository(session).near(48.4650, 35.0450, 2_000, [], 100, min_area_m2=5_000)
    assert ids(hits) == ["way/100", "relation/300"]
