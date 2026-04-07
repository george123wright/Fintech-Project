from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.services.portfolio import get_portfolio_or_404

router = APIRouter(prefix="/chat", tags=["chat"])


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
    if payload.page_context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Use this page context when relevant and cite it in plain language: "
                    f"{payload.page_context}"
                ),
            }
        )

    for turn in payload.conversation_history:
        messages.append({"role": turn.role, "content": turn.content})

    messages.append({"role": "user", "content": payload.question})
    return messages, portfolio_context


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
    db: Session = Depends(get_db),
    _: None = Depends(require_chat_config),
) -> ChatQueryResponse:
    portfolio = get_portfolio_or_404(db, payload.portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=404,
            detail=ChatErrorDetail(code="portfolio_not_found", message="Portfolio not found").model_dump(),
        )

    if len(payload.conversation_history) > MAX_CHAT_HISTORY_TURNS:
        raise HTTPException(
            status_code=400,
            detail=ChatErrorDetail(
                code="conversation_too_long",
                message=f"Conversation history exceeds {MAX_CHAT_HISTORY_TURNS} turns",
            ).model_dump(),
        )

    messages, portfolio_context = _build_messages(payload, db)
    started_at = time.perf_counter()

    try:
        result = call_openrouter_chat(messages=messages)
    except OpenRouterConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail=ChatErrorDetail(code="provider_not_configured", message=str(exc)).model_dump(),
        ) from exc
    except OpenRouterRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=ChatErrorDetail(code="provider_rate_limit", message=str(exc)).model_dump(),
        ) from exc
    except OpenRouterTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=ChatErrorDetail(code="provider_timeout", message=str(exc)).model_dump(),
        ) from exc
    except (OpenRouterNetworkError, OpenRouterServerError) as exc:
        raise HTTPException(
            status_code=502,
            detail=ChatErrorDetail(code="provider_unavailable", message=str(exc)).model_dump(),
        ) from exc
    except OpenRouterResponseError as exc:
        raise HTTPException(
            status_code=502,
            detail=ChatErrorDetail(code="provider_bad_response", message=str(exc)).model_dump(),
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
