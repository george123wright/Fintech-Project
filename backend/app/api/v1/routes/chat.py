from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter(prefix="/chat", tags=["chat"])


async def require_chat_config(request: Request) -> None:
    chat_config_error = getattr(request.app.state, "chat_config_error", None)
    if chat_config_error:
        raise HTTPException(status_code=503, detail=chat_config_error)


@router.post("")
async def chat(_: None = Depends(require_chat_config)) -> dict[str, str]:
    raise HTTPException(
        status_code=501,
        detail="Chat endpoint is not implemented yet. OpenRouter configuration is loaded.",
    )
