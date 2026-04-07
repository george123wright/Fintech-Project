from __future__ import annotations

from app.services.chat_observability import ChatRateLimiter, redact_sensitive_data


def test_chat_rate_limiter_enforces_ip_and_session_limits() -> None:
    limiter = ChatRateLimiter(window_sec=60, max_requests_per_ip=2, max_requests_per_session=2)

    assert limiter.allow(ip_key="1.1.1.1", session_key="abc", now=1000.0) == (True, None)
    assert limiter.allow(ip_key="1.1.1.1", session_key="abc", now=1001.0) == (True, None)

    allowed, retry_after = limiter.allow(ip_key="1.1.1.1", session_key="abc", now=1002.0)
    assert allowed is False
    assert retry_after is not None and retry_after > 0


def test_redact_sensitive_data_masks_secrets() -> None:
    payload = {
        "api_key": "sk-1234567890ABCDE",
        "nested": {
            "authorization": "Bearer secret-token-value",
            "safe": "hello",
        },
        "arr": ["token sk-ABCDEFGHIJKLMNOP", "ok"],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert "[REDACTED]" in redacted["arr"][0]
    assert redacted["nested"]["safe"] == "hello"
