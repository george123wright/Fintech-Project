from __future__ import annotations

import pandas as pd

from app.services.providers.yahoo import fetch_market_rate_snapshot


def test_fetch_market_rate_snapshot_computes_rf_and_erp(monkeypatch) -> None:
    idx = pd.date_range("2021-01-01", periods=252 * 5 + 10, freq="B")
    gspc = pd.DataFrame({"Close": pd.Series(range(len(idx)), index=idx, dtype=float) + 1000.0})
    tnx = pd.DataFrame({"Close": pd.Series([4.0] * len(idx), index=idx, dtype=float)})

    def _fake_download(symbol: str, *args, **kwargs):
        if symbol.upper() == "^GSPC":
            return gspc
        if symbol.upper() == "^TNX":
            return tnx
        return pd.DataFrame()

    monkeypatch.setattr("app.services.providers.yahoo.yf.download", _fake_download)

    snapshot = fetch_market_rate_snapshot(years=5, market_symbol="^GSPC", risk_free_symbol="^TNX")
    assert snapshot.status in {"ok", "partial"}
    assert snapshot.risk_free_rate is not None
    assert abs(snapshot.risk_free_rate - 0.04) < 1e-9
    assert snapshot.market_return_5y is not None
    assert snapshot.erp_5y is not None
    assert abs(snapshot.erp_5y - (snapshot.market_return_5y - snapshot.risk_free_rate)) < 1e-9
    assert snapshot.observations >= 252
