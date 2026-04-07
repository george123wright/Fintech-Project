from __future__ import annotations

import logging
import re
import threading
import time
from collections import Counter, defaultdict, deque
from typing import Any

logger = logging.getLogger("app.chat")

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYWORDS = ("api_key", "apikey", "secret", "token", "password", "authorization", "auth")
_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9._\-]+")
_SK_RE = re.compile(r"\bsk-[a-zA-Z0-9]{10,}\b")


class ChatRateLimiter:
    """Simple in-memory fixed-window rate limiter for IP and session keys."""

    def __init__(
        self,
        *,
        window_sec: int,
        max_requests_per_ip: int,
        max_requests_per_session: int,
    ) -> None:
        self.window_sec = max(1, window_sec)
        self.max_requests_per_ip = max(1, max_requests_per_ip)
        self.max_requests_per_session = max(1, max_requests_per_session)
        self._ip_hits: dict[str, deque[float]] = defaultdict(deque)
        self._session_hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, *, ip_key: str, session_key: str, now: float | None = None) -> tuple[bool, int | None]:
        ts = now or time.time()
        with self._lock:
            ip_retry = self._apply_limit(self._ip_hits[ip_key], self.max_requests_per_ip, ts)
            session_retry = self._apply_limit(self._session_hits[session_key], self.max_requests_per_session, ts)
            retry_after = max(ip_retry or 0, session_retry or 0)
            if ip_retry is not None or session_retry is not None:
                return False, retry_after
            self._ip_hits[ip_key].append(ts)
            self._session_hits[session_key].append(ts)
            return True, None

    def _apply_limit(self, bucket: deque[float], limit: int, ts: float) -> int | None:
        cutoff = ts - self.window_sec
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = int(max(1, self.window_sec - (ts - bucket[0])))
            return retry_after
        return None


class ChatAnalytics:
    """Thread-safe counters for reliability monitoring."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def inc(self, key: str) -> None:
        with self._lock:
            self._counts[key] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(token in key.lower() for token in _SENSITIVE_KEYWORDS):
                redacted[key] = _REDACTED
            else:
                redacted[key] = redact_sensitive_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, str):
        sanitized = _BEARER_RE.sub(f"Bearer {_REDACTED}", value)
        sanitized = _SK_RE.sub(_REDACTED, sanitized)
        return sanitized
    return value


def log_chat_event(event: str, **fields: Any) -> None:
    logger.info("chat_event=%s %s", event, redact_sensitive_data(fields))


def log_chat_error(event: str, **fields: Any) -> None:
    logger.error("chat_event=%s %s", event, redact_sensitive_data(fields))
