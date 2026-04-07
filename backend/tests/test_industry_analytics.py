from __future__ import annotations

import pandas as pd

from app.services import industry_analytics as ia


class _TickerRef:
    def __init__(self, ticker: str | None):
        self.ticker = ticker


class _IndustryRef:
    def __init__(self, ticker: str | None):
        self.ticker = _TickerRef(ticker)


def test_resolve_industry_ticker_map_retries_and_normalizes(monkeypatch) -> None:
    attempts = {"software-infrastructure": 0}

    def fake_industry(slug: str):
        if slug == "software-infrastructure":
            attempts[slug] += 1
            if attempts[slug] == 1:
                raise RuntimeError("transient")
            return _IndustryRef("igv")
        if slug == "invalid":
            return _IndustryRef(None)
        return _IndustryRef("xle")

    monkeypatch.setattr(ia.yf, "Industry", fake_industry)

    mapped = ia.resolve_industry_ticker_map(["software-infrastructure", "invalid", "oil-gas-integrated"])

    assert mapped == {"IGV": "software-infrastructure", "XLE": "oil-gas-integrated"}


def test_fetch_industry_price_panel_normalizes_close_columns(monkeypatch) -> None:
    idx = pd.date_range("2026-01-01", periods=3)
    raw = pd.DataFrame(
        {
            ("Close", "IGV"): [100.0, 101.0, 102.0],
            ("Close", "XLE"): [80.0, 81.0, 82.0],
            ("Open", "IGV"): [99.0, 100.0, 101.0],
        },
        index=idx,
    )

    def fake_download(*args, **kwargs):
        return raw

    monkeypatch.setattr(ia.yf, "download", fake_download)

    panel = ia.fetch_industry_price_panel(["igv", "xle"], start="2026-01-01", end="2026-01-10")

    assert list(panel.columns) == ["IGV", "XLE"]
    assert panel.shape == (3, 2)


def test_map_tickers_to_display_industries_two_step_and_safe_collapse() -> None:
    df = pd.DataFrame({"IGV": [0.01, 0.02], "SOXX": [0.03, 0.04]}, index=pd.date_range("2026-01-01", periods=2))

    mapped = ia.map_tickers_to_display_industries(
        df,
        ticker_to_slug={"IGV": "software-infrastructure", "SOXX": "software-infrastructure"},
        slug_to_display={"software-infrastructure": "Software - Infrastructure"},
    )

    assert list(mapped.columns) == ["Software - Infrastructure", "Software - Infrastructure"]
    assert mapped.iloc[0, 0] == 0.01
    assert mapped.iloc[0, 1] == 0.03


def test_aggregate_industry_panel_equal_weight_default() -> None:
    prices = pd.DataFrame(
        {
            "IGV": [100.0, 110.0, 121.0],
            "SOXX": [50.0, 55.0, 60.5],
        },
        index=pd.date_range("2026-01-01", periods=3),
    )
    aggregated, meta = ia.aggregate_industry_panel(
        prices,
        ticker_to_industry={"IGV": "Software - Infrastructure", "SOXX": "Software - Infrastructure"},
    )

    assert list(aggregated.columns) == ["Software - Infrastructure"]
    assert round(float(aggregated.iloc[0, 0]), 6) == 0.1
    assert meta["aggregation_method"] == "equal_weight_returns"
    assert meta["series_type"] == "returns"


def test_aggregate_industry_panel_cap_weight_and_rebased() -> None:
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 121.0],  # +10%, +10%
            "BBB": [100.0, 120.0, 132.0],  # +20%, +10%
        },
        index=pd.date_range("2026-01-01", periods=3),
    )
    cap_weighted, cap_meta = ia.aggregate_industry_panel(
        prices,
        ticker_to_industry={"AAA": "Industry A", "BBB": "Industry A"},
        method="cap_weight_returns",
        market_caps={"AAA": 100.0, "BBB": 300.0},
    )
    rebased, rebased_meta = ia.aggregate_industry_panel(
        prices,
        ticker_to_industry={"AAA": "Industry A", "BBB": "Industry A"},
        method="rebased_price_index",
    )

    assert round(float(cap_weighted.iloc[0, 0]), 6) == 0.175
    assert cap_meta["aggregation_method"] == "cap_weight_returns"
    assert cap_meta["series_type"] == "returns"
    assert round(float(rebased.iloc[0, 0]), 6) == 100.0
    assert round(float(rebased.iloc[-1, 0]), 6) == 126.5
    assert rebased_meta["aggregation_method"] == "rebased_price_index"
    assert rebased_meta["series_type"] == "index_level"


def test_clean_returns_panel_generalized() -> None:
    prices = pd.DataFrame(
        {
            "A": ["121", "100", "110"],
            "B": [0.0, 1.0, 2.0],
            "C": [None, None, None],
        },
        index=pd.to_datetime(["2026-01-03", "2026-01-01", "2026-01-02"]),
    )

    cleaned = ia.clean_returns_panel(prices)

    assert list(cleaned.columns) == ["A", "B"]
    assert cleaned.index.is_monotonic_increasing
    assert cleaned.notna().all().all()
    # A should be +10% each step after sorting and pct_change.
    assert round(cleaned["A"].iloc[0], 4) == 0.1
    assert round(cleaned["A"].iloc[1], 4) == 0.1
