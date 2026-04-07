from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.v1.router import api_router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.jobs.scheduler import start_scheduler
from app.services.chat_observability import ChatAnalytics, ChatRateLimiter

scheduler = None


def _chat_config_error() -> str | None:
    if settings.is_dev or settings.openrouter_api_key:
        return None
    return (
        "OPENROUTER_API_KEY is required for chat endpoints when APP_ENV/ENV is not a dev environment."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    Base.metadata.create_all(bind=engine)
    app.state.chat_config_error = _chat_config_error()
    app.state.chat_rate_limiter = ChatRateLimiter(
        window_sec=settings.chat_rate_limit_window_sec,
        max_requests_per_ip=settings.chat_rate_limit_per_ip,
        max_requests_per_session=settings.chat_rate_limit_per_session,
    )
    app.state.chat_analytics = ChatAnalytics()
    scheduler = start_scheduler(SessionLocal, settings.nightly_refresh_cron)
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Quick Balance API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


_dist_dir = Path(settings.frontend_dist_dir).expanduser().resolve()
_index_file = _dist_dir / "index.html"


def _frontend_enabled() -> bool:
    return _dist_dir.exists() and _index_file.exists()


@app.get("/", include_in_schema=False)
def serve_root() -> FileResponse:
    if not _frontend_enabled():
        raise HTTPException(
            status_code=404,
            detail=f"Frontend build not found at {_dist_dir}. Run `npm run build` in repo root.",
        )
    return FileResponse(_index_file)


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str) -> FileResponse:
    # Keep API/doc/health routes handled by FastAPI's registered routes.
    if full_path.startswith("api/") or full_path in {"healthz", "docs", "redoc", "openapi.json"}:
        raise HTTPException(status_code=404, detail="Not found")

    if not _frontend_enabled():
        raise HTTPException(
            status_code=404,
            detail=f"Frontend build not found at {_dist_dir}. Run `npm run build` in repo root.",
        )

    candidate = (_dist_dir / full_path).resolve()
    if candidate.exists() and candidate.is_file() and str(candidate).startswith(str(_dist_dir)):
        return FileResponse(candidate)

    return FileResponse(_index_file)
