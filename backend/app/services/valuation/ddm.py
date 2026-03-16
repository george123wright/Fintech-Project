from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number):  # NaN
        return None
    return number


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def _fade(start: float, end: float, step: int, total_steps: int) -> float:
    if total_steps <= 0:
        return end
    t = _clamp(step / total_steps, 0.0, 1.0)
    return start + (end - start) * t


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


def _median(values: list[float | None], fallback: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return fallback
    return float(median(cleaned))


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


@dataclass
class DdmScenarioResult:
    scenario_key: str
    fair_value: float | None
    upside: float | None
    pv_stage1: float | None
    terminal_value: float | None
    terminal_pv: float | None
    tv_pv_share: float | None
    cost_of_equity: float | None
    terminal_growth: float | None
    warnings: list[str]
    anchor_diagnostics: dict[str, Any]
    forecast: list[dict[str, Any]]


def _run_ddm_scenario(
    *,
    scenario_key: str,
    current_price: float | None,
    explicit_years: int,
    shares0: float,
    buyback_rate: float,
    eps_anchor_1: float | None,
    eps_anchor_2: float | None,
    rev_anchor_1: float | None,
    rev_anchor_2: float | None,
    eps_latest: float,
    eps_terminal_growth: float,
    payout_start_1: float,
    payout_start_2: float,
    payout_cap: float,
    payout_shift: float,
    long_run_payout: float,
    cost_of_equity: float,
    terminal_growth: float,
    margin_p10: float,
    margin_p90: float,
) -> DdmScenarioResult:
    warnings: list[str] = []

    if eps_anchor_1 is None and eps_anchor_2 is None and eps_latest <= 0:
        warnings.append("ddm:missing_eps_anchor")
        return DdmScenarioResult(
            scenario_key=scenario_key,
            fair_value=None,
            upside=None,
            pv_stage1=None,
            terminal_value=None,
            terminal_pv=None,
            tv_pv_share=None,
            cost_of_equity=cost_of_equity,
            terminal_growth=terminal_growth,
            warnings=warnings,
            anchor_diagnostics={},
            forecast=[],
        )

    eps_path: list[float] = []
    if eps_anchor_1 is not None:
        eps_path.append(float(eps_anchor_1))
    else:
        eps_path.append(eps_latest * (1.0 + eps_terminal_growth))
        warnings.append("ddm:missing_eps_anchor")

    if explicit_years > 1:
        if eps_anchor_2 is not None:
            eps_path.append(float(eps_anchor_2))
        else:
            eps_path.append(eps_path[0] * (1.0 + eps_terminal_growth))
            warnings.append("ddm:missing_eps_anchor")

    while len(eps_path) < explicit_years:
        year_no = len(eps_path) + 1
        g_year = _fade(
            _safe_div(eps_path[1] - eps_path[0], abs(eps_path[0])) if len(eps_path) >= 2 else eps_terminal_growth,
            eps_terminal_growth,
            max(0, year_no - 2),
            max(1, explicit_years - 2),
        )
        prev = eps_path[-1]
        eps_path.append(prev * (1.0 + g_year))

    shares_path: list[float] = [shares0]
    for _ in range(1, explicit_years):
        shares_path.append(max(1e-6, shares_path[-1] * (1.0 - buyback_rate)))

    payout_path: list[float] = []
    for idx in range(explicit_years):
        if idx == 0:
            payout = payout_start_1
        elif idx == 1:
            payout = payout_start_2
        else:
            payout = _fade(payout_start_2, long_run_payout, idx - 1, max(1, explicit_years - 2))
        payout = _clamp(payout + payout_shift, 0.0, payout_cap)
        payout_path.append(payout)

    pv_stage1 = 0.0
    cum_pv = 0.0
    eps_fit_values: list[float] = []
    rev_fit_values: list[float] = []
    payout_violations = 0
    margin_outliers = 0
    forced_zero_dividends = 0
    forecast_rows: list[dict[str, Any]] = []
    dps_last = 0.0

    for idx in range(explicit_years):
        year_no = idx + 1
        eps_t = eps_path[idx]
        payout_t = payout_path[idx]
        dps_t = max(eps_t, 0.0) * payout_t
        if eps_t < 0 and payout_t > 0:
            forced_zero_dividends += 1

        if payout_t < -1e-9 or payout_t > payout_cap + 1e-9:
            payout_violations += 1

        disc = (1.0 + cost_of_equity) ** year_no
        pv_div = dps_t / disc
        pv_stage1 += pv_div
        cum_pv += pv_div

        ni_t = eps_t * shares_path[idx]
        rev_anchor_t = rev_anchor_1 if year_no == 1 else (rev_anchor_2 if year_no == 2 else None)
        margin_implied = _safe_div(ni_t, rev_anchor_t) if rev_anchor_t is not None and rev_anchor_t > 0 else None
        if margin_implied is not None and (margin_implied < margin_p10 or margin_implied > margin_p90):
            margin_outliers += 1

        eps_anchor_t = eps_anchor_1 if year_no == 1 else (eps_anchor_2 if year_no == 2 else None)
        if eps_anchor_t is not None and abs(eps_anchor_t) > 1e-12:
            eps_fit_values.append((eps_t - eps_anchor_t) / eps_anchor_t)
        if rev_anchor_t is not None and rev_anchor_t > 0:
            rev_fit_values.append((ni_t / rev_anchor_t) if rev_anchor_t > 0 else 0.0)

        forecast_rows.append(
            {
                "year": year_no,
                "eps": eps_t,
                "payout": payout_t,
                "dps": dps_t,
                "pv_dividend": pv_div,
                "cum_pv": cum_pv,
                "shares": shares_path[idx],
                "net_income": ni_t,
                "revenue_anchor": rev_anchor_t,
                "eps_anchor": eps_anchor_t,
                "implied_payout": _safe_div(dps_t, eps_t) if eps_t > 0 else None,
                "margin_implied": margin_implied,
            }
        )
        dps_last = dps_t

    dps_n1 = dps_last * (1.0 + terminal_growth)
    terminal_value = None
    terminal_pv = None
    if cost_of_equity > terminal_growth and dps_n1 >= 0:
        terminal_value = dps_n1 / (cost_of_equity - terminal_growth)
        terminal_pv = terminal_value / ((1.0 + cost_of_equity) ** explicit_years)

    fair_value = None
    if terminal_pv is not None:
        fair_value = pv_stage1 + terminal_pv
    tv_pv_share = _safe_div(terminal_pv, fair_value) if fair_value is not None else None
    if tv_pv_share is not None and tv_pv_share > 0.85:
        warnings.append("ddm:terminal_dominance_high")
    if margin_outliers > 0:
        warnings.append("ddm:margin_consistency_outlier")
    if payout_violations > 0:
        warnings.append("ddm:payout_outlier")
    if forced_zero_dividends > 0:
        warnings.append("ddm:eps_negative_dividend_forced_zero")

    upside = None
    if fair_value is not None and current_price is not None and current_price > 0:
        upside = fair_value / current_price - 1.0

    return DdmScenarioResult(
        scenario_key=scenario_key,
        fair_value=fair_value,
        upside=upside,
        pv_stage1=pv_stage1,
        terminal_value=terminal_value,
        terminal_pv=terminal_pv,
        tv_pv_share=tv_pv_share,
        cost_of_equity=cost_of_equity,
        terminal_growth=terminal_growth,
        warnings=warnings,
        anchor_diagnostics={
            "eps_fit_t1": eps_fit_values[0] if len(eps_fit_values) > 0 else None,
            "eps_fit_t2": eps_fit_values[1] if len(eps_fit_values) > 1 else None,
            "margin_implied_t1": rev_fit_values[0] if len(rev_fit_values) > 0 else None,
            "margin_implied_t2": rev_fit_values[1] if len(rev_fit_values) > 1 else None,
            "payout_violations": payout_violations,
            "margin_outliers": margin_outliers,
            "forced_zero_dividends": forced_zero_dividends,
        },
        forecast=forecast_rows,
    )


def _quality_score(
    *,
    base: DdmScenarioResult | None,
    eps_anchor_available: tuple[bool, bool],
    payout_hist_available: bool,
    hybrid_mode_used: bool,
    quality_penalty_enabled: bool,
) -> float:
    if base is None or base.fair_value is None:
        return 0.0
    if not quality_penalty_enabled:
        return 100.0

    score = 100.0
    missing_eps = 2 - int(eps_anchor_available[0]) - int(eps_anchor_available[1])
    score -= 15.0 * missing_eps

    if not payout_hist_available:
        score -= 10.0
    if hybrid_mode_used:
        score -= 8.0

    payout_violations = _to_float(base.anchor_diagnostics.get("payout_violations")) or 0.0
    margin_outliers = _to_float(base.anchor_diagnostics.get("margin_outliers")) or 0.0
    score -= min(20.0, payout_violations * 4.0)
    score -= min(20.0, margin_outliers * 4.0)

    tv_share = base.tv_pv_share or 0.0
    if tv_share > 0.85:
        score -= min(25.0, (tv_share - 0.85) * 100.0)

    return _clamp(score, 0.0, 100.0)


def compute_ddm_fair_value(
    *,
    symbol: str,
    current_price: float | None,
    beta: float | None,
    assumptions: dict,
    forward_estimates: Mapping[str, float | int | None] | None = None,
    statement_inputs: Mapping[str, Any] | None = None,
    ratio_inputs: Mapping[str, Any] | None = None,
    shares_outstanding: float | None = None,
) -> tuple[float | None, float | None, float | None, float | None, list[str], dict[str, Any]]:
    warnings: list[str] = []
    ddm_cfg = assumptions.get("ddm", {})
    dcf_cfg = assumptions.get("dcf", {})
    forward = forward_estimates or {}
    statements = statement_inputs or {}
    ratios = ratio_inputs or {}

    explicit_years = int(_clamp(float(ddm_cfg.get("explicit_years", 7)), 5, 10))
    anchor_mode = str(ddm_cfg.get("anchor_mode", "eps_payout_linked"))
    coverage_mode = str(ddm_cfg.get("coverage_mode", "hybrid_eps_payout"))
    terminal_method = str(ddm_cfg.get("terminal_method", "two_stage_gordon"))
    steady_state_growth = _clamp(float(ddm_cfg.get("steady_state_growth", 0.025)), -0.01, 0.08)
    long_run_payout = _clamp(float(ddm_cfg.get("long_run_payout", 0.35)), 0.0, 0.95)
    payout_smoothing_weight = _clamp(float(ddm_cfg.get("payout_smoothing_weight", 0.60)), 0.0, 1.0)
    initiation_payout_floor = _clamp(float(ddm_cfg.get("initiation_payout_floor", 0.08)), 0.0, 0.5)
    payout_cap = _clamp(float(ddm_cfg.get("payout_cap", 0.90)), 0.3, 1.2)
    fallback_eps_spread = _clamp(float(ddm_cfg.get("fallback_eps_spread", 0.15)), 0.01, 1.0)
    fallback_payout_spread = _clamp(float(ddm_cfg.get("fallback_payout_spread", 0.10)), 0.0, 0.5)
    terminal_clip_buffer = _clamp(float(ddm_cfg.get("terminal_clip_buffer", 0.02)), 0.0, 0.1)
    quality_penalty_enabled = bool(ddm_cfg.get("quality_penalty_enabled", True))

    rf = float(dcf_cfg.get("rf", 0.02))
    erp = float(dcf_cfg.get("erp", 0.05))
    beta_used = float(beta if beta is not None else 1.0)
    cost_of_equity = _to_float(ddm_cfg.get("cost_of_equity"))
    if cost_of_equity is None:
        cost_of_equity = rf + beta_used * erp
    cost_of_equity = _clamp(cost_of_equity, 0.06, 0.18)

    shares0 = _to_float(shares_outstanding)
    if shares0 is None or shares0 <= 0:
        shares0 = _to_float(statements.get("diluted_shares_latest"))
    if shares0 is None or shares0 <= 0:
        warnings.append("ddm:missing_shares")
        return None, None, None, None, warnings, {"model_version": "ddm_v2_eps_dps"}

    shares_prev = _to_float(statements.get("diluted_shares_prev"))
    buyback_rate = 0.0
    if shares_prev is not None and shares_prev > 0:
        buyback_rate = _clamp((shares_prev - shares0) / shares_prev, -0.05, 0.08)

    eps_latest = _to_float(statements.get("diluted_eps_latest"))
    if eps_latest is None:
        eps_latest = _to_float(ratios.get("eps_growth_yoy"))
    if eps_latest is None:
        eps_latest = 0.0

    growth_proxy = _to_float(statements.get("growth_proxy"))
    if growth_proxy is None:
        growth_proxy = _to_float(ratios.get("eps_growth_yoy"))
    if growth_proxy is None:
        growth_proxy = 0.05
    growth_proxy = _clamp(growth_proxy, -0.30, 0.60)
    eps_terminal_growth = _clamp(steady_state_growth, -0.01, 0.08)

    payout_hist = _to_float(ratios.get("payout_ratio"))
    dividends_paid_latest = _to_float(statements.get("dividends_paid_latest"))
    net_income_latest = _to_float(statements.get("net_income_latest"))
    payout_hist_available = payout_hist is not None
    if payout_hist is None and dividends_paid_latest is not None and net_income_latest not in (None, 0.0):
        payout_hist = _safe_div(abs(dividends_paid_latest), net_income_latest)
        payout_hist_available = payout_hist is not None
    if payout_hist is None:
        dividend_yield = _to_float(ratios.get("dividend_yield"))
        if dividend_yield is not None and current_price is not None and current_price > 0 and eps_latest != 0:
            trail_dps = dividend_yield * current_price
            payout_hist = _safe_div(trail_dps, eps_latest)
            payout_hist_available = payout_hist is not None
    if payout_hist is None:
        payout_hist = long_run_payout
    payout_hist = _clamp(payout_hist, 0.0, payout_cap)

    payout_base = _clamp(
        payout_smoothing_weight * payout_hist + (1.0 - payout_smoothing_weight) * long_run_payout,
        0.0,
        payout_cap,
    )

    trail_dps_from_cash = _safe_div(abs(dividends_paid_latest) if dividends_paid_latest is not None else None, shares0)
    trailing_dps = trail_dps_from_cash
    if trailing_dps is None:
        dividend_yield = _to_float(ratios.get("dividend_yield"))
        if dividend_yield is not None and current_price is not None and current_price > 0:
            trailing_dps = dividend_yield * current_price

    hybrid_mode_used = False
    if (trailing_dps is None or trailing_dps <= 1e-8) and eps_latest > 0 and coverage_mode == "hybrid_eps_payout":
        payout_start_1 = max(initiation_payout_floor, 0.25 * long_run_payout)
        payout_start_2 = max(payout_start_1, 0.60 * long_run_payout)
        hybrid_mode_used = True
        warnings.append("ddm:missing_dividend_history")
        warnings.append("ddm:hybrid_initiation_mode")
    else:
        payout_start_1 = payout_base
        payout_start_2 = _fade(payout_base, long_run_payout, 1, max(1, explicit_years - 1))

    roe_long = _to_float(ratios.get("roe"))
    if roe_long is None:
        roe_long = 0.12
    roe_long = _clamp(roe_long, 0.0, 0.6)
    g_sustainable = roe_long * max(0.0, 1.0 - long_run_payout)

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

    if eps_avg_1 is None:
        eps_avg_1 = eps_latest * (1.0 + growth_proxy)
        warnings.append("ddm:missing_eps_anchor")
    if eps_avg_2 is None:
        eps_avg_2 = eps_avg_1 * (1.0 + 0.8 * growth_proxy)
        warnings.append("ddm:missing_eps_anchor")

    if eps_low_1 is None and eps_avg_1 is not None:
        eps_low_1 = eps_avg_1 * (1.0 - fallback_eps_spread)
    if eps_high_1 is None and eps_avg_1 is not None:
        eps_high_1 = eps_avg_1 * (1.0 + fallback_eps_spread)
    if eps_low_2 is None and eps_avg_2 is not None:
        eps_low_2 = eps_avg_2 * (1.0 - fallback_eps_spread)
    if eps_high_2 is None and eps_avg_2 is not None:
        eps_high_2 = eps_avg_2 * (1.0 + fallback_eps_spread)

    # Terminal growth is estimated from available growth signals, then clipped
    # by valuation safety margin: g <= CoE - x.
    eps_anchor_growth = _safe_div(
        (eps_avg_2 - eps_avg_1) if eps_avg_1 is not None and eps_avg_2 is not None else None,
        abs(eps_avg_1) if eps_avg_1 not in (None, 0) else None,
    )
    growth_candidates: list[float] = [_clamp(steady_state_growth, -0.02, 0.10)]
    growth_candidates.append(_clamp(g_sustainable, -0.02, 0.10))
    growth_candidates.append(_clamp(growth_proxy * 0.35, -0.02, 0.10))
    if eps_anchor_growth is not None:
        growth_candidates.append(_clamp(eps_anchor_growth * 0.35, -0.02, 0.10))
    terminal_growth_raw = _clamp(_median(growth_candidates, steady_state_growth), -0.02, 0.08)
    terminal_growth_ceiling = cost_of_equity - terminal_clip_buffer
    if terminal_growth_ceiling <= -0.02:
        warnings.append("ddm:terminal_clip_buffer_too_large")
        terminal_growth_ceiling = max(-0.015, cost_of_equity - 0.005)
    terminal_growth = _clamp(min(terminal_growth_raw, g_sustainable), -0.02, terminal_growth_ceiling)
    if terminal_growth >= cost_of_equity:
        terminal_growth = cost_of_equity - 0.001

    net_margin_hist_raw = statements.get("net_margin_history") or []
    net_margin_history = [_to_float(v) for v in net_margin_hist_raw]
    net_margin_history = [v for v in net_margin_history if v is not None]
    net_margin_mid = _median(net_margin_history, _to_float(ratios.get("net_margin")) or 0.10)
    margin_p10 = _pct(net_margin_history, 0.10) if net_margin_history else net_margin_mid - 0.04
    margin_p90 = _pct(net_margin_history, 0.90) if net_margin_history else net_margin_mid + 0.04
    margin_p10 = _clamp(margin_p10, -0.4, 0.8)
    margin_p90 = _clamp(margin_p90, -0.3, 1.0)

    scenario_definitions = {
        "base": {
            "eps1": _scenario_anchor(
                scenario="base",
                avg=eps_avg_1,
                low=eps_low_1,
                high=eps_high_1,
                fallback_spread=fallback_eps_spread,
            ),
            "eps2": _scenario_anchor(
                scenario="base",
                avg=eps_avg_2,
                low=eps_low_2,
                high=eps_high_2,
                fallback_spread=fallback_eps_spread,
            ),
            "rev1": _scenario_anchor(
                scenario="base",
                avg=rev_avg_1,
                low=rev_low_1,
                high=rev_high_1,
                fallback_spread=fallback_eps_spread,
            ),
            "rev2": _scenario_anchor(
                scenario="base",
                avg=rev_avg_2,
                low=rev_low_2,
                high=rev_high_2,
                fallback_spread=fallback_eps_spread,
            ),
            "payout_shift": 0.0,
        },
        "bull": {
            "eps1": _scenario_anchor(
                scenario="bull",
                avg=eps_avg_1,
                low=eps_low_1,
                high=eps_high_1,
                fallback_spread=fallback_eps_spread,
            ),
            "eps2": _scenario_anchor(
                scenario="bull",
                avg=eps_avg_2,
                low=eps_low_2,
                high=eps_high_2,
                fallback_spread=fallback_eps_spread,
            ),
            "rev1": _scenario_anchor(
                scenario="bull",
                avg=rev_avg_1,
                low=rev_low_1,
                high=rev_high_1,
                fallback_spread=fallback_eps_spread,
            ),
            "rev2": _scenario_anchor(
                scenario="bull",
                avg=rev_avg_2,
                low=rev_low_2,
                high=rev_high_2,
                fallback_spread=fallback_eps_spread,
            ),
            "payout_shift": fallback_payout_spread,
        },
        "bear": {
            "eps1": _scenario_anchor(
                scenario="bear",
                avg=eps_avg_1,
                low=eps_low_1,
                high=eps_high_1,
                fallback_spread=fallback_eps_spread,
            ),
            "eps2": _scenario_anchor(
                scenario="bear",
                avg=eps_avg_2,
                low=eps_low_2,
                high=eps_high_2,
                fallback_spread=fallback_eps_spread,
            ),
            "rev1": _scenario_anchor(
                scenario="bear",
                avg=rev_avg_1,
                low=rev_low_1,
                high=rev_high_1,
                fallback_spread=fallback_eps_spread,
            ),
            "rev2": _scenario_anchor(
                scenario="bear",
                avg=rev_avg_2,
                low=rev_low_2,
                high=rev_high_2,
                fallback_spread=fallback_eps_spread,
            ),
            "payout_shift": -fallback_payout_spread,
        },
    }

    scenario_results: list[DdmScenarioResult] = []
    for scenario_key, anchors in scenario_definitions.items():
        result = _run_ddm_scenario(
            scenario_key=scenario_key,
            current_price=current_price,
            explicit_years=explicit_years,
            shares0=shares0,
            buyback_rate=buyback_rate,
            eps_anchor_1=_to_float(anchors.get("eps1")),
            eps_anchor_2=_to_float(anchors.get("eps2")),
            rev_anchor_1=_to_float(anchors.get("rev1")),
            rev_anchor_2=_to_float(anchors.get("rev2")),
            eps_latest=eps_latest,
            eps_terminal_growth=eps_terminal_growth,
            payout_start_1=payout_start_1,
            payout_start_2=payout_start_2,
            payout_cap=payout_cap,
            payout_shift=float(anchors.get("payout_shift") or 0.0),
            long_run_payout=long_run_payout,
            cost_of_equity=cost_of_equity,
            terminal_growth=terminal_growth,
            margin_p10=margin_p10,
            margin_p90=margin_p90,
        )
        scenario_results.append(result)
        warnings.extend(result.warnings)

    scenario_map = {row.scenario_key: row for row in scenario_results}
    base = scenario_map.get("base")
    bull = scenario_map.get("bull")
    bear = scenario_map.get("bear")

    fair_value = base.fair_value if base is not None else None
    low = bear.fair_value if bear is not None else None
    high = bull.fair_value if bull is not None else None
    if low is None or high is None:
        values = [v for v in [fair_value, low, high] if v is not None]
        if values:
            low = min(values)
            high = max(values)

    upside = None
    if fair_value is not None and current_price is not None and current_price > 0:
        upside = fair_value / current_price - 1.0

    quality = _quality_score(
        base=base,
        eps_anchor_available=(eps_avg_1 is not None, eps_avg_2 is not None),
        payout_hist_available=payout_hist_available,
        hybrid_mode_used=hybrid_mode_used,
        quality_penalty_enabled=quality_penalty_enabled,
    )
    if quality < 60:
        warnings.append("ddm:quality_low")

    detail = {
        "model_version": "ddm_v2_eps_dps",
        "quality_score": quality,
        "anchor_mode": anchor_mode,
        "coverage_mode": coverage_mode,
        "terminal_method": terminal_method,
        "scenario_results": {
            row.scenario_key: {
                "fair_value": row.fair_value,
                "upside": row.upside,
                "pv_stage1": row.pv_stage1,
                "terminal_value": row.terminal_value,
                "terminal_pv": row.terminal_pv,
                "tv_pv_share": row.tv_pv_share,
                "cost_of_equity": row.cost_of_equity,
                "terminal_growth": row.terminal_growth,
                "anchor_diagnostics": row.anchor_diagnostics,
                "forecast": row.forecast,
                "warnings": sorted(set(row.warnings)),
            }
            for row in scenario_results
        },
        "anchor_diagnostics_summary": {
            "eps_fit_t1": (base.anchor_diagnostics.get("eps_fit_t1") if base else None),
            "eps_fit_t2": (base.anchor_diagnostics.get("eps_fit_t2") if base else None),
            "margin_implied_t1": (base.anchor_diagnostics.get("margin_implied_t1") if base else None),
            "margin_implied_t2": (base.anchor_diagnostics.get("margin_implied_t2") if base else None),
            "payout_violations": (base.anchor_diagnostics.get("payout_violations") if base else None),
            "margin_outliers": (base.anchor_diagnostics.get("margin_outliers") if base else None),
        },
        "terminal_summary": {
            "terminal_method": terminal_method,
            "terminal_growth_raw": terminal_growth_raw,
            "terminal_growth_ceiling": terminal_growth_ceiling,
            "terminal_clip_buffer": terminal_clip_buffer,
            "base_terminal_value": (base.terminal_value if base else None),
            "base_terminal_pv": (base.terminal_pv if base else None),
            "base_tv_pv_share": (base.tv_pv_share if base else None),
        },
        "assumptions_used": {
            "explicit_years": explicit_years,
            "rf": rf,
            "erp": erp,
            "beta": beta_used,
            "cost_of_equity": cost_of_equity,
            "steady_state_growth": steady_state_growth,
            "eps_terminal_growth": eps_terminal_growth,
            "terminal_growth_raw": terminal_growth_raw,
            "terminal_growth_ceiling": terminal_growth_ceiling,
            "terminal_clip_buffer": terminal_clip_buffer,
            "terminal_growth": terminal_growth,
            "long_run_payout": long_run_payout,
            "payout_smoothing_weight": payout_smoothing_weight,
            "initiation_payout_floor": initiation_payout_floor,
            "payout_cap": payout_cap,
            "buyback_rate": buyback_rate,
            "shares0": shares0,
            "hybrid_mode_used": hybrid_mode_used,
            "payout_hist": payout_hist,
        },
    }
    return fair_value, low, high, upside, sorted(set(warnings)), detail
