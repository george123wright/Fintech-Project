from __future__ import annotations

from app.services.valuation.composite import combine_valuation_models
from app.services.valuation.dcf import compute_dcf_fair_value
from app.services.valuation.ddm import compute_ddm_fair_value
from app.services.valuation.relative import compute_relative_fair_value
from app.services.valuation.ri import compute_ri_fair_value


def test_dcf_returns_value_with_deterministic_inputs() -> None:
    fair, low, high, upside, warnings, detail = compute_dcf_fair_value(
        symbol="TEST",
        current_price=100.0,
        market_cap=12_000_000_000.0,
        shares_outstanding=120_000_000.0,
        beta=1.1,
        sector="Technology",
        assumptions={
            "dcf": {
                "terminal_growth": 0.025,
                "steady_state_growth": 0.025,
                "explicit_years": 7,
                "rf": 0.02,
                "erp": 0.05,
                "tv_blend_weight": 0.65,
                "reinvestment_blend_weight": 0.5,
            }
        },
        forward_estimates={
            "fy0_revenue_avg": 10_500_000_000.0,
            "fy0_revenue_low": 9_800_000_000.0,
            "fy0_revenue_high": 11_300_000_000.0,
            "fy1_revenue_avg": 11_600_000_000.0,
            "fy1_revenue_low": 10_700_000_000.0,
            "fy1_revenue_high": 12_400_000_000.0,
            "fy0_eps_avg": 4.8,
            "fy0_eps_low": 4.3,
            "fy0_eps_high": 5.3,
            "fy1_eps_avg": 5.2,
            "fy1_eps_low": 4.7,
            "fy1_eps_high": 5.8,
        },
        statement_inputs={
            "revenue_latest": 9_700_000_000.0,
            "revenue_prev": 8_900_000_000.0,
            "growth_proxy": 0.09,
            "ebit_margin_history": [0.23, 0.22, 0.21, 0.20, 0.19],
            "net_margin_history": [0.17, 0.165, 0.16, 0.155, 0.15],
            "tax_rate_eff": 0.20,
            "tax_provision_latest": 480_000_000.0,
            "pretax_income_latest": 2_400_000_000.0,
            "depreciation_latest": 320_000_000.0,
            "capex_latest": -450_000_000.0,
            "current_assets_latest": 4_100_000_000.0,
            "current_liabilities_latest": 2_300_000_000.0,
            "nopat_latest": 1_850_000_000.0,
            "invested_capital_latest": 7_800_000_000.0,
            "diluted_shares_prev": 122_000_000.0,
            "total_debt_latest": 1_800_000_000.0,
            "total_debt_prev": 1_900_000_000.0,
            "cash_and_short_latest": 900_000_000.0,
            "cash_latest": 650_000_000.0,
            "avg_debt": 1_850_000_000.0,
            "interest_expense_latest": 90_000_000.0,
            "diluted_eps_latest": 4.5,
        },
        ratio_inputs={
            "operating_margin": 0.22,
            "da_to_revenue": 0.031,
            "capex_to_revenue": 0.044,
            "nwc_to_revenue": 0.17,
            "roic": 0.19,
            "price_to_sales": 1.24,
        },
    )
    assert fair is not None and fair > 0
    assert low is not None and low > 0
    assert high is not None and high > 0
    assert upside is not None
    assert isinstance(warnings, list)
    assert isinstance(detail, dict)
    assert detail.get("model_version") == "dcf_v2_fcff_anchor"
    base = detail.get("scenario_results", {}).get("base", {})
    wacc = base.get("wacc")
    g = base.get("terminal_growth")
    if isinstance(wacc, (int, float)) and isinstance(g, (int, float)):
        assert g <= (wacc - 0.02 + 1e-9)


def test_ri_returns_value_with_book_value() -> None:
    fair, low, high, upside, warnings, detail = compute_ri_fair_value(
        symbol="TEST",
        current_price=100.0,
        book_value_per_share=20.0,
        roe=0.18,
        beta=1.0,
        assumptions={
            "dcf": {"rf": 0.02, "erp": 0.05},
            "ri": {
                "explicit_years": 7,
                "steady_state_growth": 0.025,
                "long_run_roe": 0.12,
                "long_run_payout": 0.35,
                "fade_years_post_horizon": 8,
            },
        },
        forward_estimates={
            "fy0_revenue_avg": 10_500_000_000.0,
            "fy0_revenue_low": 9_800_000_000.0,
            "fy0_revenue_high": 11_300_000_000.0,
            "fy1_revenue_avg": 11_600_000_000.0,
            "fy1_revenue_low": 10_700_000_000.0,
            "fy1_revenue_high": 12_400_000_000.0,
            "fy0_eps_avg": 4.8,
            "fy0_eps_low": 4.3,
            "fy0_eps_high": 5.3,
            "fy1_eps_avg": 5.2,
            "fy1_eps_low": 4.7,
            "fy1_eps_high": 5.8,
        },
        statement_inputs={
            "revenue_latest": 9_700_000_000.0,
            "revenue_prev": 8_900_000_000.0,
            "growth_proxy": 0.09,
            "net_margin_history": [0.17, 0.165, 0.16, 0.155, 0.15],
            "diluted_shares_latest": 120_000_000.0,
            "diluted_shares_prev": 122_000_000.0,
            "diluted_eps_latest": 4.5,
        },
        ratio_inputs={"net_margin": 0.16, "roe": 0.18, "payout_ratio": 0.3},
        shares_outstanding=120_000_000.0,
    )
    assert fair is not None and fair > 0
    assert low is not None and high is not None
    assert low <= fair <= high
    assert upside is not None
    assert isinstance(warnings, list)
    assert detail.get("model_version") == "ri_v2_clean_surplus"
    base = detail.get("scenario_results", {}).get("base", {})
    coe = base.get("cost_of_equity")
    g = base.get("terminal_growth")
    if isinstance(coe, (int, float)) and isinstance(g, (int, float)):
        assert g <= (coe - 0.02 + 1e-9)


def test_ddm_returns_value_and_eps_dps_identity() -> None:
    fair, low, high, upside, warnings, detail = compute_ddm_fair_value(
        symbol="DIV",
        current_price=85.0,
        beta=0.95,
        assumptions={
            "dcf": {"rf": 0.02, "erp": 0.05},
            "ddm": {
                "explicit_years": 7,
                "anchor_mode": "eps_payout_linked",
                "coverage_mode": "hybrid_eps_payout",
                "terminal_method": "two_stage_gordon",
                "steady_state_growth": 0.025,
                "long_run_payout": 0.35,
                "payout_smoothing_weight": 0.6,
                "initiation_payout_floor": 0.08,
                "payout_cap": 0.9,
                "fallback_eps_spread": 0.15,
                "fallback_payout_spread": 0.1,
                "quality_penalty_enabled": True,
            },
        },
        forward_estimates={
            "fy0_eps_avg": 3.6,
            "fy0_eps_low": 3.1,
            "fy0_eps_high": 4.0,
            "fy1_eps_avg": 3.9,
            "fy1_eps_low": 3.4,
            "fy1_eps_high": 4.3,
            "fy0_revenue_avg": 12_500_000_000.0,
            "fy1_revenue_avg": 13_400_000_000.0,
        },
        statement_inputs={
            "diluted_shares_latest": 510_000_000.0,
            "diluted_shares_prev": 520_000_000.0,
            "diluted_eps_latest": 3.2,
            "net_income_latest": 1_650_000_000.0,
            "dividends_paid_latest": -580_000_000.0,
            "net_margin_history": [0.14, 0.145, 0.15, 0.152, 0.155],
            "growth_proxy": 0.07,
        },
        ratio_inputs={
            "payout_ratio": 0.34,
            "dividend_yield": 0.026,
            "eps_growth_yoy": 0.09,
            "roe": 0.16,
            "net_margin": 0.15,
        },
        shares_outstanding=510_000_000.0,
    )
    assert fair is not None and fair > 0
    assert low is not None and high is not None
    assert low <= fair <= high
    assert upside is not None
    assert isinstance(warnings, list)
    assert detail.get("model_version") == "ddm_v2_eps_dps"
    base_diag = detail.get("scenario_results", {}).get("base", {})
    coe = base_diag.get("cost_of_equity")
    g = base_diag.get("terminal_growth")
    if isinstance(coe, (int, float)) and isinstance(g, (int, float)):
        assert g <= (coe - 0.02 + 1e-9)

    scenario_results = detail.get("scenario_results", {})
    base = scenario_results.get("base", {})
    forecast = base.get("forecast", [])
    assert isinstance(forecast, list) and forecast
    for row in forecast:
        eps = row.get("eps")
        payout = row.get("payout")
        dps = row.get("dps")
        if isinstance(eps, (int, float)) and isinstance(payout, (int, float)) and isinstance(dps, (int, float)):
            assert abs(dps - max(eps, 0) * payout) < 1e-9


def test_relative_uses_global_fallback() -> None:
    fair, upside, warnings, used = compute_relative_fair_value(
        current_price=100.0,
        sector="Unknown Sector",
        metrics={"forward_pe": 25.0, "pb": 4.0, "ev_ebitda": 11.0},
        assumptions={"relative": {"multiples": ["forward_pe", "pb", "ev_ebitda"], "cap_upside": 0.6}},
    )
    assert fair is not None and fair > 0
    assert upside is not None
    assert "relative: sector_baseline_missing_using_global" in warnings
    assert used


def test_composite_renormalizes_available_models() -> None:
    fair, upside, low, high, status, warnings = combine_valuation_models(
        current_price=100.0,
        analyst_upside=0.1,
        dcf_fair_value=120.0,
        ri_fair_value=None,
        relative_fair_value=None,
    )
    assert fair is not None
    assert upside is not None
    assert low is not None
    assert high is not None
    assert status == "partial"
    assert "composite: partial_model_coverage" in warnings
