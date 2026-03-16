from __future__ import annotations

from typing import Any


def ingest_holdings_upload(*args: Any, **kwargs: Any):
    from app.services.ingestion import ingest_holdings_upload as _impl

    return _impl(*args, **kwargs)


def ingest_manual_holdings(*args: Any, **kwargs: Any):
    from app.services.ingestion import ingest_manual_holdings as _impl

    return _impl(*args, **kwargs)


def ensure_default_portfolio(*args: Any, **kwargs: Any):
    from app.services.portfolio import ensure_default_portfolio as _impl

    return _impl(*args, **kwargs)


def run_refresh_for_portfolio(*args: Any, **kwargs: Any):
    from app.services.refresh import run_refresh_for_portfolio as _impl

    return _impl(*args, **kwargs)


def run_nightly_refresh(*args: Any, **kwargs: Any):
    from app.services.refresh import run_nightly_refresh as _impl

    return _impl(*args, **kwargs)

__all__ = [
    "ingest_holdings_upload",
    "ingest_manual_holdings",
    "ensure_default_portfolio",
    "run_refresh_for_portfolio",
    "run_nightly_refresh",
]
