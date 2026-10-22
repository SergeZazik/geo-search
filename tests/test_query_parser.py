from typing import Any

import pytest
from redis.asyncio import Redis

from app.cache import FilterCache
from app.schemas.search import SearchFilter
from app.services.query_parser import QueryNotUnderstoodError, QueryParser, SearchUnavailableError
from tests.fake_openai import FakeOpenAI

QUERY = "кафе возле набережной в Днепре"
FILTER: dict[str, Any] = {
    "kinds": ["cafe"],
    "city": "Дніпро",
    "near_place": "набережна",
    "radius_m": None,
    "min_area_m2": None,
}
NOTHING: dict[str, Any] = {
    "kinds": [],
    "city": None,
    "near_place": None,
    "radius_m": None,
    "min_area_m2": None,
}


@pytest.fixture
def parser(fake_openai: FakeOpenAI, redis: Redis) -> QueryParser:
    return QueryParser(fake_openai.client, "test-model", FilterCache(redis, ttl_s=60))


async def test_parses_query_into_filter(parser: QueryParser, fake_openai: FakeOpenAI) -> None:
    fake_openai.answer(FILTER)

    search_filter = await parser.parse(QUERY)

    assert search_filter == SearchFilter(kinds=["cafe"], city="Дніпро", near_place="набережна")
    [request] = fake_openai.requests
    assert request["model"] == "test-model"
    assert request["messages"][-1] == {"role": "user", "content": QUERY}


async def test_kinds_are_an_enum_in_a_strict_schema(
    parser: QueryParser, fake_openai: FakeOpenAI
) -> None:
    fake_openai.answer(FILTER)
    await parser.parse(QUERY)

    json_schema = fake_openai.requests[0]["response_format"]["json_schema"]
    assert json_schema["strict"] is True
    kinds = json_schema["schema"]["properties"]["kinds"]["items"]["enum"]
    assert {"cafe", "pharmacy", "park"} <= set(kinds)
    assert "coffee_shop" not in kinds


async def test_same_query_is_parsed_once(
    parser: QueryParser, fake_openai: FakeOpenAI, redis: Redis
) -> None:
    fake_openai.answer(FILTER)

    first = await parser.parse(QUERY)
    second = await parser.parse("  Кафе возле  НАБЕРЕЖНОЙ в Днепре ")

    assert second == first
    assert len(fake_openai.requests) == 1
    assert 0 < await redis.ttl("search-filter:v1:кафе возле набережной в днепре") <= 60


async def test_parses_without_redis(fake_openai: FakeOpenAI) -> None:
    unreachable = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    parser = QueryParser(fake_openai.client, "test-model", FilterCache(unreachable, ttl_s=60))
    fake_openai.answer(FILTER)

    assert (await parser.parse(QUERY)).city == "Дніпро"
    await unreachable.aclose()


async def test_refusal_is_not_understood(parser: QueryParser, fake_openai: FakeOpenAI) -> None:
    fake_openai.refuse("I can't help with that.")
    with pytest.raises(QueryNotUnderstoodError, match="can't help"):
        await parser.parse(QUERY)


async def test_cut_off_answer_is_not_understood(
    parser: QueryParser, fake_openai: FakeOpenAI
) -> None:
    fake_openai.answer(FILTER, finish_reason="length")
    with pytest.raises(QueryNotUnderstoodError):
        await parser.parse(QUERY)


async def test_invalid_value_is_not_understood(
    parser: QueryParser, fake_openai: FakeOpenAI
) -> None:
    fake_openai.answer({**FILTER, "radius_m": 100_000})
    with pytest.raises(QueryNotUnderstoodError, match="Invalid filter"):
        await parser.parse(QUERY)


async def test_empty_filter_is_not_understood_and_not_cached(
    parser: QueryParser, fake_openai: FakeOpenAI
) -> None:
    fake_openai.answer({**NOTHING, "radius_m": 300})  # a radius alone is not a search
    for _ in range(2):
        with pytest.raises(QueryNotUnderstoodError, match="what to look for"):
            await parser.parse("привет")
    assert len(fake_openai.requests) == 2


@pytest.mark.parametrize("status_code", [401, 429, 500])
async def test_api_errors_make_search_unavailable(
    parser: QueryParser, fake_openai: FakeOpenAI, status_code: int
) -> None:
    fake_openai.fail(status_code)
    with pytest.raises(SearchUnavailableError):
        await parser.parse(QUERY)
