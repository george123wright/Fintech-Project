from __future__ import annotations

import re
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.chat import (
    MAX_CHAT_HISTORY_TURNS,
    ChatCitation,
    ChatErrorDetail,
    ChatErrorResponse,
    ChatLatencyMetadata,
    ChatQueryRequest,
    ChatQueryResponse,
)
from app.services.ai_chat import (
    OpenRouterConfigError,
    OpenRouterNetworkError,
    OpenRouterRateLimitError,
    OpenRouterResponseError,
    OpenRouterServerError,
    OpenRouterTimeoutError,
    build_chat_system_prompt,
    build_portfolio_context,
    call_openrouter_chat,
    serialize_portfolio_context,
)
from app.services.chat_observability import log_chat_error, log_chat_event
from app.services.portfolio import get_portfolio_or_404

router = APIRouter(prefix="/chat", tags=["chat"])
_ECHO_PATTERN = re.compile(r"\b(status|holdings?|warning|warnings)\b", re.IGNORECASE)
_MIN_DIRECT_ANSWER_LEN = 80
_MAX_PAGE_CONTEXT_CHARS = 280


def _request_id(request: Request) -> str:
    header_id = request.headers.get("x-request-id")
    return (header_id or str(uuid4())).strip()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _session_id(request: Request) -> str:
    return (
        request.headers.get("x-session-id")
        or request.cookies.get("session_id")
        or request.cookies.get("sessionid")
        or "anonymous"
    )


async def require_chat_config(request: Request) -> None:
    chat_config_error = getattr(request.app.state, "chat_config_error", None)
    if chat_config_error:
        raise HTTPException(
            status_code=503,
            detail=ChatErrorDetail(
                code="chat_config_missing",
                message=chat_config_error,
                warnings=["chat:disabled"],
            ).model_dump(),
        )


def _build_messages(payload: ChatQueryRequest, db: Session) -> tuple[list[dict[str, str]], dict[str, object]]:
    portfolio_context = build_portfolio_context(db, payload.portfolio_id)
    portfolio_context_json = serialize_portfolio_context(portfolio_context)
    messages: list[dict[str, str]] = []
    messages.append(
        {
            "role": "system",
            "content": build_chat_system_prompt(portfolio_context_json=portfolio_context_json),
        }
    )
    for turn in payload.conversation_history:
        messages.append({"role": turn.role, "content": turn.content})

    question = payload.question
    if payload.page_context:
        compact_page_context = _compact_page_context(payload.page_context)
        question = (
            f"{payload.question}\n\n"
            "Context notes (secondary, use only if relevant):\n"
            f"{compact_page_context}"
        )
    messages.append({"role": "user", "content": question})
    return messages, portfolio_context


def _compact_page_context(value: str) -> str:
    squashed = " ".join(value.split())
    if len(squashed) <= _MAX_PAGE_CONTEXT_CHARS:
        return squashed
    return f"{squashed[:_MAX_PAGE_CONTEXT_CHARS].rstrip()}…"


def _response_missed_question_intent(answer: str) -> bool:
    normalized = " ".join(answer.split())
    if len(normalized) < _MIN_DIRECT_ANSWER_LEN and _ECHO_PATTERN.search(normalized):
        return True
    lowered = normalized.lower()
    if normalized and not any(ch in normalized for ch in (".", "!", "?", "\n")) and _ECHO_PATTERN.search(normalized):
        return True
    return bool(
        _ECHO_PATTERN.search(lowered)
        and "question" not in lowered
        and "because" not in lowered
        and len(normalized.split()) <= 20
    )


def _with_intent_retry_instruction(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    retry_messages = list(messages)
    retry_messages.append(
        {
            "role": "system",
            "content": (
                "Your prior response missed the user's intent. Retry now: "
                "answer the user's exact question directly in the first paragraph, "
                "then provide any status/holdings/warnings as secondary context notes."
            ),
        }
    )
    return retry_messages


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    responses={
        400: {"model": ChatErrorResponse},
        404: {"model": ChatErrorResponse},
        429: {"model": ChatErrorResponse},
        502: {"model": ChatErrorResponse},
        503: {"model": ChatErrorResponse},
        504: {"model": ChatErrorResponse},
    },
)
def chat_query_route(
    payload: ChatQueryRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(require_chat_config),
) -> ChatQueryResponse:
    req_id = _request_id(request)
    response.headers["X-Request-ID"] = req_id

    client_ip = _client_ip(request)
    session_id = _session_id(request)
    rate_limiter = getattr(request.app.state, "chat_rate_limiter", None)
    analytics = getattr(request.app.state, "chat_analytics", None)

    if rate_limiter is not None:
        allowed, retry_after = rate_limiter.allow(ip_key=client_ip, session_key=session_id)
        if not allowed:
            if analytics is not None:
                analytics.inc("chat.rate_limited")
            log_chat_error(
                "rate_limited",
                request_id=req_id,
                ip=client_ip,
                session_id=session_id,
                retry_after_sec=retry_after,
            )
            raise HTTPException(
                status_code=429,
                detail=ChatErrorDetail(
                    code="chat_rate_limited",
                    message="Chat rate limit exceeded",
                    warnings=[f"retry_after_seconds:{retry_after or 1}"],
                ).model_dump(),
                headers={"Retry-After": str(retry_after or 1), "X-Request-ID": req_id},
            )

    portfolio = get_portfolio_or_404(db, payload.portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=404,
            detail=ChatErrorDetail(code="portfolio_not_found", message="Portfolio not found").model_dump(),
            headers={"X-Request-ID": req_id},
        )

    if len(payload.conversation_history) > MAX_CHAT_HISTORY_TURNS:
        raise HTTPException(
            status_code=400,
            detail=ChatErrorDetail(
                code="conversation_too_long",
                message=f"Conversation history exceeds {MAX_CHAT_HISTORY_TURNS} turns",
            ).model_dump(),
            headers={"X-Request-ID": req_id},
        )

    messages, portfolio_context = _build_messages(payload, db)
    started_at = time.perf_counter()

    try:
        result = call_openrouter_chat(messages=messages)
        if _response_missed_question_intent(str(result.get("content") or "")):
            result = call_openrouter_chat(messages=_with_intent_retry_instruction(messages))
    except OpenRouterConfigError as exc:
        if analytics is not None:
            analytics.inc("chat.error")
        log_chat_error("provider_error", request_id=req_id, error_class=exc.__class__.__name__, message=str(exc))
        raise HTTPException(
            status_code=503,
            detail=ChatErrorDetail(code="provider_not_configured", message=str(exc)).model_dump(),
            headers={"X-Request-ID": req_id},
        ) from exc
    except OpenRouterRateLimitError as exc:
        if analytics is not None:
            analytics.inc("chat.error")
        log_chat_error("provider_error", request_id=req_id, error_class=exc.__class__.__name__, message=str(exc))
        raise HTTPException(
            status_code=429,
            detail=ChatErrorDetail(code="provider_rate_limit", message=str(exc)).model_dump(),
            headers={"X-Request-ID": req_id},
        ) from exc
    except OpenRouterTimeoutError as exc:
        if analytics is not None:
            analytics.inc("chat.timeout")
        log_chat_error("provider_timeout", request_id=req_id, error_class=exc.__class__.__name__, message=str(exc))
        raise HTTPException(
            status_code=504,
            detail=ChatErrorDetail(code="provider_timeout", message=str(exc)).model_dump(),
            headers={"X-Request-ID": req_id},
        ) from exc
    except (OpenRouterNetworkError, OpenRouterServerError) as exc:
        if analytics is not None:
            analytics.inc("chat.error")
        log_chat_error("provider_error", request_id=req_id, error_class=exc.__class__.__name__, message=str(exc))
        raise HTTPException(
            status_code=502,
            detail=ChatErrorDetail(code="provider_unavailable", message=str(exc)).model_dump(),
            headers={"X-Request-ID": req_id},
        ) from exc
    except OpenRouterResponseError as exc:
        if analytics is not None:
            analytics.inc("chat.error")
        log_chat_error("provider_error", request_id=req_id, error_class=exc.__class__.__name__, message=str(exc))
        raise HTTPException(
            status_code=502,
            detail=ChatErrorDetail(code="provider_bad_response", message=str(exc)).model_dump(),
            headers={"X-Request-ID": req_id},
        ) from exc

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)

    citations: list[ChatCitation] = []
    if payload.page_context:
        citations.append(ChatCitation(label="page_context", detail="Answer grounded in provided page context"))

    warnings: list[str] = []
    finish_reason = result.get("finish_reason")
    if isinstance(finish_reason, str) and finish_reason not in {"stop", "tool_calls"}:
        warnings.append(f"finish_reason:{finish_reason}")

    usage = result.get("usage")
    if isinstance(usage, dict) and usage.get("total_tokens"):
        citations.append(ChatCitation(label="token_usage", detail=f"total_tokens={usage['total_tokens']}"))

    if analytics is not None:
        analytics.inc("chat.success")

    log_chat_event(
        "completed",
        request_id=req_id,
        ip=client_ip,
        session_id=session_id,
        latency_ms=elapsed_ms,
        model=result.get("model"),
        token_usage=usage if isinstance(usage, dict) else None,
        finish_reason=finish_reason,
        analytics_snapshot=analytics.snapshot() if analytics is not None else None,
    )

    return ChatQueryResponse(
        assistant_message=(result.get("content") or "").strip(),
        context_summary=(
            f"portfolio_as_of={portfolio_context.get('as_of_date')}"
            if portfolio_context.get("as_of_date")
            else (payload.page_context[:240] if payload.page_context else None)
        ),
        citations=citations,
        latency=ChatLatencyMetadata(
            total_ms=elapsed_ms,
            provider=str(result.get("provider") or "openrouter"),
            model=(str(result.get("model")) if result.get("model") else None),
        ),
        warnings=warnings + [str(item) for item in portfolio_context.get("warnings", []) if isinstance(item, str)],
    )
