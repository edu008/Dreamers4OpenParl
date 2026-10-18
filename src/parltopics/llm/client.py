"""LLM-Client mit Allowlist, Wiederholung und adaptiver Drosselung (PRD 7.7, 9; ARCHITEKTUR 3.5).

Der einzige Netzwerkzugriff der Anwendung zur Laufzeit geht an den Host aus LLM_BASE_URL.
`AllowlistTransport` erzwingt das auf Ebene des HTTP-Clients: Anfragen an andere Hosts scheitern,
bevor eine Verbindung aufgebaut wird.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
import openai

from parltopics.config import Settings

T = TypeVar("T")

RETRYABLE = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.InternalServerError,
    openai.APIConnectionError,
)
OVERLOAD = (openai.RateLimitError, openai.APITimeoutError)


class HostNotAllowedError(RuntimeError):
    """Eine Anfrage ging an einen Host ausserhalb der Allowlist."""


class AllowlistTransport(httpx.AsyncBaseTransport):
    """HTTP-Transport, der nur Anfragen an erlaubte Hosts weiterreicht."""

    def __init__(
        self, allowed_hosts: Iterable[str], inner: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._allowed = frozenset(host.lower() for host in allowed_hosts)
        self._inner = inner or httpx.AsyncHTTPTransport()

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return self._allowed

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = (request.url.host or "").lower()
        if host not in self._allowed:
            allowed = ", ".join(sorted(self._allowed))
            raise HostNotAllowedError(f"Host nicht erlaubt: {host!r} (erlaubt: {allowed})")
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class AdaptiveLimiter:
    """Begrenzt gleichzeitige Anfragen je Modell.

    Bei Überlast (429, Timeout) halbiert sich die Grenze, mindestens auf 1. Nach `recover_after`
    erfolgreichen Antworten in Folge steigt sie um 1, höchstens bis `maximum`.
    """

    def __init__(self, maximum: int, *, recover_after: int = 50) -> None:
        if maximum < 1:
            raise ValueError("maximum muss mindestens 1 sein")
        self.maximum = maximum
        self.limit = maximum
        self.recover_after = recover_after
        self._in_flight = 0
        self._streak = 0
        self._condition = asyncio.Condition()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        async with self._condition:
            await self._condition.wait_for(lambda: self._in_flight < self.limit)
            self._in_flight += 1
        try:
            yield
        finally:
            async with self._condition:
                self._in_flight -= 1
                self._condition.notify_all()

    async def record_success(self) -> None:
        async with self._condition:
            self._streak += 1
            if self._streak >= self.recover_after and self.limit < self.maximum:
                self.limit += 1
                self._streak = 0
                self._condition.notify_all()

    async def record_overload(self) -> None:
        async with self._condition:
            self.limit = max(1, self.limit // 2)
            self._streak = 0


def blocked_by_allowlist(error: BaseException | None) -> bool:
    """True, wenn der Fehler (oder seine Ursache) ein Verstoss gegen die Allowlist ist."""
    while error is not None:
        if isinstance(error, HostNotAllowedError):
            return True
        error = error.__cause__ or error.__context__
    return False


async def call_with_retry(
    call: Callable[[], Awaitable[T]],
    limiter: AdaptiveLimiter,
    *,
    attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> T:
    """Führt `call` mit Drosselung aus und wiederholt vorübergehende Fehler mit Backoff.

    Ein Verstoss gegen die Allowlist wird nie wiederholt.
    """
    for attempt in range(1, attempts + 1):
        async with limiter.slot():
            try:
                result = await call()
            except RETRYABLE as error:
                if blocked_by_allowlist(error):
                    raise
                if isinstance(error, OVERLOAD):
                    await limiter.record_overload()
                if attempt == attempts:
                    raise
            else:
                await limiter.record_success()
                return result
        delay = min(max_delay, base_delay * 2 ** (attempt - 1))
        await sleep(delay * (0.5 + random.random() / 2))
    raise AssertionError("unerreichbar")  # pragma: no cover


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    duration_ms: int


class LLMClient:
    """OpenAI-kompatibler Client für Apertus 8B und 70B mit Allowlist und Drosselung."""

    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self._http = httpx.AsyncClient(
            transport=AllowlistTransport([settings.llm_host], inner=transport),
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        self._openai = openai.AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or "EMPTY",
            http_client=self._http,
            max_retries=0,
        )
        self._limiters = {
            settings.llm_name: AdaptiveLimiter(settings.parallel_8b),
            settings.llm_name_large: AdaptiveLimiter(settings.parallel_70b),
        }

    def limiter(self, model: str) -> AdaptiveLimiter:
        return self._limiters.setdefault(model, AdaptiveLimiter(self.settings.parallel_8b))

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        large: bool = False,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        attempts: int = 5,
    ) -> ChatResult:
        """Eine Chat-Anfrage an 8B (Standard) oder 70B (`large=True`)."""
        model = self.settings.llm_name_large if large else self.settings.llm_name
        options: dict[str, Any] = {}
        if max_tokens is not None:
            options["max_tokens"] = max_tokens
        if response_format is not None:
            options["response_format"] = response_format

        async def once() -> Any:
            return await self._openai.chat.completions.create(
                model=model, messages=messages, temperature=temperature, **options
            )

        start = time.monotonic()
        response = await call_with_retry(once, self.limiter(model), attempts=attempts)
        duration_ms = int((time.monotonic() - start) * 1000)
        content = response.choices[0].message.content or ""
        return ChatResult(content=content, model=response.model or model, duration_ms=duration_ms)

    async def models(self) -> list[str]:
        """Modellnamen laut GET /models des Endpunkts."""
        return [model.id async for model in self._openai.models.list()]

    async def aclose(self) -> None:
        await self._openai.close()

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
