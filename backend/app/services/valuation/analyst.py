from __future__ import annotations


def compute_analyst_upside(
    *,
    current_price: float | None,
    target_mean: float | None,
) -> tuple[float | None, str, list[str]]:
    warnings: list[str] = []
    if current_price is None or current_price <= 0:
        warnings.append("analyst: current_price_missing")
        return None, "partial", warnings
    if target_mean is None or target_mean <= 0:
        warnings.append("analyst: target_mean_missing")
        return None, "partial", warnings
    upside = target_mean / current_price - 1.0
    return float(upside), "full", warnings

