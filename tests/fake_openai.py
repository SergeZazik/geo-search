"""An OpenAI client that answers from the test, not from the API: no network, no key.

The SDK sends requests through httpx2, so a MockTransport stands in for the
API and records what the parser sent.
"""

import json
from typing import Any

import httpx2
from openai import AsyncOpenAI


def chat_completion(
    content: str | None, *, refusal: str | None = None, finish_reason: str = "stop"
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content, "refusal": refusal},
            }
        ],
    }


class FakeOpenAI:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.response = httpx2.Response(500)
        transport = httpx2.MockTransport(self._handle)
        self.client = AsyncOpenAI(
            api_key="test", max_retries=0, http_client=httpx2.AsyncClient(transport=transport)
        )

    def answer(self, search_filter: dict[str, Any], *, finish_reason: str = "stop") -> None:
        content = json.dumps(search_filter, ensure_ascii=False)
        body = chat_completion(content, finish_reason=finish_reason)
        self.response = httpx2.Response(200, json=body)

    def refuse(self, refusal: str) -> None:
        self.response = httpx2.Response(200, json=chat_completion(None, refusal=refusal))

    def fail(self, status_code: int) -> None:
        self.response = httpx2.Response(status_code, json={"error": {"message": "test error"}})

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        return self.response
