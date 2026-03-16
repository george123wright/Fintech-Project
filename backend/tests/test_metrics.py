from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.services.metrics import compute_metrics


@dataclass
class DummyHolding:
    symbol: str
    weight: float
    market_value: float


def test_compute_metrics_core_fields() -> None:
    idx = pd.date_range("2025-01-01", periods=260, freq="B")
    prices = pd.DataFrame(
        {
            "AAA": np.linspace(100, 130, len(idx)),
            "BBB": np.linspace(90, 110, len(idx)) + np.sin(np.arange(len(idx))),
        },
        index=idx,
    )
    benchmark = pd.Series(np.linspace(400, 450, len(idx)), index=idx)

    holdings = [
        DummyHolding(symbol="AAA", weight=0.6, market_value=6000),
        DummyHolding(symbol="BBB", weight=0.4, market_value=4000),
    ]

    result = compute_metrics(
        holdings=holdings,
        price_frame=prices,
        benchmark_prices=benchmark,
        risk_free_rate=0.02,
    )

    assert result.portfolio_value == 10000
    assert np.isfinite(result.ann_return)
    assert np.isfinite(result.ann_vol)
    assert np.isfinite(result.sharpe)
    assert np.isfinite(result.sortino)
    assert np.isfinite(result.var_95)
    assert np.isfinite(result.cvar_95)
