from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.routes.portfolios import _industry_analytics_params
from app.schemas.analytics import IndustryAnalyticsParams


def test_industry_analytics_params_normalizes_benchmark() -> None:
    params = _industry_analytics_params(
        window="1Y",
        interval="daily",
        benchmark=" spy ",
        sort_by="return",
        sort_order="desc",
    )

    assert params.benchmark == "SPY"


def test_industry_analytics_params_rejects_invalid_window_or_interval() -> None:
    with pytest.raises(ValidationError):
        IndustryAnalyticsParams(window="2Y")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        IndustryAnalyticsParams(interval="hourly")  # type: ignore[arg-type]
