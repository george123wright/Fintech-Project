from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.services.metrics_extended import compute_extended_metrics


@dataclass
class DummyHolding:
    symbol: str
    weight: float
    market_value: float


def test_compute_extended_metrics_returns_expected_sections() -> None:
    idx = pd.date_range("2021-01-01", periods=900, freq="B")
    prices = pd.DataFrame(
        {
            "AAA": np.linspace(100.0, 180.0, len(idx)) + 2.0 * np.sin(np.arange(len(idx)) / 20.0),
            "BBB": np.linspace(80.0, 130.0, len(idx)) + 1.5 * np.cos(np.arange(len(idx)) / 13.0),
            "CCC": np.linspace(50.0, 90.0, len(idx)) + 1.0 * np.sin(np.arange(len(idx)) / 7.0),
        },
        index=idx,
    )
    benchmark = pd.Series(np.linspace(300.0, 470.0, len(idx)), index=idx)

    holdings = [
        DummyHolding(symbol="AAA", weight=0.5, market_value=5000.0),
        DummyHolding(symbol="BBB", weight=0.3, market_value=3000.0),
        DummyHolding(symbol="CCC", weight=0.2, market_value=2000.0),
    ]

    result = compute_extended_metrics(
        holdings=holdings,
        price_frame=prices,
        benchmark_prices=benchmark,
        risk_free_rate=0.02,
        benchmark_symbol="SPY",
        db=None,
        include_live_extras=False,
    )

    metrics = result.metrics
    assert metrics["status"] == "ok"
    assert "portfolio" in metrics
    assert "stocks" in metrics
    assert "factor_model" in metrics
    assert "macro_model" in metrics
    assert "fundamental_rollup" in metrics

    portfolio = metrics["portfolio"]
    assert portfolio["sharpe"] is not None
    assert portfolio["sortino"] is not None
    assert portfolio["var"]["historical_95"] is not None
    assert portfolio["returns"]["1m"] is not None

    stocks = metrics["stocks"]
    assert "AAA" in stocks
    assert stocks["AAA"]["technicals"]["rsi_14"] is not None
