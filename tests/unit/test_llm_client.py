import asyncio
import json

import httpx
import openai
import pytest

from parltopics.llm import (
    AdaptiveLimiter,
    AllowlistTransport,
    HostNotAllowedError,
    LLMClient,
    call_with_retry,
)
from tests.mock_llm.app import completion


async def no_sleep(_seconds: float) -> None:
    return None


async def test_allowlist_blocks_every_other_host():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200)

    transport = AllowlistTransport(["llm.test"], inner=httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        assert (await client.get("http://llm.test/v1/models")).status_code == 200
        for url in ["https://example.org/", "https://pypi.org/simple/", "http://LLM.test.evil/"]:
            with pytest.raises(HostNotAllowedError):
                await client.get(url)
    assert seen == ["llm.test"]


async def test_chat_uses_only_the_configured_endpoint(settings):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=completion("OK", "test-8b"))

    async with LLMClient(settings, transport=httpx.MockTransport(handler)) as client:
        result = await client.chat([{"role": "user", "content": "Hallo"}])
    assert result.content == "OK"
    assert result.model == "test-8b"
    assert [str(r.url) for r in requests] == ["http://llm.test/v1/chat/completions"]
    body = json.loads(requests[0].content)
    assert body["model"] == "test-8b"
    assert body["temperature"] == 0.0
    assert requests[0].headers["authorization"] == "Bearer secret"


async def test_large_switches_to_70b(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("OK", json.loads(request.content)["model"]))

    async with LLMClient(settings, transport=httpx.MockTransport(handler)) as client:
        result = await client.chat([{"role": "user", "content": "Hallo"}], large=True)
    assert result.model == "test-70b"


async def test_retry_after_rate_limit_halves_the_limit():
    limiter = AdaptiveLimiter(8)
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    errors = [
        openai.RateLimitError("429", response=httpx.Response(429, request=request), body=None)
    ]
    sleeps: list[float] = []

    async def call() -> str:
        if errors:
            raise errors.pop()
        return "ok"

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    assert await call_with_retry(call, limiter, sleep=record_sleep) == "ok"
    assert limiter.limit == 4
    assert len(sleeps) == 1


async def test_allowlist_violation_is_never_retried():
    limiter = AdaptiveLimiter(2)
    request = httpx.Request("GET", "https://example.org/")
    calls = 0

    async def call() -> None:
        nonlocal calls
        calls += 1
        try:
            raise HostNotAllowedError("example.org")
        except HostNotAllowedError as error:
            raise openai.APIConnectionError(request=request) from error

    with pytest.raises(openai.APIConnectionError):
        await call_with_retry(call, limiter, sleep=no_sleep)
    assert calls == 1


async def test_server_errors_give_up_after_attempts():
    limiter = AdaptiveLimiter(2)
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    calls = 0

    async def call() -> None:
        nonlocal calls
        calls += 1
        raise openai.InternalServerError(
            "500", response=httpx.Response(500, request=request), body=None
        )

    with pytest.raises(openai.InternalServerError):
        await call_with_retry(call, limiter, attempts=3, sleep=no_sleep)
    assert calls == 3
    assert limiter.limit == 2  # 5xx ist keine Überlast


async def test_limiter_recovers_but_never_exceeds_maximum():
    limiter = AdaptiveLimiter(4, recover_after=3)
    await limiter.record_overload()
    assert limiter.limit == 2
    for _ in range(3):
        await limiter.record_success()
    assert limiter.limit == 3
    for _ in range(20):
        await limiter.record_success()
    assert limiter.limit == 4


async def test_limiter_never_drops_below_one():
    limiter = AdaptiveLimiter(3)
    for _ in range(5):
        await limiter.record_overload()
    assert limiter.limit == 1


async def test_limiter_caps_concurrency():
    limiter = AdaptiveLimiter(2)
    peak = 0

    async def work() -> None:
        nonlocal peak
        async with limiter.slot():
            peak = max(peak, limiter.in_flight)
            await asyncio.sleep(0.01)

    await asyncio.gather(*(work() for _ in range(6)))
    assert peak == 2
    assert limiter.in_flight == 0
