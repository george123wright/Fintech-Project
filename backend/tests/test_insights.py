from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.services.insights import build_portfolio_exposure_summary, build_portfolio_narrative


@dataclass
class DummyHolding:
    symbol: str
    name: str | None
    weight: float
    market_value: float
    currency: str
    asset_type: str | None


def test_build_portfolio_exposure_summary_flags_concentration() -> None:
    holdings = [
        DummyHolding("NVDA", "NVIDIA", 0.32, 3200, "USD", "Equity"),
        DummyHolding("MSFT", "Microsoft", 0.22, 2200, "USD", "Equity"),
        DummyHolding("AAPL", "Apple", 0.18, 1800, "USD", "Equity"),
        DummyHolding("SHEL", "Shell", 0.16, 1600, "GBP", "Equity"),
        DummyHolding("BND", "Bond ETF", 0.12, 1200, "USD", "ETF"),
    ]
    fundamentals = {
        "NVDA": SimpleNamespace(sector="Technology", industry="Semiconductors"),
        "MSFT": SimpleNamespace(sector="Technology", industry="Software"),
        "AAPL": SimpleNamespace(sector="Technology", industry="Consumer Electronics"),
        "SHEL": SimpleNamespace(sector="Energy", industry="Integrated Oil"),
        "BND": SimpleNamespace(sector="Fixed Income", industry="Aggregate Bond"),
    }
    metrics = SimpleNamespace(top3_weight_share=0.72, hhi=0.215)

    summary = build_portfolio_exposure_summary(holdings, fundamentals_by_symbol=fundamentals, metrics=metrics)

    assert summary["sector"][0]["label"] == "Technology"
    assert round(summary["sector"][0]["weight_pct"], 1) == 72.0
    assert any(flag["title"] == "Top holdings concentration" for flag in summary["concentration_flags"])
    assert any(flag["title"] == "Sector crowding" for flag in summary["concentration_flags"])


def test_build_portfolio_narrative_includes_core_cards() -> None:
    holdings = [
        DummyHolding("NVDA", "NVIDIA", 0.35, 3500, "USD", "Equity"),
        DummyHolding("MSFT", "Microsoft", 0.25, 2500, "USD", "Equity"),
        DummyHolding("TLT", "Treasury ETF", 0.20, 2000, "USD", "ETF"),
        DummyHolding("SHEL", "Shell", 0.20, 2000, "GBP", "Equity"),
    ]
    exposure_summary = {
        "sector": [{"label": "Technology", "weight": 0.60, "weight_pct": 60.0}],
        "currency": [
            {"label": "USD", "weight": 0.80, "weight_pct": 80.0},
            {"label": "GBP", "weight": 0.20, "weight_pct": 20.0},
        ],
        "concentration_flags": [{"title": "Top holdings concentration"}],
    }
    metrics = SimpleNamespace(top3_weight_share=0.80)
    valuation = SimpleNamespace(coverage_ratio=0.75, weighted_composite_upside=0.12)
    scenario = SimpleNamespace(status="completed", factor_key="rates", shock_value=25, shock_unit="bps", horizon_days=21)

    narrative = build_portfolio_narrative(
        positions=holdings,
        exposure_summary=exposure_summary,
        metrics=metrics,
        valuation_summary=valuation,
        latest_scenario=scenario,
    )

    titles = [card["title"] for card in narrative["cards"]]
    assert "Concentration check" in titles
    assert "Sector tilt" in titles
    assert "Valuation coverage" in titles
    assert "Latest stress run" in titles
