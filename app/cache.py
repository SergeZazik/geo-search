"""Redis cache of parsed queries: the same question costs one LLM call per TTL.

The cache is an optimization. If Redis is down, search goes on without it.
"""

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.schemas.search import SearchFilter

logger = logging.getLogger(__name__)

# Bump the version when SearchFilter or the prompt changes meaning.
KEY_PREFIX = "search-filter:v1:"


def normalize_query(text: str) -> str:
    """One key for "Кафе  возле набережной " and "кафе возле набережной"."""
    return " ".join(text.lower().split())


class FilterCache:
    def __init__(self, redis: Redis, ttl_s: int) -> None:
        self.redis = redis
        self.ttl_s = ttl_s

    async def get(self, query: str) -> SearchFilter | None:
        try:
            raw = await self.redis.get(self._key(query))
        except RedisError as exc:
            logger.warning("Search cache unavailable: %s", exc)
            return None
        return SearchFilter.model_validate_json(raw) if raw is not None else None

    async def set(self, query: str, search_filter: SearchFilter) -> None:
        try:
            await self.redis.set(self._key(query), search_filter.model_dump_json(), ex=self.ttl_s)
        except RedisError as exc:
            logger.warning("Search cache unavailable: %s", exc)

    @staticmethod
    def _key(query: str) -> str:
        return KEY_PREFIX + normalize_query(query)
