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

def test_compute_industry_return_metrics_with_benchmark() -> None:
    idx = pd.date_range("2026-01-01", periods=8, freq="D")
    industry_returns = pd.DataFrame(
        {
            "Software": [0.01, -0.005, 0.008, 0.002, -0.003, 0.007, 0.001, 0.004],
            "Energy": [0.004, 0.006, -0.002, 0.003, 0.005, -0.004, 0.002, 0.001],
        },
        index=idx,
    )
    benchmark = pd.Series([0.008, -0.004, 0.006, 0.001, -0.002, 0.005, 0.0, 0.003], index=idx)

    out = ia.compute_industry_return_metrics(industry_returns, benchmark_returns=benchmark, risk_free_rate=0.02)

    assert set(out.keys()) == {"Software", "Energy"}
    software = out["Software"]
    assert software["window_return"] is not None
    assert software["volatility_periodic"] is not None
    assert software["volatility_annualized"] is not None
    assert software["skewness"] is not None
    assert software["kurtosis"] is not None
    assert software["var_95"] is not None
    assert software["cvar_95"] is not None
    assert software["sharpe"] is not None
    assert software["sortino"] is not None
    assert software["upside_capture"] is not None
    assert software["downside_capture"] is not None
    assert software["beta"] is not None
    assert software["max_drawdown"] is not None
    assert software["hit_rate"] is not None
    assert software["tracking_error"] is not None
    assert software["information_ratio"] is not None


def test_compute_industry_return_metrics_without_benchmark() -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    industry_returns = pd.DataFrame({"Utilities": [0.01, 0.0, -0.01, 0.005, 0.002]}, index=idx)

    out = ia.compute_industry_return_metrics(industry_returns)

    utilities = out["Utilities"]
    assert utilities["window_return"] is not None
    assert utilities["upside_capture"] is None
    assert utilities["downside_capture"] is None
    assert utilities["beta"] is None
    assert utilities["tracking_error"] is None
    assert utilities["information_ratio"] is None


def test_build_industry_return_matrices_sorted_by_return() -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    returns = pd.DataFrame(
        {
            "Software": [0.03, 0.01, -0.005, 0.02, 0.01],
            "Utilities": [0.005, 0.002, 0.0, 0.004, 0.001],
            "Energy": [-0.01, 0.0, 0.005, -0.002, 0.001],
        },
        index=idx,
    )

    out = ia.build_industry_return_matrices(returns, sort_by="return")

    labels = out["covariance_matrix"]["labels"]
    assert labels == ["Software", "Utilities", "Energy"]
    assert out["correlation_matrix"]["labels"] == labels
    assert out["covariance_matrix"]["sort_context"]["sort_by"] == "return"
    assert out["covariance_matrix"]["sort_context"]["direction"] == "desc"

    cov_vals = out["covariance_matrix"]["values"]
    corr_vals = out["correlation_matrix"]["values"]
    assert len(cov_vals) == len(labels)
    assert len(corr_vals) == len(labels)
    assert all(len(row) == len(labels) for row in cov_vals)
    assert all(len(row) == len(labels) for row in corr_vals)
    assert cov_vals[0][1] == cov_vals[1][0]
    assert round(float(corr_vals[0][0]), 6) == 1.0


def test_build_industry_return_matrices_alphabetical_sort() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="D")
    returns = pd.DataFrame(
        {
            "Utilities": [0.01, -0.01, 0.0, 0.005],
            "Energy": [0.0, 0.002, -0.001, 0.003],
        },
        index=idx,
    )

    out = ia.build_industry_return_matrices(returns, sort_by="alphabetical")
    assert out["covariance_matrix"]["labels"] == ["Energy", "Utilities"]
    assert out["covariance_matrix"]["sort_context"]["direction"] == "asc"
