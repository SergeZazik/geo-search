import pytest

from etl.osm import AdminAreaRecord, OsmReader, PlaceRecord
from tests.conftest import SAMPLE_OSM


@pytest.fixture(scope="module")
def records() -> list[PlaceRecord | AdminAreaRecord]:
    return list(OsmReader(SAMPLE_OSM))


@pytest.fixture(scope="module")
def places(records: list[PlaceRecord | AdminAreaRecord]) -> dict[str, PlaceRecord]:
    return {f"{r.osm_type}/{r.osm_id}": r for r in records if isinstance(r, PlaceRecord)}


def test_reads_points_lines_and_areas(places: dict[str, PlaceRecord]) -> None:
    assert sorted(places) == [
        "node/1",
        "node/2",
        "node/3",
        "node/5",
        "node/8",
        "relation/300",
        "way/100",
        "way/200",
    ]


def test_skips_street_furniture_and_objects_without_poi_tags(
    places: dict[str, PlaceRecord],
) -> None:
    assert "node/4" not in places  # bench
    assert "node/6" not in places  # bus stop


def test_untagged_member_ways_are_not_places(places: dict[str, PlaceRecord]) -> None:
    assert "way/301" not in places
    assert "way/401" not in places


def test_amenity_takes_priority_over_tourism(places: dict[str, PlaceRecord]) -> None:
    restaurant = places["node/3"]
    assert (restaurant.category, restaurant.kind) == ("amenity", "restaurant")
    assert restaurant.tags["tourism"] == "hotel"


def test_multi_valued_tag_uses_first_value(places: dict[str, PlaceRecord]) -> None:
    assert places["node/5"].kind == "supermarket"


def test_keeps_names_in_all_languages(places: dict[str, PlaceRecord]) -> None:
    names = places["node/1"].names
    assert (names.name, names.uk, names.en, names.ru) == (
        "Кава Тест",
        "Кава Тест",
        "Test Coffee",
        "Кофе Тест",
    )


def test_reads_admin_boundaries_of_configured_levels_only(
    records: list[PlaceRecord | AdminAreaRecord],
) -> None:
    areas = [r for r in records if isinstance(r, AdminAreaRecord)]
    assert [(a.osm_id, a.admin_level, a.names.en) for a in areas] == [(400, 8, "Testograd")]
