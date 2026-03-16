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
    if not (number == number):
        return None
    return number


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


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


def _fade(start: float, end: float, step: int, total_steps: int) -> float:
    if total_steps <= 0:
        return end
    t = _clamp(step / total_steps, 0.0, 1.0)
    return start + (end - start) * t


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


@dataclass
class RiScenarioResult:
    scenario_key: str
    fair_value: float | None
    upside: float | None
    equity_value: float | None
    pv_residual_stream: float | None
    tv_gordon: float | None
    tv_fade: float | None
    tv_blended: float | None
    tv_pv_share: float | None
    cost_of_equity: float | None
    terminal_growth: float | None
    warnings: list[str]
    anchor_diagnostics: dict[str, Any]
    forecast: list[dict[str, Any]]


def _run_ri_scenario(
    *,
    scenario_key: str,
    current_price: float | None,
    shares0: float,
    explicit_years: int,
    fade_years_post_horizon: int,
    rev_anchor_1: float,
    rev_anchor_2: float,
    eps_anchor_1: float | None,
    eps_anchor_2: float | None,
    revenue0: float,
    book_value_total0: float,
    cost_of_equity: float,
    terminal_growth: float,
    terminal_clip_buffer: float,
    terminal_blend_weight: float,
    long_run_roe: float,
    long_run_payout: float,
    payout_start: float,
    buyback_rate: float,
    net_margin_steady: float,
    net_margin_p10: float,
    net_margin_p90: float,
) -> RiScenarioResult:
    warnings: list[str] = []
    if rev_anchor_1 <= 0 or rev_anchor_2 <= 0:
        warnings.append("ri:missing_rev_anchor")
        return RiScenarioResult(
            scenario_key=scenario_key,
            fair_value=None,
            upside=None,
            equity_value=None,
            pv_residual_stream=None,
            tv_gordon=None,
            tv_fade=None,
            tv_blended=None,
            tv_pv_share=None,
            cost_of_equity=cost_of_equity,
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

    net_margin_targets: list[float] = []
    for idx in range(min(2, explicit_years)):
        eps_anchor = eps_anchor_1 if idx == 0 else eps_anchor_2
        if eps_anchor is None:
            net_margin_targets.append(net_margin_steady)
            warnings.append("ri:missing_eps_anchor")
            continue
        ni_anchor = eps_anchor * shares_path[idx]
        margin = _safe_div(ni_anchor, revenues[idx])
        if margin is None:
            net_margin_targets.append(net_margin_steady)
            warnings.append("ri:missing_eps_anchor")
            continue
        net_margin_targets.append(_clamp(margin, net_margin_p10, net_margin_p90))

    if not net_margin_targets:
        net_margin_targets.append(net_margin_steady)
    net_margins: list[float] = []
    for year_idx in range(1, explicit_years + 1):
        if year_idx <= len(net_margin_targets):
            net_margins.append(net_margin_targets[year_idx - 1])
            continue
        start_margin = net_margin_targets[-1]
        net_margins.append(_fade(start_margin, net_margin_steady, year_idx - 2, max(1, explicit_years - 2)))

    bv_prev = book_value_total0
    pv_residual = 0.0
    forecast_rows: list[dict[str, Any]] = []
    rev_fit_values: list[float] = []
    eps_fit_values: list[float] = []
    clean_surplus_max_abs = 0.0
    ratio_violations = 0
    last_ri = 0.0
    last_roe = long_run_roe

    for idx in range(explicit_years):
        year_no = idx + 1
        revenue_t = revenues[idx]
        net_margin_t = net_margins[idx]
        payout_t = _fade(payout_start, long_run_payout, idx, max(1, explicit_years - 1))
        payout_t = _clamp(payout_t, 0.0, 0.95)

        ni_t = revenue_t * net_margin_t
        div_t = payout_t * ni_t
        bv_t = bv_prev + ni_t - div_t
        ri_t = ni_t - cost_of_equity * bv_prev
        pv_residual += ri_t / ((1.0 + cost_of_equity) ** year_no)

        clean_surplus_resid = bv_t - (bv_prev + ni_t - div_t)
        clean_surplus_max_abs = max(clean_surplus_max_abs, abs(clean_surplus_resid))
        if abs(clean_surplus_resid) > 1e-6:
            warnings.append("ri:clean_surplus_violation")

        eps_model_t = _safe_div(ni_t, shares_path[idx])
        eps_anchor_t = eps_anchor_1 if year_no == 1 else (eps_anchor_2 if year_no == 2 else None)
        rev_anchor_t = rev_anchor_1 if year_no == 1 else (rev_anchor_2 if year_no == 2 else None)
        if rev_anchor_t is not None and abs(rev_anchor_t) > 1e-12:
            rev_fit_values.append((revenue_t - rev_anchor_t) / rev_anchor_t)
        if eps_anchor_t is not None and eps_model_t is not None and abs(eps_anchor_t) > 1e-12:
            eps_fit_values.append((eps_model_t - eps_anchor_t) / eps_anchor_t)

        roe_model_t = _safe_div(ni_t, bv_prev)
        if roe_model_t is not None:
            last_roe = roe_model_t
        if net_margin_t < net_margin_p10 - 1e-9 or net_margin_t > net_margin_p90 + 1e-9:
            ratio_violations += 1
        if payout_t < 0 or payout_t > 0.95:
            ratio_violations += 1
        if bv_t <= 0:
            ratio_violations += 1
            warnings.append("ri:negative_book_path")

        forecast_rows.append(
            {
                "year": year_no,
                "revenue": revenue_t,
                "growth": growth[idx] if idx < len(growth) else terminal_growth,
                "shares": shares_path[idx],
                "net_margin": net_margin_t,
                "net_income": ni_t,
                "payout": payout_t,
                "dividends": div_t,
                "book_value_prev": bv_prev,
                "book_value": bv_t,
                "residual_income": ri_t,
                "roe_model": roe_model_t,
                "eps_model": eps_model_t,
                "eps_anchor": eps_anchor_t,
                "clean_surplus_residual": clean_surplus_resid,
            }
        )

        bv_prev = bv_t
        last_ri = ri_t

    g_terminal = min(terminal_growth, cost_of_equity - terminal_clip_buffer)
    g_terminal = _clamp(g_terminal, -0.01, cost_of_equity - terminal_clip_buffer)
    ri_n1 = last_ri * (1.0 + g_terminal)
    tv_gordon = ri_n1 / max(cost_of_equity - g_terminal, 1e-6)

    # Fade-runoff terminal: excess ROE decays linearly to zero.
    pv_fade_0 = 0.0
    bv_fade_prev = bv_prev
    excess_start = (last_roe - cost_of_equity)
    for step in range(1, fade_years_post_horizon + 1):
        decay = max(0.0, 1.0 - step / max(1, fade_years_post_horizon))
        roe_step = cost_of_equity + excess_start * decay
        ni_step = roe_step * bv_fade_prev
        div_step = _clamp(long_run_payout, 0.0, 0.95) * ni_step
        bv_fade = bv_fade_prev + ni_step - div_step
        ri_step = ni_step - cost_of_equity * bv_fade_prev
        pv_fade_0 += ri_step / ((1.0 + cost_of_equity) ** (explicit_years + step))
        bv_fade_prev = bv_fade

    tv_fade_at_n = pv_fade_0 * ((1.0 + cost_of_equity) ** explicit_years)
    tv_blended = terminal_blend_weight * tv_gordon + (1.0 - terminal_blend_weight) * tv_fade_at_n
    pv_tv = tv_blended / ((1.0 + cost_of_equity) ** explicit_years)

    equity_value = book_value_total0 + pv_residual + pv_tv
    fair_value = _safe_div(equity_value, shares0)
    upside = None
    if fair_value is not None and current_price is not None and current_price > 0:
        upside = fair_value / current_price - 1.0

    tv_pv_share = _safe_div(pv_tv, equity_value)
    if tv_pv_share is not None and tv_pv_share > 0.85:
        warnings.append("ri:terminal_dominance_high")

    anchor_diagnostics = {
        "rev_fit_t1": rev_fit_values[0] if len(rev_fit_values) > 0 else None,
        "rev_fit_t2": rev_fit_values[1] if len(rev_fit_values) > 1 else None,
        "eps_fit_t1": eps_fit_values[0] if len(eps_fit_values) > 0 else None,
        "eps_fit_t2": eps_fit_values[1] if len(eps_fit_values) > 1 else None,
        "clean_surplus_max_abs": clean_surplus_max_abs,
        "ratio_violations": ratio_violations,
    }

    return RiScenarioResult(
        scenario_key=scenario_key,
        fair_value=fair_value,
        upside=upside,
        equity_value=equity_value,
        pv_residual_stream=pv_residual,
        tv_gordon=tv_gordon,
        tv_fade=tv_fade_at_n,
        tv_blended=tv_blended,
        tv_pv_share=tv_pv_share,
        cost_of_equity=cost_of_equity,
        terminal_growth=g_terminal,
        warnings=sorted(set(warnings)),
        anchor_diagnostics=anchor_diagnostics,
        forecast=forecast_rows,
    )


def _quality_score(
    *,
    results: list[RiScenarioResult],
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

    base = next((row for row in results if row.scenario_key == "base"), None)
    if base is not None:
        rev_fit = [
            abs(_to_float(base.anchor_diagnostics.get("rev_fit_t1")) or 0.0),
            abs(_to_float(base.anchor_diagnostics.get("rev_fit_t2")) or 0.0),
        ]
        eps_fit = [
            abs(_to_float(base.anchor_diagnostics.get("eps_fit_t1")) or 0.0),
            abs(_to_float(base.anchor_diagnostics.get("eps_fit_t2")) or 0.0),
        ]
        score -= 20.0 * (sum(rev_fit) / len(rev_fit))
        score -= 20.0 * (sum(eps_fit) / len(eps_fit))
        score -= 3.0 * float(_to_float(base.anchor_diagnostics.get("ratio_violations")) or 0.0)
        tv_share = _to_float(base.tv_pv_share)
        if tv_share is not None and tv_share > 0.85:
            score -= min(25.0, (tv_share - 0.85) * 200.0)
        clean_surplus_max_abs = _to_float(base.anchor_diagnostics.get("clean_surplus_max_abs"))
        if clean_surplus_max_abs is not None and clean_surplus_max_abs > 1e-4:
            score -= 8.0

    if not quality_penalty_enabled:
        return _clamp(score, 0.0, 100.0)
    return _clamp(score, 0.0, 100.0)


def compute_ri_fair_value(
    *,
    symbol: str,
    current_price: float | None,
    book_value_per_share: float | None,
    roe: float | None,
    beta: float | None,
    assumptions: dict,
    forward_estimates: Mapping[str, float | int | None] | None = None,
    statement_inputs: Mapping[str, Any] | None = None,
    ratio_inputs: Mapping[str, Any] | None = None,
    shares_outstanding: float | None = None,
) -> tuple[float | None, float | None, float | None, float | None, list[str], dict[str, Any]]:
    warnings: list[str] = []
    if book_value_per_share is None or book_value_per_share <= 0:
        warnings.append("ri:missing_book_value")
        return None, None, None, None, warnings, {"model_version": "ri_v2_clean_surplus"}

    ri_cfg = assumptions.get("ri", {})
    dcf_cfg = assumptions.get("dcf", {})
    forward = forward_estimates or {}
    statements = statement_inputs or {}
    ratios = ratio_inputs or {}

    explicit_years = int(_clamp(float(ri_cfg.get("explicit_years", 7)), 5, 10))
    anchor_mode = str(ri_cfg.get("anchor_mode", "revenue_eps_consistency"))
    terminal_method = str(ri_cfg.get("terminal_method", "blended"))
    terminal_blend_weight = _clamp(float(ri_cfg.get("terminal_blend_weight", 0.65)), 0.0, 1.0)
    steady_state_growth = float(ri_cfg.get("steady_state_growth", 0.025))
    long_run_roe = _clamp(float(ri_cfg.get("long_run_roe", 0.12)), 0.0, 0.6)
    long_run_payout = _clamp(float(ri_cfg.get("long_run_payout", 0.35)), 0.0, 0.95)
    payout_smoothing_weight = _clamp(float(ri_cfg.get("payout_smoothing_weight", 0.60)), 0.0, 1.0)
    fade_years_post_horizon = int(_clamp(float(ri_cfg.get("fade_years_post_horizon", 8)), 3, 15))
    fallback_rev_spread = _clamp(float(ri_cfg.get("fallback_rev_spread", 0.10)), 0.01, 1.0)
    fallback_eps_spread = _clamp(float(ri_cfg.get("fallback_eps_spread", 0.15)), 0.01, 1.0)
    terminal_clip_buffer = _clamp(float(ri_cfg.get("terminal_clip_buffer", 0.02)), 0.0, 0.1)
    quality_penalty_enabled = bool(ri_cfg.get("quality_penalty_enabled", True))

    rf = float(dcf_cfg.get("rf", 0.02))
    erp = float(dcf_cfg.get("erp", 0.05))
    beta_used = float(beta if beta is not None else 1.0)
    cost_of_equity = _to_float(ri_cfg.get("cost_of_equity"))
    if cost_of_equity is None:
        cost_of_equity = rf + beta_used * erp
    cost_of_equity = _clamp(float(cost_of_equity), 0.06, 0.18)

    shares0 = _to_float(shares_outstanding)
    if shares0 is None or shares0 <= 0:
        shares0 = _to_float(statements.get("diluted_shares_latest"))
    if shares0 is None or shares0 <= 0:
        warnings.append("ri:shares_unavailable")
        return None, None, None, None, warnings, {"model_version": "ri_v2_clean_surplus"}

    book_value_total0 = float(book_value_per_share) * shares0

    revenue_latest = _to_float(statements.get("revenue_latest"))
    revenue_prev = _to_float(statements.get("revenue_prev"))
    growth_proxy = _to_float(statements.get("growth_proxy"))
    if growth_proxy is None:
        growth_proxy = _safe_div(
            (revenue_latest - revenue_prev) if revenue_latest is not None and revenue_prev is not None else None,
            revenue_prev,
        )
    if growth_proxy is None:
        growth_proxy = 0.06
    growth_proxy = _clamp(growth_proxy, -0.3, 0.6)
    if revenue_latest is None or revenue_latest <= 0:
        warnings.append("ri:revenue_base_unavailable")
        return None, None, None, None, warnings, {"model_version": "ri_v2_clean_surplus"}
    revenue0 = revenue_latest / max(1e-6, 1.0 + growth_proxy)

    net_margin_history_raw = statements.get("net_margin_history") or []
    net_margin_history = [_to_float(v) for v in net_margin_history_raw]
    net_margin_history = [v for v in net_margin_history if v is not None]
    net_margin_steady = _median(net_margin_history, _to_float(ratios.get("net_margin")) or 0.10)
    net_margin_p10 = (
        _pct(net_margin_history, 0.10)
        if net_margin_history
        else _clamp(net_margin_steady - 0.04, -0.25, 0.7)
    )
    net_margin_p90 = (
        _pct(net_margin_history, 0.90)
        if net_margin_history
        else _clamp(net_margin_steady + 0.04, -0.25, 0.8)
    )
    if len(net_margin_history) < 3:
        warnings.append("ri:low_statement_history")

    payout_hist = _to_float(ratios.get("payout_ratio"))
    if payout_hist is None:
        payout_hist = long_run_payout
    payout_start = _clamp(
        payout_smoothing_weight * payout_hist + (1.0 - payout_smoothing_weight) * long_run_payout,
        0.0,
        0.95,
    )

    shares_prev = _to_float(statements.get("diluted_shares_prev"))
    buyback_rate = 0.0
    if shares_prev is not None and shares_prev > 0:
        buyback_rate = _clamp((shares_prev - shares0) / shares_prev, -0.05, 0.10)

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

    diluted_eps_latest = _to_float(statements.get("diluted_eps_latest"))
    roe_base = _to_float(roe)
    if roe_base is None:
        roe_base = _to_float(ratios.get("roe"))
    if roe_base is None:
        roe_base = long_run_roe

    if rev_avg_1 is None:
        rev_avg_1 = revenue_latest * (1.0 + growth_proxy)
        warnings.append("ri:missing_rev_anchor")
    if rev_avg_2 is None:
        rev_avg_2 = rev_avg_1 * (1.0 + growth_proxy * 0.8)
        warnings.append("ri:missing_rev_anchor")

    if eps_avg_1 is None:
        if diluted_eps_latest is not None:
            eps_avg_1 = diluted_eps_latest * (1.0 + growth_proxy * 0.5)
        elif current_price is not None and book_value_per_share > 0:
            eps_avg_1 = roe_base * book_value_per_share
        warnings.append("ri:missing_eps_anchor")
    if eps_avg_2 is None and eps_avg_1 is not None:
        eps_avg_2 = eps_avg_1 * (1.0 + growth_proxy * 0.4)
        warnings.append("ri:missing_eps_anchor")

    if rev_low_1 is None and rev_avg_1 is not None:
        rev_low_1 = rev_avg_1 * (1.0 - fallback_rev_spread)
    if rev_high_1 is None and rev_avg_1 is not None:
        rev_high_1 = rev_avg_1 * (1.0 + fallback_rev_spread)
    if rev_low_2 is None and rev_avg_2 is not None:
        rev_low_2 = rev_avg_2 * (1.0 - fallback_rev_spread)
    if rev_high_2 is None and rev_avg_2 is not None:
        rev_high_2 = rev_avg_2 * (1.0 + fallback_rev_spread)
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
    anchor_growth = _safe_div(
        (rev_avg_2 - rev_avg_1) if rev_avg_1 is not None and rev_avg_2 is not None else None,
        rev_avg_1,
    )
    g_sustainable = long_run_roe * max(0.0, 1.0 - long_run_payout)
    growth_candidates: list[float] = [_clamp(steady_state_growth, -0.01, 0.10)]
    growth_candidates.append(_clamp(growth_proxy * 0.35, -0.01, 0.10))
    growth_candidates.append(_clamp(g_sustainable * 0.30, -0.01, 0.10))
    if anchor_growth is not None:
        growth_candidates.append(_clamp(anchor_growth * 0.35, -0.01, 0.10))
    terminal_growth_raw = _clamp(_median(growth_candidates, steady_state_growth), -0.01, 0.08)
    terminal_growth_ceiling = cost_of_equity - terminal_clip_buffer
    if terminal_growth_ceiling <= -0.01:
        warnings.append("ri:terminal_clip_buffer_too_large")
        terminal_growth_ceiling = max(-0.005, cost_of_equity - 0.005)
    terminal_growth = _clamp(min(terminal_growth_raw, g_sustainable), -0.01, terminal_growth_ceiling)
    if terminal_growth >= cost_of_equity:
        terminal_growth = cost_of_equity - 0.001

    scenario_definitions = {
        "base": {
            "rev1": _scenario_anchor(
                scenario="base",
                avg=rev_avg_1,
                low=rev_low_1,
                high=rev_high_1,
                fallback_spread=fallback_rev_spread,
            ),
            "rev2": _scenario_anchor(
                scenario="base",
                avg=rev_avg_2,
                low=rev_low_2,
                high=rev_high_2,
                fallback_spread=fallback_rev_spread,
            ),
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
        },
        "bull": {
            "rev1": _scenario_anchor(
                scenario="bull",
                avg=rev_avg_1,
                low=rev_low_1,
                high=rev_high_1,
                fallback_spread=fallback_rev_spread,
            ),
            "rev2": _scenario_anchor(
                scenario="bull",
                avg=rev_avg_2,
                low=rev_low_2,
                high=rev_high_2,
                fallback_spread=fallback_rev_spread,
            ),
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
        },
        "bear": {
            "rev1": _scenario_anchor(
                scenario="bear",
                avg=rev_avg_1,
                low=rev_low_1,
                high=rev_high_1,
                fallback_spread=fallback_rev_spread,
            ),
            "rev2": _scenario_anchor(
                scenario="bear",
                avg=rev_avg_2,
                low=rev_low_2,
                high=rev_high_2,
                fallback_spread=fallback_rev_spread,
            ),
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
        },
    }

    scenario_results: list[RiScenarioResult] = []
    for scenario_key, anchors in scenario_definitions.items():
        result = _run_ri_scenario(
            scenario_key=scenario_key,
            current_price=current_price,
            shares0=shares0,
            explicit_years=explicit_years,
            fade_years_post_horizon=fade_years_post_horizon,
            rev_anchor_1=float(anchors["rev1"]) if anchors["rev1"] is not None else -1.0,
            rev_anchor_2=float(anchors["rev2"]) if anchors["rev2"] is not None else -1.0,
            eps_anchor_1=_to_float(anchors["eps1"]),
            eps_anchor_2=_to_float(anchors["eps2"]),
            revenue0=float(revenue0),
            book_value_total0=book_value_total0,
            cost_of_equity=cost_of_equity,
            terminal_growth=terminal_growth,
            terminal_clip_buffer=terminal_clip_buffer,
            terminal_blend_weight=terminal_blend_weight,
            long_run_roe=long_run_roe,
            long_run_payout=long_run_payout,
            payout_start=payout_start,
            buyback_rate=buyback_rate,
            net_margin_steady=net_margin_steady,
            net_margin_p10=net_margin_p10,
            net_margin_p90=net_margin_p90,
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
        results=scenario_results,
        rev_anchor_available=(rev_avg_1 is not None, rev_avg_2 is not None),
        eps_anchor_available=(eps_avg_1 is not None, eps_avg_2 is not None),
        quality_penalty_enabled=quality_penalty_enabled,
    )
    if quality < 60:
        warnings.append("ri:quality_low")

    detail = {
        "model_version": "ri_v2_clean_surplus",
        "quality_score": quality,
        "anchor_mode": anchor_mode,
        "terminal_method": terminal_method,
        "scenario_results": {
            row.scenario_key: {
                "fair_value": row.fair_value,
                "upside": row.upside,
                "equity_value": row.equity_value,
                "pv_residual_stream": row.pv_residual_stream,
                "tv_gordon": row.tv_gordon,
                "tv_fade": row.tv_fade,
                "tv_blended": row.tv_blended,
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
            "rev_fit_t1": base.anchor_diagnostics.get("rev_fit_t1") if base else None,
            "rev_fit_t2": base.anchor_diagnostics.get("rev_fit_t2") if base else None,
            "eps_fit_t1": base.anchor_diagnostics.get("eps_fit_t1") if base else None,
            "eps_fit_t2": base.anchor_diagnostics.get("eps_fit_t2") if base else None,
            "clean_surplus_max_abs": base.anchor_diagnostics.get("clean_surplus_max_abs") if base else None,
            "ratio_violations": base.anchor_diagnostics.get("ratio_violations") if base else None,
        },
        "terminal_summary": {
            "terminal_method": terminal_method,
            "terminal_blend_weight": terminal_blend_weight,
            "terminal_growth_raw": terminal_growth_raw,
            "terminal_growth_ceiling": terminal_growth_ceiling,
            "terminal_clip_buffer": terminal_clip_buffer,
            "base_tv_gordon": base.tv_gordon if base else None,
            "base_tv_fade": base.tv_fade if base else None,
            "base_tv_blended": base.tv_blended if base else None,
            "base_tv_pv_share": base.tv_pv_share if base else None,
        },
        "assumptions_used": {
            "explicit_years": explicit_years,
            "fade_years_post_horizon": fade_years_post_horizon,
            "rf": rf,
            "erp": erp,
            "cost_of_equity": cost_of_equity,
            "steady_state_growth": steady_state_growth,
            "terminal_growth_raw": terminal_growth_raw,
            "terminal_growth_ceiling": terminal_growth_ceiling,
            "terminal_clip_buffer": terminal_clip_buffer,
            "terminal_growth": terminal_growth,
            "long_run_roe": long_run_roe,
            "long_run_payout": long_run_payout,
            "payout_smoothing_weight": payout_smoothing_weight,
            "buyback_rate": buyback_rate,
            "net_margin_steady": net_margin_steady,
            "book_value_total0": book_value_total0,
            "shares0": shares0,
        },
    }
    return fair_value, low, high, upside, sorted(set(warnings)), detail
