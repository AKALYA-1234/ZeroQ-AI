"""
LLM provider adapters behind one interface:

    provider.complete(operation, system, user, schema, max_tokens, effort) -> ProviderResult

* AnthropicProvider — the existing Claude integration (structured outputs + server-side refusal fallback).
* OpenAICompatibleProvider — Groq and OpenRouter (`/chat/completions`, `response_format: json_schema`).

Every response is validated against the pydantic schema; anything else raises ProviderError so the
caller can fail over. Nothing here fabricates a result. Keys are read from SecretStr settings and only
ever placed in the Authorization header.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx
from pydantic import SecretStr, ValidationError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ProviderError(Exception):
    def __init__(self, provider: str, kind: str, retryable: bool = False, config_error: bool = False):
        super().__init__(f"{provider}: {kind}")
        self.provider, self.kind, self.retryable, self.config_error = provider, kind, retryable, config_error


@dataclass
class ProviderResult:
    parsed: object
    usage: dict = field(default_factory=dict)


def _secret(value) -> Optional[str]:
    if value is None:
        return None
    raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    return raw.strip() or None


def _cost(inp: int, out: int, price_in: Optional[float], price_out: Optional[float], free: bool):
    if free:
        return 0.0, "free_tier"
    if price_in is None or price_out is None:
        return None, "unknown"
    return round((inp * price_in + out * price_out) / 1_000_000, 6), "paid"


class OpenAICompatibleProvider:
    """Groq / OpenRouter chat-completions adapter."""

    def __init__(self, name: str, base_url: str, api_key, model: Optional[str], timeout: float,
                 max_retries: int, retry_max_wait: float, price_in: Optional[float] = None,
                 price_out: Optional[float] = None, extra_headers: Optional[dict] = None,
                 transport: Optional[httpx.BaseTransport] = None, sleep: Callable[[float], None] = time.sleep):
        self.name, self.base_url, self.model = name, base_url.rstrip("/"), model
        self._key = _secret(api_key)
        self.timeout, self.max_retries, self.retry_max_wait = timeout, max_retries, retry_max_wait
        self.price_in, self.price_out = price_in, price_out
        self.extra_headers = extra_headers or {}
        self._transport, self._sleep = transport, sleep

    @property
    def configured(self) -> bool:
        return bool(self._key and self.model)

    @property
    def free_tier(self) -> bool:
        return bool(self.model and self.model.endswith(":free"))

    def describe(self) -> dict:
        return {"provider": self.name, "model": self.model, "configured": self.configured,
                "billing": "free_tier" if self.free_tier else ("paid" if self.price_in is not None else "unknown")}

    def _body(self, system: str, user: str, schema, max_tokens: int, structured: bool) -> dict:
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if structured:
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": schema.__name__, "schema": schema.model_json_schema(), "strict": False}}
        else:  # model without json_schema support: instruct + validate
            body["messages"][0]["content"] = (system + "\n\nRespond with only a JSON object that matches this "
                                              f"JSON Schema, no prose:\n{json.dumps(schema.model_json_schema())}")
        return body

    def _post(self, client: httpx.Client, body: dict) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json", **self.extra_headers}
        return client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)

    def _wait(self, response: Optional[httpx.Response], attempt: int) -> None:
        delay = min(self.retry_max_wait, 2 ** attempt)
        if response is not None:
            try:
                delay = min(self.retry_max_wait, float(response.headers.get("retry-after", delay)))
            except ValueError:
                pass
        self._sleep(max(0.0, delay))

    def complete(self, operation: str, system: str, user: str, schema, max_tokens: int, effort: str) -> ProviderResult:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", config_error=True)
        structured = True
        started = time.monotonic()
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            attempt = 0
            while True:
                try:
                    response = self._post(client, self._body(system, user, schema, max_tokens, structured))
                except httpx.TimeoutException:
                    if attempt < self.max_retries:
                        attempt += 1
                        self._wait(None, attempt)
                        continue
                    raise ProviderError(self.name, "timeout", retryable=True)
                except httpx.HTTPError as exc:
                    if attempt < self.max_retries:
                        attempt += 1
                        self._wait(None, attempt)
                        continue
                    raise ProviderError(self.name, f"connection:{type(exc).__name__}", retryable=True)
                status = response.status_code
                if status in (401, 403):
                    raise ProviderError(self.name, "authentication", config_error=True)
                if status == 404:
                    raise ProviderError(self.name, "model_not_found", config_error=True)
                if status == 400 and structured and "response_format" in response.text.lower():
                    structured = False   # model lacks json_schema support: retry once in prompt-JSON mode
                    continue
                if status in RETRYABLE_STATUS:
                    if attempt < self.max_retries:
                        attempt += 1
                        self._wait(response, attempt)
                        continue
                    raise ProviderError(self.name, "rate_limited" if status == 429 else f"http_{status}", retryable=True)
                if status >= 400:
                    raise ProviderError(self.name, f"http_{status}")
                break
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            data = response.json()
            choice = data["choices"][0]
            content = (choice.get("message") or {}).get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError(self.name, "malformed_response")
        if choice.get("finish_reason") == "length":
            raise ProviderError(self.name, "incomplete_output")
        try:
            parsed = schema.model_validate_json(FENCE_RE.sub("", content.strip()))
        except ValidationError:
            raise ProviderError(self.name, "invalid_output")
        usage = data.get("usage") or {}
        inp, out = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        cost, billing = _cost(inp, out, self.price_in, self.price_out, self.free_tier)
        return ProviderResult(parsed, {
            "operation": operation, "provider": self.name, "model": data.get("model") or self.model,
            "input_tokens": inp, "output_tokens": out, "latency_ms": latency_ms, "retries": attempt,
            "structured_output": "json_schema" if structured else "prompt_json",
            "billing": billing, "estimated_cost_usd": cost, "status": "ok"})


class AnthropicProvider:
    """The existing Claude integration (unchanged behaviour), wrapped in the provider interface."""
    BETA = "server-side-fallback-2026-07-01"

    def __init__(self, model: str, timeout: float, api_key=None, client=None,
                 price_in: float = 4.0, price_out: float = 20.0):
        self.name, self.model = "anthropic", model
        self._key, self._client, self.timeout = _secret(api_key), client, timeout
        self.price_in, self.price_out = price_in, price_out

    @property
    def configured(self) -> bool:
        if self._client is not None:
            return True
        import importlib.util
        import os
        has_key = self._key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        return bool(has_key) and importlib.util.find_spec("anthropic") is not None

    def describe(self) -> dict:
        return {"provider": self.name, "model": self.model, "configured": self.configured, "billing": "paid"}

    def _get_client(self):
        if self._client is None:
            import anthropic
            kwargs = {"timeout": self.timeout, "max_retries": 2}
            if self._key:
                kwargs["api_key"] = self._key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    @staticmethod
    def _classify(exc: Exception):
        try:
            import anthropic
        except ImportError:
            return type(exc).__name__, False
        if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
            return "authentication", True
        if isinstance(exc, anthropic.NotFoundError):
            return "model_not_found", True
        if isinstance(exc, anthropic.RateLimitError):
            return "rate_limited", False
        if isinstance(exc, anthropic.APITimeoutError):
            return "timeout", False
        if isinstance(exc, anthropic.APIStatusError):
            return f"api_error_{exc.status_code}", False
        if isinstance(exc, anthropic.APIConnectionError):
            return "connection", False
        return type(exc).__name__, False

    def complete(self, operation: str, system: str, user: str, schema, max_tokens: int, effort: str) -> ProviderResult:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", config_error=True)
        started = time.monotonic()
        try:
            response = self._get_client().beta.messages.parse(
                model=self.model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}], output_format=schema,
                output_config={"effort": effort}, betas=[self.BETA], fallbacks="default")
        except Exception as exc:
            kind, config_error = self._classify(exc)
            raise ProviderError(self.name, kind, retryable=not config_error, config_error=config_error) from exc
        usage = getattr(response, "usage", None)
        inp = int(getattr(usage, "input_tokens", 0) or 0)
        out = int(getattr(usage, "output_tokens", 0) or 0)
        record = {"operation": operation, "provider": self.name, "model": getattr(response, "model", self.model),
                  "input_tokens": inp, "output_tokens": out,
                  "latency_ms": int((time.monotonic() - started) * 1000), "retries": 0,
                  "structured_output": "json_schema", "billing": "paid",
                  "estimated_cost_usd": round((inp * self.price_in + out * self.price_out) / 1_000_000, 6)}
        if response.stop_reason == "refusal":
            raise ProviderError(self.name, "refused")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise ProviderError(self.name, "incomplete_output")
        return ProviderResult(response.parsed_output, {**record, "status": "ok"})
