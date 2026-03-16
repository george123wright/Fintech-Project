from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./quick_balance.db")
    default_benchmark: str = os.getenv("DEFAULT_BENCHMARK", "SPY")
    default_base_ccy: str = os.getenv("DEFAULT_BASE_CCY", "USD")
    nightly_refresh_cron: str = os.getenv("NIGHTLY_REFRESH_CRON", "10 2 * * *")
    risk_free_rate: float = float(os.getenv("RISK_FREE_RATE", "0.02"))
    fred_api_key: str | None = os.getenv("FRED_API_KEY")
    fred_base_url: str = os.getenv("FRED_BASE_URL", "https://api.stlouisfed.org/fred")
    fred_timeout_sec: float = float(os.getenv("FRED_TIMEOUT_SEC", "12"))
    frontend_dist_dir: str = os.getenv("FRONTEND_DIST_DIR", str(REPO_ROOT / "dist"))


settings = Settings()
