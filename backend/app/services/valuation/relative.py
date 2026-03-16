from __future__ import annotations

from collections.abc import Mapping


SECTOR_BASELINES: dict[str, dict[str, float]] = {
    "Technology": {"forward_pe": 28.0, "pb": 7.0, "ev_ebitda": 20.0},
    "Communication Services": {"forward_pe": 24.0, "pb": 5.0, "ev_ebitda": 14.0},
    "Consumer Cyclical": {"forward_pe": 22.0, "pb": 4.0, "ev_ebitda": 13.0},
    "Financial Services": {"forward_pe": 13.0, "pb": 1.6, "ev_ebitda": 10.0},
    "Healthcare": {"forward_pe": 20.0, "pb": 4.5, "ev_ebitda": 15.0},
    "Industrials": {"forward_pe": 19.0, "pb": 3.2, "ev_ebitda": 13.5},
    "Energy": {"forward_pe": 11.0, "pb": 1.8, "ev_ebitda": 6.5},
    "Utilities": {"forward_pe": 18.0, "pb": 2.0, "ev_ebitda": 11.0},
}

GLOBAL_BASELINE: dict[str, float] = {"forward_pe": 20.0, "pb": 3.5, "ev_ebitda": 12.0}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_relative_fair_value(
    *,
    current_price: float | None,
    sector: str | None,
    metrics: Mapping[str, float | None],
    assumptions: dict,
) -> tuple[float | None, float | None, list[str], dict[str, float]]:
    warnings: list[str] = []
    if current_price is None or current_price <= 0:
        warnings.append("relative: current_price_missing")
        return None, None, warnings, {}

    rel_cfg = assumptions.get("relative", {})
    multiples = list(rel_cfg.get("multiples", ["forward_pe", "pb", "ev_ebitda"]))
    cap_upside = float(rel_cfg.get("cap_upside", 0.6))
    cap_upside = _clamp(cap_upside, 0.0, 2.0)

    baseline = SECTOR_BASELINES.get(sector or "", GLOBAL_BASELINE)
    if baseline is GLOBAL_BASELINE:
        warnings.append("relative: sector_baseline_missing_using_global")

    ratios: list[float] = []
    used: dict[str, float] = {}
    for multiple in multiples:
        company_value = metrics.get(multiple)
        baseline_value = baseline.get(multiple) if isinstance(baseline, dict) else None
        if company_value is None or baseline_value is None or company_value <= 0 or baseline_value <= 0:
            continue
        ratio = baseline_value / company_value
        ratios.append(ratio)
        used[multiple] = ratio

    if not ratios:
        warnings.append("relative: insufficient_multiple_data")
        return None, None, warnings, {}

    fair_multiplier = sum(ratios) / len(ratios)
    implied_upside = _clamp(fair_multiplier - 1.0, -cap_upside, cap_upside)
    fair_value = current_price * (1.0 + implied_upside)
    return float(fair_value), float(implied_upside), warnings, used

