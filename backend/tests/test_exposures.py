from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.exposures import build_portfolio_exposure_snapshot
from app.services.narratives import build_narrative_payload
from app.services.scenarios.templates import guided_macro_workflow_payload


class DummyDB:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def scalar(self, *_args, **_kwargs):
        return None

    def scalars(self, *_args, **_kwargs):
        return []

    def add(self, row: object) -> None:
        if getattr(row, "id", None) is None:
            setattr(row, "id", len(self.rows) + 1)
        self.rows.append(row)

    def execute(self, *_args, **_kwargs):
        return None

    def flush(self) -> None:
        return None


class DummySnapshot:
    def __init__(self) -> None:
        self.id = 10
        self.as_of_date = date(2026, 3, 18)


class DummyPosition:
    def __init__(self, symbol: str, weight: float, asset_type: str, currency: str = "USD", name: str | None = None):
        self.symbol = symbol
        self.weight = weight
        self.asset_type = asset_type
        self.currency = currency
        self.name = name or symbol
        self.market_value = weight * 1000


def test_build_portfolio_exposure_snapshot_creates_overlap_and_breakdowns() -> None:
    db = DummyDB()
    positions = [
        DummyPosition("QQQ", 0.40, "ETF"),
        DummyPosition("SPY", 0.30, "ETF"),
        DummyPosition("NVDA", 0.30, "Equity"),
    ]
    result = build_portfolio_exposure_snapshot(db, portfolio_id=1, snapshot=DummySnapshot(), positions=positions)

    assert result.summary["breakdowns"]["sector"][0]["label"] == "Technology"
    assert result.summary["overlap_pairs"]
    assert any(signal["signal_key"] in {"top3_lookthrough_weight", "fund_overlap", "sector_crowding"} for signal in result.summary["concentration_signals"])


def test_build_narrative_payload_includes_change_and_watchouts() -> None:
    exposure_summary = {
        "breakdowns": {
            "sector": [{"label": "Technology", "lookthrough_weight": 0.62, "lookthrough_weight_pct": 62.0, "direct_weight": 0.4, "direct_weight_pct": 40.0}],
            "currency": [{"label": "USD", "lookthrough_weight": 0.9, "lookthrough_weight_pct": 90.0, "direct_weight": 0.9, "direct_weight_pct": 90.0}],
        },
        "overlap_pairs": [{"left_symbol": "QQQ", "right_symbol": "SPY", "overlap_weight": 0.12, "overlap_pct_of_pair": 0.18, "overlap_type": "lookthrough"}],
        "concentration_signals": [{"signal_key": "sector_crowding", "signal_value": 0.62, "severity": "high", "summary": "Technology dominates the portfolio."}],
        "top_lookthrough_holdings": [{"symbol": "NVDA", "weight": 0.18, "weight_pct": 18.0}],
        "warnings": [],
    }
    metrics = SimpleNamespace(top3_weight_share=0.7)
    valuation = SimpleNamespace(coverage_ratio=0.45, weighted_composite_upside=0.11)
    latest_scenario = SimpleNamespace(status="completed", factor_key="rates", shock_value=25, shock_unit="bps", horizon_days=21)
    previous_payload = {"exposure_summary": {"breakdowns": {"sector": [{"lookthrough_weight": 0.52}]}}, "change_summary": {"prior_top3_weight": 0.6}}

    payload = build_narrative_payload(positions=[DummyPosition("QQQ", 0.4, "ETF"), DummyPosition("NVDA", 0.3, "Equity")], exposure_summary=exposure_summary, metrics=metrics, valuation_summary=valuation, latest_scenario=latest_scenario, previous_payload=previous_payload)

    assert payload["cards"]
    assert payload["watchouts"]
    assert payload["change_summary"]["headline"] != "No prior narrative snapshot available."


def test_guided_macro_workflow_payload_returns_templates() -> None:
    payload = guided_macro_workflow_payload()
    assert payload["workflow_key"] == "guided_macro_v1"
    assert len(payload["templates"]) >= 3
