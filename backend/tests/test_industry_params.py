from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.api.v1.routes.portfolios import _industry_analytics_params
from app.schemas.analytics import IndustryAnalyticsParams


def test_industry_analytics_params_normalizes_benchmark() -> None:
    params = _industry_analytics_params(
        window="1Y",
        date_mode="preset",
        interval="daily",
        benchmark=" spy ",
        sort_by="return",
        sort_order="desc",
    )

    assert params.benchmark == "SPY"


@pytest.mark.parametrize("window", ["1D", "1W", "1M", "3M", "1Y", "3Y", "5Y", "10Y"])
def test_industry_analytics_params_accepts_supported_presets(window: str) -> None:
    params = IndustryAnalyticsParams(window=window)  # type: ignore[arg-type]
    assert params.window == window


def test_industry_analytics_params_rejects_invalid_window_or_interval() -> None:
    with pytest.raises(ValidationError):
        IndustryAnalyticsParams(window="2Y")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        IndustryAnalyticsParams(interval="hourly")  # type: ignore[arg-type]


def test_industry_analytics_params_validates_custom_mode_dates() -> None:
    with pytest.raises(ValidationError):
        IndustryAnalyticsParams(date_mode="custom")

    with pytest.raises(ValidationError):
        IndustryAnalyticsParams(date_mode="custom", start_date="2026-03-10", end_date="2026-03-01")  # type: ignore[arg-type]

    params = _industry_analytics_params(
        window="1M",
        date_mode="custom",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        interval="weekly",
        benchmark=" qqq ",
        sort_by="vol",
        sort_order="asc",
    )
    assert params.date_mode == "custom"
    assert params.start_date == date(2026, 3, 1)
    assert params.end_date == date(2026, 3, 31)
