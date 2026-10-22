"""Street search: fuzzy match by name, then places near every way of the street.

See the streets in tests/fixtures/sample.osm: the embankment with two ways in
the sample city and a namesake in Kyiv, and another embankment in the sample city.
"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import AdminArea
from app.repositories.places import NearbyPlaceHit, PlaceRepository
from app.repositories.streets import StreetRepository

EMBANKMENT = "Січеславська набережна"
OTHER_EMBANKMENT = "Набережна вулиця"


@pytest.fixture
async def session(api_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(api_engine) as session:
        yield session


async def area_id(session: AsyncSession, osm_id: int) -> int:
    query = select(AdminArea.id).where(AdminArea.osm_type == "relation", AdminArea.osm_id == osm_id)
    return (await session.execute(query)).scalar_one()


@pytest.fixture
async def city_id(session: AsyncSession) -> int:
    return await area_id(session, 400)


def ids(hits: list[NearbyPlaceHit]) -> list[str]:
    return [f"{hit.place.osm_type}/{hit.place.osm_id}" for hit in hits]


@pytest.mark.parametrize("phrase", ["Embankment", "січеславська"])
async def test_finds_street_by_part_of_its_name_in_any_language(
    session: AsyncSession, phrase: str
) -> None:
    # Three ways share the name, the match is one street.
    [match] = await StreetRepository(session).match(phrase, limit=5)
    assert match.name == EMBANKMENT
    assert match.similarity >= 0.6


async def test_generic_word_matches_several_streets_equally(session: AsyncSession) -> None:
    matches = await StreetRepository(session).match("набережная", limit=5)
    assert {match.name for match in matches} == {EMBANKMENT, OTHER_EMBANKMENT}
    assert matches[0].similarity == matches[1].similarity


async def test_unrelated_name_finds_no_street(session: AsyncSession) -> None:
    assert await StreetRepository(session).match("Шевченка", limit=5) == []


async def test_finds_street_inside_city(session: AsyncSession) -> None:
    # In Kyiv only the namesake of the embankment.
    kyiv = await area_id(session, 900)
    [match] = await StreetRepository(session).match("набережная", limit=5, area_id=kyiv)
    assert match.name == EMBANKMENT


async def test_places_near_street_are_measured_to_the_nearest_way(
    session: AsyncSession,
) -> None:
    hits = await PlaceRepository(session).near_street([EMBANKMENT], 280, [], 100)

    # The Kyiv cafe is ~55 m from the namesake way. The restaurant (node/3) is
    # ~261 m from way 610 and ~319 m from way 600, so it is found through 610.
    assert ids(hits) == ["node/8", "node/5", "node/1", "node/3"]
    distances = {f"{hit.place.osm_type}/{hit.place.osm_id}": hit.distance_m for hit in hits}
    assert distances["node/5"] == pytest.approx(111, abs=2)  # way 600; way 610 is ~185 m
    assert distances["node/3"] == pytest.approx(261, abs=3)


async def test_places_near_street_inside_city(session: AsyncSession, city_id: int) -> None:
    hits = await PlaceRepository(session).near_street([EMBANKMENT], 280, [], 100, area_id=city_id)
    # The namesake in Kyiv is outside the city, and so is the Kyiv cafe.
    assert ids(hits) == ["node/5", "node/1", "node/3"]


async def test_places_near_street_filter_by_type(session: AsyncSession) -> None:
    hits = await PlaceRepository(session).near_street([EMBANKMENT], 280, ["cafe"], 100)
    assert ids(hits) == ["node/8", "node/1"]


async def test_places_near_any_of_several_streets(session: AsyncSession, city_id: int) -> None:
    streets = [EMBANKMENT, OTHER_EMBANKMENT]
    hits = await PlaceRepository(session).near_street(streets, 280, ["cafe"], 100, area_id=city_id)
    # The far cafe is ~55 m from the other embankment, the near one ~222 m from way 600.
    assert ids(hits) == ["node/2", "node/1"]
    assert hits[0].distance_m == pytest.approx(56, abs=2)
