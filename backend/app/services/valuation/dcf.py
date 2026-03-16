from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping

from app.services.valuation.relative import GLOBAL_BASELINE, SECTOR_BASELINES


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number):  # NaN check
        return None
    return number


def _pct(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = _clamp(quantile, 0.0, 1.0) * (len(ordered) - 1)
    low_i = int(pos)
    high_i = min(low_i + 1, len(ordered) - 1)
    w = pos - low_i
    return ordered[low_i] * (1.0 - w) + ordered[high_i] * w


def _avg(values: list[float | None], fallback: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return fallback
    return float(sum(cleaned) / len(cleaned))


def _median(values: list[float | None], fallback: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return fallback
    return float(median(cleaned))


def _fade(start: float, end: float, step: int, total_steps: int) -> float:
    if total_steps <= 0:
        return end
    t = _clamp(step / total_steps, 0.0, 1.0)
    return start + (end - start) * t


@dataclass
class DcfScenarioResult:
    scenario_key: str
    fair_value: float | None
    upside: float | None
    ev: float | None
    tv_gordon: float | None
    tv_multiple: float | None
    tv_blended: float | None
    tv_pv_share: float | None
    wacc: float | None
    terminal_growth: float | None
    warnings: list[str]
    anchor_diagnostics: dict[str, Any]
    forecast: list[dict[str, Any]]


def _select_terminal_multiple(sector: str | None) -> float:
    baseline = SECTOR_BASELINES.get((sector or "").strip(), GLOBAL_BASELINE)
    multiple = _to_float(baseline.get("ev_ebitda")) if isinstance(baseline, dict) else None
    if multiple is None:
        multiple = _to_float(GLOBAL_BASELINE.get("ev_ebitda"))
    return _clamp(float(multiple if multiple is not None else 12.0), 4.0, 30.0)


def _build_revenue_path(
    *,
    revenue0: float,
    revenue1: float,
    revenue2: float,
    explicit_years: int,
    terminal_growth: float,
) -> tuple[list[float], list[float]]:
    revenues = [revenue1]
    growth = [_safe_div(revenue1 - revenue0, revenue0) or 0.0]
    if explicit_years == 1:
        return revenues, growth

    revenues.append(revenue2)
    growth.append(_safe_div(revenue2 - revenue1, revenue1) or 0.0)

    g2 = growth[-1]
    for year in range(3, explicit_years + 1):
        g_year = _fade(g2, terminal_growth, year - 2, max(1, explicit_years - 2))
        revenue_prev = revenues[-1]
        revenue_next = revenue_prev * (1.0 + g_year)
        revenues.append(revenue_next)
        growth.append(g_year)
    return revenues, growth


def _run_fcff_scenario(
    *,
    scenario_key: str,
    current_price: float | None,
    shares0: float,
    sector: str | None,
    explicit_years: int,
    rev_anchor_1: float,
    rev_anchor_2: float,
    eps_anchor_1: float | None,
    eps_anchor_2: float | None,
    revenue0: float,
    tax_rate: float,
    kappa: float,
    buyback_rate: float,
    margin_p10: float,
    margin_p90: float,
    steady_ebit_margin: float,
    da_ratio: float,
    capex_ratio: float,
    nwc_ratio: float,
    roic: float,
    wacc: float,
    terminal_growth: float,
    tv_blend_weight: float,
    reinvestment_blend_weight: float,
    net_debt: float,
) -> DcfScenarioResult:
    warnings: list[str] = []

    if rev_anchor_1 <= 0 or rev_anchor_2 <= 0:
        warnings.append("dcf:missing_rev_anchor")
        return DcfScenarioResult(
            scenario_key=scenario_key,
            fair_value=None,
            upside=None,
            ev=None,
            tv_gordon=None,
            tv_multiple=None,
            tv_blended=None,
            tv_pv_share=None,
            wacc=wacc,
            terminal_growth=terminal_growth,
            warnings=warnings,
            anchor_diagnostics={},
            forecast=[],
        )

    revenues, growth = _build_revenue_path(
        revenue0=revenue0,
        revenue1=rev_anchor_1,
        revenue2=rev_anchor_2,
        explicit_years=explicit_years,
        terminal_growth=terminal_growth,
    )

    shares_path: list[float] = [shares0]
    for _ in range(1, explicit_years):
        shares_path.append(max(1e-6, shares_path[-1] * (1.0 - buyback_rate)))

    eps_margin_targets: list[float | None] = []
    if eps_anchor_1 is not None:
        ni1 = eps_anchor_1 * shares_path[0]
        eps_margin_targets.append(_safe_div(ni1, revenues[0]))
    else:
        eps_margin_targets.append(None)
    if explicit_years > 1:
        if eps_anchor_2 is not None:
            ni2 = eps_anchor_2 * shares_path[1]
            eps_margin_targets.append(_safe_div(ni2, revenues[1]))
        else:
            eps_margin_targets.append(None)

    ebit_margin_targets: list[float] = []
    for idx in range(min(2, explicit_years)):
        margin_eps = eps_margin_targets[idx] if idx < len(eps_margin_targets) else None
        if margin_eps is None:
            ebit_margin_targets.append(steady_ebit_margin)
            warnings.append("dcf:missing_eps_anchor")
            continue
        implied = margin_eps * kappa
        ebit_margin_targets.append(_clamp(implied, margin_p10, margin_p90))

    if not ebit_margin_targets:
        ebit_margin_targets.append(steady_ebit_margin)

    ebit_margins: list[float] = []
    for year_idx in range(1, explicit_years + 1):
        if year_idx <= len(ebit_margin_targets):
            ebit_margins.append(ebit_margin_targets[year_idx - 1])
            continue
        start_margin = ebit_margin_targets[-1]
        ebit_margins.append(_fade(start_margin, steady_ebit_margin, year_idx - 2, max(1, explicit_years - 2)))

    roic_clamped = _clamp(roic, 0.04, 0.60)
    fcff_stream: list[float] = []
    forecast_rows: list[dict[str, Any]] = []
    discount_pv = 0.0
    rev_prev = revenue0

    eps_fit_values: list[float] = []
    rev_fit_values: list[float] = []
    ratio_violations = 0

    for idx in range(explicit_years):
        year_no = idx + 1
        revenue_t = revenues[idx]
        growth_t = growth[idx] if idx < len(growth) else terminal_growth
        ebit_margin_t = ebit_margins[idx]
        ebit_t = revenue_t * ebit_margin_t
        nopat_t = ebit_t * (1.0 - tax_rate)

        da_t = revenue_t * da_ratio
        capex_t = revenue_t * capex_ratio
        delta_nwc_t = (revenue_t - rev_prev) * nwc_ratio
        fcff_ratio_t = nopat_t + da_t - capex_t - delta_nwc_t

        reinvestment_t = (growth_t / roic_clamped) * nopat_t
        fcff_roic_t = nopat_t - reinvestment_t
        fcff_t = reinvestment_blend_weight * fcff_ratio_t + (1.0 - reinvestment_blend_weight) * fcff_roic_t
        fcff_stream.append(fcff_t)

        discount_factor = (1.0 + wacc) ** year_no
        discount_pv += fcff_t / discount_factor

        shares_t = shares_path[idx]
        ni_model_t = _safe_div(ebit_margin_t, kappa) * revenue_t if kappa > 0 else None
        eps_model_t = _safe_div(ni_model_t, shares_t) if ni_model_t is not None else None
        eps_anchor_t = eps_anchor_1 if year_no == 1 else (eps_anchor_2 if year_no == 2 else None)
        if eps_model_t is not None and eps_anchor_t is not None and abs(eps_anchor_t) > 1e-12:
            eps_fit_values.append((eps_model_t - eps_anchor_t) / eps_anchor_t)

        rev_anchor_t = rev_anchor_1 if year_no == 1 else (rev_anchor_2 if year_no == 2 else None)
        if rev_anchor_t is not None and abs(rev_anchor_t) > 1e-12:
            rev_fit_values.append((revenue_t - rev_anchor_t) / rev_anchor_t)

        if ebit_margin_t < margin_p10 - 1e-9 or ebit_margin_t > margin_p90 + 1e-9:
            ratio_violations += 1
        if capex_ratio < 0 or capex_ratio > 0.5:
            ratio_violations += 1
        if roic_clamped <= terminal_growth:
            ratio_violations += 1

        forecast_rows.append(
            {
                "year": year_no,
                "revenue": revenue_t,
                "growth": growth_t,
                "shares": shares_t,
                "ebit_margin": ebit_margin_t,
                "ebit": ebit_t,
                "nopat": nopat_t,
                "da": da_t,
                "capex": capex_t,
                "delta_nwc": delta_nwc_t,
                "fcff_ratio": fcff_ratio_t,
                "fcff_roic": fcff_roic_t,
                "fcff": fcff_t,
                "eps_model": eps_model_t,
                "eps_anchor": eps_anchor_t,
            }
        )
        rev_prev = revenue_t

    fcff_n = fcff_stream[-1]
    fcff_n1 = fcff_n * (1.0 + terminal_growth)
    tv_gordon = fcff_n1 / max(wacc - terminal_growth, 1e-6)

    ebitda_margin_terminal = _clamp(ebit_margins[-1] + da_ratio, 0.01, 0.95)
    ebitda_n = revenues[-1] * ebitda_margin_terminal
    multiple_terminal = _select_terminal_multiple(sector)
    tv_multiple = ebitda_n * multiple_terminal
    tv_blended = tv_blend_weight * tv_gordon + (1.0 - tv_blend_weight) * tv_multiple

    pv_tv = tv_blended / ((1.0 + wacc) ** explicit_years)
    ev = discount_pv + pv_tv
    equity_value = ev - net_debt
    fair_value = _safe_div(equity_value, shares0)
    upside = _safe_div((fair_value - current_price) if fair_value is not None and current_price is not None else None, current_price)

    tv_pv_share = _safe_div(pv_tv, ev)
    if tv_pv_share is not None and tv_pv_share > 0.85:
        warnings.append("dcf:tv_dominance_high")

    anchor_diagnostics = {
        "rev_fit_t1": rev_fit_values[0] if len(rev_fit_values) > 0 else None,
        "rev_fit_t2": rev_fit_values[1] if len(rev_fit_values) > 1 else None,
        "eps_fit_t1": eps_fit_values[0] if len(eps_fit_values) > 0 else None,
        "eps_fit_t2": eps_fit_values[1] if len(eps_fit_values) > 1 else None,
        "ratio_violations": ratio_violations,
    }

    return DcfScenarioResult(
        scenario_key=scenario_key,
        fair_value=fair_value,
        upside=upside,
        ev=ev,
        tv_gordon=tv_gordon,
        tv_multiple=tv_multiple,
        tv_blended=tv_blended,
        tv_pv_share=tv_pv_share,
        wacc=wacc,
        terminal_growth=terminal_growth,
        warnings=warnings,
        anchor_diagnostics=anchor_diagnostics,
        forecast=forecast_rows,
    )


def _scenario_anchor(
    *,
    scenario: str,
    avg: float | None,
    low: float | None,
    high: float | None,
    fallback_spread: float,
) -> float | None:
    if scenario == "base":
        return avg
    if scenario == "bull":
        if high is not None:
            return high
        if avg is not None:
            return avg * (1.0 + fallback_spread)
        return None
    if scenario == "bear":
        if low is not None:
            return low
        if avg is not None:
            return avg * max(0.0, 1.0 - fallback_spread)
        return None
    return avg


def _quality_score(
    *,
    results: list[DcfScenarioResult],
    rev_anchor_available: tuple[bool, bool],
    eps_anchor_available: tuple[bool, bool],
    quality_penalty_enabled: bool,
) -> float:
    score = 100.0
    if not rev_anchor_available[0]:
        score -= 20.0
    if not rev_anchor_available[1]:
        score -= 20.0
    if not eps_anchor_available[0]:
        score -= 10.0
    if not eps_anchor_available[1]:
        score -= 10.0

    base_result = next((r for r in results if r.scenario_key == "base"), None)
    if base_result is not None:
        eps_fit = [
            abs(_to_float(base_result.anchor_diagnostics.get("eps_fit_t1")) or 0.0),
            abs(_to_float(base_result.anchor_diagnostics.get("eps_fit_t2")) or 0.0),
        ]
        rev_fit = [
            abs(_to_float(base_result.anchor_diagnostics.get("rev_fit_t1")) or 0.0),
            abs(_to_float(base_result.anchor_diagnostics.get("rev_fit_t2")) or 0.0),
        ]
        score -= 20.0 * _avg(eps_fit, 0.0)
        score -= 10.0 * _avg(rev_fit, 0.0)
        score -= 3.0 * float(_to_float(base_result.anchor_diagnostics.get("ratio_violations")) or 0.0)
        tv_share = _to_float(base_result.tv_pv_share)
        if tv_share is not None and tv_share > 0.85:
            score -= min(25.0, (tv_share - 0.85) * 200.0)

    if not quality_penalty_enabled:
        return _clamp(score, 0.0, 100.0)
    return _clamp(score, 0.0, 100.0)


def compute_dcf_fair_value(
    *,
    symbol: str,
    current_price: float | None,
    market_cap: float | None,
    shares_outstanding: float | None,
    beta: float | None,
    sector: str | None,
    assumptions: dict,
    forward_estimates: Mapping[str, float | int | None] | None,
    statement_inputs: Mapping[str, Any],
    ratio_inputs: Mapping[str, Any],
) -> tuple[float | None, float | None, float | None, float | None, list[str], dict[str, Any]]:
    warnings: list[str] = []
    dcf_cfg = assumptions.get("dcf", {})

    explicit_years = int(_clamp(float(dcf_cfg.get("explicit_years", 7)), 5, 10))
    rf = float(dcf_cfg.get("rf", 0.02))
    erp = float(dcf_cfg.get("erp", 0.05))
    steady_state_growth = float(dcf_cfg.get("steady_state_growth", dcf_cfg.get("terminal_growth", 0.025)))
    fallback_rev_spread = _clamp(float(dcf_cfg.get("fallback_rev_spread", 0.10)), 0.02, 0.6)
    fallback_eps_spread = _clamp(float(dcf_cfg.get("fallback_eps_spread", 0.15)), 0.02, 0.6)
    terminal_clip_buffer = _clamp(float(dcf_cfg.get("terminal_clip_buffer", 0.02)), 0.0, 0.1)
    tv_blend_weight = _clamp(float(dcf_cfg.get("tv_blend_weight", 0.65)), 0.0, 1.0)
    reinvestment_blend_weight = _clamp(float(dcf_cfg.get("reinvestment_blend_weight", 0.5)), 0.0, 1.0)
    quality_penalty_enabled = bool(dcf_cfg.get("quality_penalty_enabled", True))

    shares0 = _to_float(shares_outstanding)
    if shares0 is None or shares0 <= 0:
        warnings.append("dcf:shares_unavailable")
        return None, None, None, None, warnings, {"model_version": "dcf_v2_fcff_anchor"}

    revenue_latest = _to_float(statement_inputs.get("revenue_latest"))
    revenue_prev = _to_float(statement_inputs.get("revenue_prev"))
    growth_proxy = _to_float(statement_inputs.get("growth_proxy"))
    if growth_proxy is None:
        growth_proxy = _safe_div((revenue_latest - revenue_prev) if revenue_latest is not None and revenue_prev is not None else None, revenue_prev)
    if growth_proxy is None:
        growth_proxy = 0.06
    growth_proxy = _clamp(growth_proxy, -0.3, 0.5)

    if revenue_latest is None or revenue_latest <= 0:
        if market_cap is not None and current_price is not None and shares0 > 0:
            price_to_sales = _to_float(ratio_inputs.get("price_to_sales"))
            if price_to_sales is not None and price_to_sales > 0:
                revenue_latest = market_cap / price_to_sales
        if revenue_latest is None or revenue_latest <= 0:
            warnings.append("dcf:revenue_base_unavailable")
            return None, None, None, None, warnings, {"model_version": "dcf_v2_fcff_anchor"}

    revenue0 = revenue_latest / max(1e-6, 1.0 + growth_proxy)

    ebit_margin_history = [
        _to_float(value) for value in (statement_inputs.get("ebit_margin_history") or [])
    ]
    net_margin_history = [
        _to_float(value) for value in (statement_inputs.get("net_margin_history") or [])
    ]
    ebit_margin_history = [value for value in ebit_margin_history if value is not None]
    net_margin_history = [value for value in net_margin_history if value is not None]

    if len(ebit_margin_history) < 3:
        warnings.append("dcf:low_statement_history")

    steady_ebit_margin = _median(
        ebit_margin_history,
        _to_float(ratio_inputs.get("operating_margin")) or 0.18,
    )
    margin_p10 = _pct(ebit_margin_history, 0.10) if ebit_margin_history else _clamp(steady_ebit_margin - 0.05, -0.2, 0.7)
    margin_p90 = _pct(ebit_margin_history, 0.90) if ebit_margin_history else _clamp(steady_ebit_margin + 0.05, -0.2, 0.9)

    kappa_candidates: list[float] = []
    for ebit_margin, net_margin in zip(ebit_margin_history, net_margin_history):
        ratio = _safe_div(ebit_margin, net_margin)
        if ratio is not None and ratio > 0:
            kappa_candidates.append(ratio)
    kappa = _median(kappa_candidates, 1.30)
    kappa = _clamp(kappa, 0.2, 4.0)

    tax_rate = _to_float(statement_inputs.get("tax_rate_eff"))
    if tax_rate is None:
        tax_rate = _safe_div(
            _to_float(statement_inputs.get("tax_provision_latest")),
            _to_float(statement_inputs.get("pretax_income_latest")),
        )
    tax_rate = _clamp(float(tax_rate if tax_rate is not None else 0.21), 0.0, 0.45)

    da_ratio = _to_float(ratio_inputs.get("da_to_revenue"))
    if da_ratio is None:
        da_ratio = _safe_div(
            _to_float(statement_inputs.get("depreciation_latest")),
            revenue_latest,
        )
    da_ratio = _clamp(float(da_ratio if da_ratio is not None else 0.03), 0.0, 0.25)

    capex_ratio = _to_float(ratio_inputs.get("capex_to_revenue"))
    if capex_ratio is None:
        capex_ratio = _safe_div(abs(_to_float(statement_inputs.get("capex_latest")) or 0.0), revenue_latest)
    capex_ratio = _clamp(float(capex_ratio if capex_ratio is not None else 0.05), 0.0, 0.40)

    nwc_ratio = _to_float(ratio_inputs.get("nwc_to_revenue"))
    if nwc_ratio is None:
        current_assets_latest = _to_float(statement_inputs.get("current_assets_latest"))
        current_liabilities_latest = _to_float(statement_inputs.get("current_liabilities_latest"))
        nwc_latest = (
            (current_assets_latest - current_liabilities_latest)
            if current_assets_latest is not None and current_liabilities_latest is not None
            else None
        )
        nwc_ratio = _safe_div(nwc_latest, revenue_latest)
    nwc_ratio = _clamp(float(nwc_ratio if nwc_ratio is not None else 0.02), -0.20, 0.50)

    roic = _to_float(ratio_inputs.get("roic"))
    if roic is None:
        roic = _safe_div(_to_float(statement_inputs.get("nopat_latest")), _to_float(statement_inputs.get("invested_capital_latest")))
    roic = _clamp(float(roic if roic is not None else 0.12), 0.04, 0.60)

    shares_prev = _to_float(statement_inputs.get("diluted_shares_prev"))
    buyback_rate = 0.0
    if shares_prev is not None and shares_prev > 0:
        buyback_rate = _clamp((shares_prev - shares0) / shares_prev, -0.05, 0.10)

    total_debt = _to_float(statement_inputs.get("total_debt_latest"))
    cash_short = _to_float(statement_inputs.get("cash_and_short_latest"))
    if cash_short is None:
        cash_short = _to_float(statement_inputs.get("cash_latest"))
    net_debt = max((total_debt or 0.0) - (cash_short or 0.0), 0.0)

    avg_debt = _to_float(statement_inputs.get("avg_debt"))
    if avg_debt is None:
        total_debt_prev = _to_float(statement_inputs.get("total_debt_prev"))
        if total_debt is not None and total_debt_prev is not None:
            avg_debt = (total_debt + total_debt_prev) / 2.0
        else:
            avg_debt = total_debt

    interest_expense = _to_float(statement_inputs.get("interest_expense_latest"))
    k_d = _safe_div(interest_expense, avg_debt)
    k_d = _clamp(float(k_d if k_d is not None else 0.045), 0.02, 0.12)

    beta_used = float(beta if beta is not None else 1.0)
    k_e = rf + beta_used * erp
    e_val = _to_float(market_cap)
    if e_val is None or e_val <= 0:
        if current_price is not None:
            e_val = current_price * shares0
        else:
            e_val = revenue_latest * (_to_float(ratio_inputs.get("price_to_sales")) or 4.0)
    d_val = net_debt if net_debt > 0 else (total_debt or 0.0)
    cap_total = e_val + max(d_val, 0.0)
    if cap_total <= 0:
        wacc = _clamp(k_e, 0.06, 0.16)
    else:
        wacc = (e_val / cap_total) * k_e + (max(d_val, 0.0) / cap_total) * k_d * (1.0 - tax_rate)
        wacc = _clamp(wacc, 0.06, 0.16)

    forward = forward_estimates or {}
    rev_avg_1 = _to_float(forward.get("fy0_revenue_avg"))
    rev_low_1 = _to_float(forward.get("fy0_revenue_low"))
    rev_high_1 = _to_float(forward.get("fy0_revenue_high"))
    rev_avg_2 = _to_float(forward.get("fy1_revenue_avg"))
    rev_low_2 = _to_float(forward.get("fy1_revenue_low"))
    rev_high_2 = _to_float(forward.get("fy1_revenue_high"))
    eps_avg_1 = _to_float(forward.get("fy0_eps_avg"))
    eps_low_1 = _to_float(forward.get("fy0_eps_low"))
    eps_high_1 = _to_float(forward.get("fy0_eps_high"))
    eps_avg_2 = _to_float(forward.get("fy1_eps_avg"))
    eps_low_2 = _to_float(forward.get("fy1_eps_low"))
    eps_high_2 = _to_float(forward.get("fy1_eps_high"))

    if rev_avg_1 is None:
        rev_avg_1 = revenue_latest * (1.0 + growth_proxy)
        warnings.append("dcf:missing_rev_anchor")
    if rev_avg_2 is None:
        rev_avg_2 = rev_avg_1 * (1.0 + growth_proxy * 0.8)
        warnings.append("dcf:missing_rev_anchor")

    if rev_low_1 is None and rev_avg_1 is not None:
        rev_low_1 = rev_avg_1 * (1.0 - fallback_rev_spread)
    if rev_high_1 is None and rev_avg_1 is not None:
        rev_high_1 = rev_avg_1 * (1.0 + fallback_rev_spread)
    if rev_low_2 is None and rev_avg_2 is not None:
        rev_low_2 = rev_avg_2 * (1.0 - fallback_rev_spread)
    if rev_high_2 is None and rev_avg_2 is not None:
        rev_high_2 = rev_avg_2 * (1.0 + fallback_rev_spread)

    if eps_avg_1 is None and _to_float(statement_inputs.get("diluted_eps_latest")) is not None:
        eps_avg_1 = _to_float(statement_inputs.get("diluted_eps_latest")) * (1.0 + growth_proxy * 0.5)
    if eps_avg_2 is None and eps_avg_1 is not None:
        eps_avg_2 = eps_avg_1 * (1.0 + growth_proxy * 0.4)

    if eps_low_1 is None and eps_avg_1 is not None:
        eps_low_1 = eps_avg_1 * (1.0 - fallback_eps_spread)
    if eps_high_1 is None and eps_avg_1 is not None:
        eps_high_1 = eps_avg_1 * (1.0 + fallback_eps_spread)
    if eps_low_2 is None and eps_avg_2 is not None:
        eps_low_2 = eps_avg_2 * (1.0 - fallback_eps_spread)
    if eps_high_2 is None and eps_avg_2 is not None:
        eps_high_2 = eps_avg_2 * (1.0 + fallback_eps_spread)

    # Terminal growth is estimated from available growth signals, then clipped
    # by valuation safety margin: g <= WACC - x.
    anchor_growth = _safe_div(
        (rev_avg_2 - rev_avg_1) if rev_avg_1 is not None and rev_avg_2 is not None else None,
        rev_avg_1,
    )
    growth_candidates: list[float] = [_clamp(steady_state_growth, -0.02, 0.10)]
    growth_candidates.append(_clamp(growth_proxy * 0.35, -0.02, 0.10))
    if anchor_growth is not None:
        growth_candidates.append(_clamp(anchor_growth * 0.35, -0.02, 0.10))
    growth_candidates.append(_clamp(roic * 0.15, -0.02, 0.10))
    terminal_growth_raw = _clamp(_median(growth_candidates, steady_state_growth), -0.02, 0.08)
    terminal_growth_ceiling = wacc - terminal_clip_buffer
    if terminal_growth_ceiling <= -0.02:
        warnings.append("dcf:terminal_clip_buffer_too_large")
        terminal_growth_ceiling = max(-0.015, wacc - 0.005)
    terminal_growth = _clamp(terminal_growth_raw, -0.02, terminal_growth_ceiling)
    if terminal_growth >= wacc:
        terminal_growth = wacc - 0.001

    scenario_definitions = {
        "base": {
            "rev1": _scenario_anchor(scenario="base", avg=rev_avg_1, low=rev_low_1, high=rev_high_1, fallback_spread=fallback_rev_spread),
            "rev2": _scenario_anchor(scenario="base", avg=rev_avg_2, low=rev_low_2, high=rev_high_2, fallback_spread=fallback_rev_spread),
            "eps1": _scenario_anchor(scenario="base", avg=eps_avg_1, low=eps_low_1, high=eps_high_1, fallback_spread=fallback_eps_spread),
            "eps2": _scenario_anchor(scenario="base", avg=eps_avg_2, low=eps_low_2, high=eps_high_2, fallback_spread=fallback_eps_spread),
        },
        "bull": {
            "rev1": _scenario_anchor(scenario="bull", avg=rev_avg_1, low=rev_low_1, high=rev_high_1, fallback_spread=fallback_rev_spread),
            "rev2": _scenario_anchor(scenario="bull", avg=rev_avg_2, low=rev_low_2, high=rev_high_2, fallback_spread=fallback_rev_spread),
            "eps1": _scenario_anchor(scenario="bull", avg=eps_avg_1, low=eps_low_1, high=eps_high_1, fallback_spread=fallback_eps_spread),
            "eps2": _scenario_anchor(scenario="bull", avg=eps_avg_2, low=eps_low_2, high=eps_high_2, fallback_spread=fallback_eps_spread),
        },
        "bear": {
            "rev1": _scenario_anchor(scenario="bear", avg=rev_avg_1, low=rev_low_1, high=rev_high_1, fallback_spread=fallback_rev_spread),
            "rev2": _scenario_anchor(scenario="bear", avg=rev_avg_2, low=rev_low_2, high=rev_high_2, fallback_spread=fallback_rev_spread),
            "eps1": _scenario_anchor(scenario="bear", avg=eps_avg_1, low=eps_low_1, high=eps_high_1, fallback_spread=fallback_eps_spread),
            "eps2": _scenario_anchor(scenario="bear", avg=eps_avg_2, low=eps_low_2, high=eps_high_2, fallback_spread=fallback_eps_spread),
        },
    }

    scenario_results: list[DcfScenarioResult] = []
    for scenario_key, anchors in scenario_definitions.items():
        result = _run_fcff_scenario(
            scenario_key=scenario_key,
            current_price=current_price,
            shares0=shares0,
            sector=sector,
            explicit_years=explicit_years,
            rev_anchor_1=float(anchors["rev1"]) if anchors["rev1"] is not None else -1.0,
            rev_anchor_2=float(anchors["rev2"]) if anchors["rev2"] is not None else -1.0,
            eps_anchor_1=_to_float(anchors["eps1"]),
            eps_anchor_2=_to_float(anchors["eps2"]),
            revenue0=float(revenue0),
            tax_rate=tax_rate,
            kappa=kappa,
            buyback_rate=buyback_rate,
            margin_p10=margin_p10,
            margin_p90=margin_p90,
            steady_ebit_margin=steady_ebit_margin,
            da_ratio=da_ratio,
            capex_ratio=capex_ratio,
            nwc_ratio=nwc_ratio,
            roic=roic,
            wacc=wacc,
            terminal_growth=terminal_growth,
            tv_blend_weight=tv_blend_weight,
            reinvestment_blend_weight=reinvestment_blend_weight,
            net_debt=net_debt,
        )
        scenario_results.append(result)
        warnings.extend(result.warnings)

    scenario_map = {result.scenario_key: result for result in scenario_results}
    base = scenario_map.get("base")
    bull = scenario_map.get("bull")
    bear = scenario_map.get("bear")

    fair_value = base.fair_value if base is not None else None
    low = bear.fair_value if bear is not None else None
    high = bull.fair_value if bull is not None else None
    if low is None or high is None:
        values = [value for value in [fair_value, low, high] if value is not None]
        if values:
            low = min(values)
            high = max(values)

    upside = None
    if fair_value is not None and current_price is not None and current_price > 0:
        upside = fair_value / current_price - 1.0

    quality = _quality_score(
        results=scenario_results,
        rev_anchor_available=(rev_avg_1 is not None, rev_avg_2 is not None),
        eps_anchor_available=(eps_avg_1 is not None, eps_avg_2 is not None),
        quality_penalty_enabled=quality_penalty_enabled,
    )
    if quality < 60:
        warnings.append("dcf:quality_low")

    detail = {
        "model_version": "dcf_v2_fcff_anchor",
        "quality_score": quality,
        "anchor_mode": dcf_cfg.get("anchor_mode", "revenue_only"),
        "scenario_results": {
            result.scenario_key: {
                "fair_value": result.fair_value,
                "upside": result.upside,
                "ev": result.ev,
                "tv_gordon": result.tv_gordon,
                "tv_multiple": result.tv_multiple,
                "tv_blended": result.tv_blended,
                "tv_pv_share": result.tv_pv_share,
                "wacc": result.wacc,
                "terminal_growth": result.terminal_growth,
                "anchor_diagnostics": result.anchor_diagnostics,
                "forecast": result.forecast,
                "warnings": sorted(set(result.warnings)),
            }
            for result in scenario_results
        },
        "anchor_diagnostics_summary": {
            "rev_fit_t1": base.anchor_diagnostics.get("rev_fit_t1") if base else None,
            "rev_fit_t2": base.anchor_diagnostics.get("rev_fit_t2") if base else None,
            "eps_fit_t1": base.anchor_diagnostics.get("eps_fit_t1") if base else None,
            "eps_fit_t2": base.anchor_diagnostics.get("eps_fit_t2") if base else None,
            "ratio_violations": base.anchor_diagnostics.get("ratio_violations") if base else None,
        },
        "tv_breakdown_summary": {
            "tv_method": dcf_cfg.get("tv_method", "blended"),
            "tv_blend_weight": tv_blend_weight,
            "terminal_growth_raw": terminal_growth_raw,
            "terminal_growth_ceiling": terminal_growth_ceiling,
            "terminal_clip_buffer": terminal_clip_buffer,
            "base_tv_gordon": base.tv_gordon if base else None,
            "base_tv_multiple": base.tv_multiple if base else None,
            "base_tv_blended": base.tv_blended if base else None,
            "base_tv_pv_share": base.tv_pv_share if base else None,
            "terminal_multiple_used": _select_terminal_multiple(sector),
        },
        "assumptions_used": {
            "explicit_years": explicit_years,
            "rf": rf,
            "erp": erp,
            "tax_rate": tax_rate,
            "wacc": wacc,
            "steady_state_growth": steady_state_growth,
            "terminal_growth_raw": terminal_growth_raw,
            "terminal_growth_ceiling": terminal_growth_ceiling,
            "terminal_clip_buffer": terminal_clip_buffer,
            "terminal_growth": terminal_growth,
            "reinvestment_blend_weight": reinvestment_blend_weight,
            "tv_blend_weight": tv_blend_weight,
            "steady_ebit_margin": steady_ebit_margin,
            "kappa": kappa,
            "buyback_rate": buyback_rate,
            "da_ratio": da_ratio,
            "capex_ratio": capex_ratio,
            "nwc_ratio": nwc_ratio,
            "roic": roic,
            "net_debt": net_debt,
        },
    }

    return fair_value, low, high, upside, sorted(set(warnings)), detail
