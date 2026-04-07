from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings


class OpenRouterError(RuntimeError):
    """Base exception for OpenRouter chat failures."""


class OpenRouterConfigError(OpenRouterError):
    """Raised when required OpenRouter config is missing."""


class OpenRouterRateLimitError(OpenRouterError):
    """Raised when OpenRouter returns a 429 response."""


class OpenRouterServerError(OpenRouterError):
    """Raised when OpenRouter returns a 5xx response."""


class OpenRouterTimeoutError(OpenRouterError):
    """Raised when OpenRouter request times out."""


class OpenRouterNetworkError(OpenRouterError):
    """Raised for retryable network transport failures."""


class OpenRouterResponseError(OpenRouterError):
    """Raised for invalid or unexpected OpenRouter responses."""


def build_openrouter_payload(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning_enabled: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a safe OpenRouter chat payload with configurable reasoning."""
    payload: dict[str, Any] = {
        "model": model or settings.openrouter_model,
        "messages": messages,
        # Default false in production to control cost/latency.
        "reasoning": {"enabled": reasoning_enabled if reasoning_enabled is not None else settings.is_dev},
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    elif settings.openrouter_max_tokens is not None:
        payload["max_tokens"] = settings.openrouter_max_tokens
    if extra:
        payload.update(extra)
    return payload


def call_openrouter_chat(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning_enabled: bool | None = None,
    timeout_sec: float | None = None,
    max_retries: int = 2,
    retry_backoff_sec: float = 0.4,
    http_referer: str | None = None,
    x_title: str | None = None,
) -> dict[str, Any]:
    """Call OpenRouter chat/completions with retries and mapped errors."""
    if not settings.openrouter_api_key:
        raise OpenRouterConfigError("OPENROUTER_API_KEY is not configured on the server")

    payload = build_openrouter_payload(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_enabled=reasoning_enabled,
    )

    request_timeout = timeout_sec or settings.openrouter_timeout_sec or 20.0
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if http_referer:
        headers["HTTP-Referer"] = http_referer
    if x_title:
        headers["X-Title"] = x_title

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

    last_exc: OpenRouterError | None = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=request_timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            last_exc = OpenRouterTimeoutError("OpenRouter request timed out")
        except httpx.RequestError as exc:
            last_exc = OpenRouterNetworkError(f"OpenRouter network error: {exc}")
        else:
            if response.status_code == 429:
                last_exc = OpenRouterRateLimitError("OpenRouter rate limit reached")
            elif 500 <= response.status_code < 600:
                last_exc = OpenRouterServerError(
                    f"OpenRouter upstream error {response.status_code}: {response.text[:240]}"
                )
            elif response.status_code >= 400:
                raise OpenRouterResponseError(
                    f"OpenRouter request failed with status {response.status_code}: {response.text[:240]}"
                )
            else:
                return _normalize_openrouter_response(response.json(), payload)

        if attempt >= max_retries:
            if last_exc:
                raise last_exc
            raise OpenRouterError("OpenRouter call failed")
        time.sleep(retry_backoff_sec * (attempt + 1))

    raise OpenRouterError("OpenRouter call failed unexpectedly")


def _normalize_openrouter_response(response_json: dict[str, Any], request_payload: dict[str, Any]) -> dict[str, Any]:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterResponseError("Missing or invalid 'choices' in OpenRouter response")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenRouterResponseError("Invalid choice object in OpenRouter response")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenRouterResponseError("Missing message object in OpenRouter response")

    content = _extract_message_content(message.get("content"))

    usage = response_json.get("usage")
    usage_norm = usage if isinstance(usage, dict) else None

    return {
        "provider": "openrouter",
        "id": response_json.get("id"),
        "model": response_json.get("model") or request_payload.get("model"),
        "content": content,
        "finish_reason": first_choice.get("finish_reason"),
        "usage": usage_norm,
        "reasoning_enabled": bool(
            ((request_payload.get("reasoning") or {}) if isinstance(request_payload.get("reasoning"), dict) else {})
            .get("enabled", False)
        ),
    }


def _extract_message_content(raw_content: Any) -> str:
    if isinstance(raw_content, str):
        return raw_content

    if isinstance(raw_content, list):
        parts: list[str] = []
        for item in raw_content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)

    return ""
