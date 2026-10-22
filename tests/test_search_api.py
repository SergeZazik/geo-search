"""POST /search end to end, with the LLM answer scripted by each test.

The parsed filter is what the model would return; the rest runs for real:
name lookups and spatial queries in PostGIS, the cache in Redis.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.config import Settings
from app.main import create_app
from app.schemas.search import SearchFilter
from tests.fake_openai import FakeOpenAI


def search_filter(**fields: Any) -> dict[str, Any]:
    """A filter as the model returns it: every field present, unused ones empty."""
    return SearchFilter().model_dump() | fields


def ids(body: dict[str, Any]) -> list[str]:
    return [feature["id"] for feature in body["features"]]


@pytest.fixture
async def client(
    api_database_url: str, redis_url: str, redis: Redis, fake_openai: FakeOpenAI
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        Settings(database_url=api_database_url, redis_url=redis_url), openai=fake_openai.client
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_cafes_near_the_embankment(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    parsed = search_filter(kinds=["cafe"], city="Тестоград", near_place="набережна")
    fake_openai.answer(parsed)

    response = await client.post("/search", json={"query": "кафе возле набережной в Тестограде"})

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["filter"] == parsed
    # "набережна" fits both embankments equally well: the search goes near either.
    assert body["matched"] == {
        "city": "Тестоград",
        "near_place": ["Набережна вулиця", "Січеславська набережна"],
        "radius_m": 500,
    }
    assert ids(body) == ["node/2", "node/1"]
    distances = [feature["properties"]["distance_m"] for feature in body["features"]]
    assert distances == [pytest.approx(56, abs=2), pytest.approx(222, abs=2)]


async def test_places_near_a_named_place(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.answer(search_filter(kinds=["restaurant"], near_place="Кофе Тест", radius_m=400))

    body = (await client.post("/search", json={"query": "ресторан возле Кофе Тест"})).json()

    assert body["matched"] == {"city": None, "near_place": ["Кава Тест"], "radius_m": 400}
    assert ids(body) == ["node/3"]
    assert body["features"][0]["properties"]["distance_m"] == pytest.approx(303, abs=2)


async def test_places_inside_a_city(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.answer(search_filter(kinds=["cafe"], city="Київ"))

    body = (await client.post("/search", json={"query": "кофейни Киева"})).json()

    assert body["matched"] == {"city": "Київ", "near_place": [], "radius_m": None}
    assert ids(body) == ["node/8"]
    assert body["features"][0]["properties"]["distance_m"] is None


async def test_large_parks(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.answer(search_filter(kinds=["park", "garden"], min_area_m2=20_000))

    body = (await client.post("/search", json={"query": "парки больше двух гектаров"})).json()

    assert ids(body) == ["way/100"]


async def test_respects_limit(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.answer(search_filter(city="Тестоград"))

    response = await client.post("/search", json={"query": "что есть в Тестограде", "limit": 2})

    assert len(response.json()["features"]) == 2


async def test_repeated_query_is_parsed_once(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.answer(search_filter(kinds=["cafe"], city="Київ"))

    first = await client.post("/search", json={"query": "Кофейни Киева"})
    second = await client.post("/search", json={"query": "  кофейни   киева"})

    assert second.json() == first.json()
    assert len(fake_openai.requests) == 1


async def test_query_that_cannot_be_parsed_is_422(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    fake_openai.answer(search_filter())

    response = await client.post("/search", json={"query": "как дела?"})

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Could not understand the query: The query does not say what to look for"
    )


@pytest.mark.parametrize(
    ("parsed", "detail"),
    [
        (search_filter(kinds=["cafe"], city="Харків"), "No city matches 'Харків'"),
        (
            search_filter(kinds=["cafe"], near_place="Оперний театр"),
            "No place or street matches 'Оперний театр'",
        ),
    ],
)
async def test_unknown_city_or_landmark_is_404(
    client: AsyncClient, fake_openai: FakeOpenAI, parsed: dict[str, Any], detail: str
) -> None:
    fake_openai.answer(parsed)

    response = await client.post("/search", json={"query": "кафе"})

    assert response.status_code == 404
    assert response.json()["detail"] == detail


async def test_llm_failure_is_503(client: AsyncClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.fail(500)

    response = await client.post("/search", json={"query": "кафе в Киеве"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Search is unavailable, try again later"


@pytest.mark.parametrize("payload", [{"query": ""}, {"query": "кафе", "limit": 0}, {}])
async def test_invalid_request_is_422(client: AsyncClient, payload: dict[str, Any]) -> None:
    response = await client.post("/search", json=payload)
    assert response.status_code == 422


async def test_search_is_off_without_api_key(api_database_url: str) -> None:
    app = create_app(Settings(database_url=api_database_url, openai_api_key=None, redis_url=None))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post("/search", json={"query": "кафе в Киеве"})
        health = await client.get("/health")

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
    assert health.status_code == 200
