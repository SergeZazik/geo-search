"""Turn a plain-language query into a SearchFilter with OpenAI structured outputs.

The LLM never writes SQL. It fills in a Pydantic model whose JSON schema the
API enforces (strict mode), and the repositories build the query from it.
"""

from openai import (
    APIError,
    AsyncOpenAI,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
)
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.cache import FilterCache
from app.schemas.search import SearchFilter

SYSTEM_PROMPT = (
    "You turn a search query about places in Ukraine into a search filter. "
    "The query can be in Ukrainian, Russian or English. "
    "Fill in only what the query asks for and leave the other fields empty: "
    "do not guess a city, a type or a size that the query does not mention."
)


class QueryNotUnderstoodError(Exception):
    """The query could not be turned into a filter."""


class SearchUnavailableError(Exception):
    """The LLM could not be reached."""


class QueryParser:
    def __init__(self, client: AsyncOpenAI, model: str, cache: FilterCache | None = None) -> None:
        self.client = client
        self.model = model
        self.cache = cache

    async def parse(self, query: str) -> SearchFilter:
        if self.cache and (cached := await self.cache.get(query)):
            return cached
        search_filter = await self._ask(query)
        if self.cache:
            await self.cache.set(query, search_filter)
        return search_filter

    async def _ask(self, query: str) -> SearchFilter:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        try:
            completion = await self.client.chat.completions.parse(
                model=self.model, messages=messages, response_format=SearchFilter
            )
        except (LengthFinishReasonError, ContentFilterFinishReasonError) as exc:
            raise QueryNotUnderstoodError("The model did not finish the filter") from exc
        except ValidationError as exc:
            raise QueryNotUnderstoodError(f"Invalid filter: {exc.errors()[0]['msg']}") from exc
        except APIError as exc:
            raise SearchUnavailableError(f"OpenAI API error: {exc.message}") from exc

        message = completion.choices[0].message
        if message.parsed is None:
            raise QueryNotUnderstoodError(message.refusal or "The model returned no filter")
        if message.parsed.is_empty():
            raise QueryNotUnderstoodError("The query does not say what to look for")
        return message.parsed
