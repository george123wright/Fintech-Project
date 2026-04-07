from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("APP_ENV", os.getenv("ENV", "dev")).lower()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./quick_balance.db")
    default_benchmark: str = os.getenv("DEFAULT_BENCHMARK", "SPY")
    default_base_ccy: str = os.getenv("DEFAULT_BASE_CCY", "USD")
    nightly_refresh_cron: str = os.getenv("NIGHTLY_REFRESH_CRON", "10 2 * * *")
    risk_free_rate: float = float(os.getenv("RISK_FREE_RATE", "0.02"))
    fred_api_key: str | None = os.getenv("FRED_API_KEY")
    fred_base_url: str = os.getenv("FRED_BASE_URL", "https://api.stlouisfed.org/fred")
    fred_timeout_sec: float = float(os.getenv("FRED_TIMEOUT_SEC", "12"))
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    openrouter_timeout_sec: float | None = (
        float(os.environ["OPENROUTER_TIMEOUT_SEC"])
        if "OPENROUTER_TIMEOUT_SEC" in os.environ
        else None
    )
    openrouter_max_tokens: int | None = (
        int(os.environ["OPENROUTER_MAX_TOKENS"])
        if "OPENROUTER_MAX_TOKENS" in os.environ
        else None
    )
    frontend_dist_dir: str = os.getenv("FRONTEND_DIST_DIR", str(REPO_ROOT / "dist"))
    chat_rate_limit_window_sec: int = int(os.getenv("CHAT_RATE_LIMIT_WINDOW_SEC", "60"))
    chat_rate_limit_per_ip: int = int(os.getenv("CHAT_RATE_LIMIT_PER_IP", "30"))
    chat_rate_limit_per_session: int = int(os.getenv("CHAT_RATE_LIMIT_PER_SESSION", "20"))

    @property
    def is_dev(self) -> bool:
        return self.environment in {"dev", "development", "local", "test", "testing"}


settings = Settings()
