from __future__ import annotations


BASE_WEIGHTS = {
    "analyst": 0.35,
    "dcf": 0.25,
    "ri": 0.25,
    "relative": 0.15,
}


def combine_valuation_models(
    *,
    current_price: float | None,
    analyst_upside: float | None,
    dcf_fair_value: float | None,
    ri_fair_value: float | None,
    relative_fair_value: float | None,
) -> tuple[float | None, float | None, float | None, float | None, str, list[str]]:
    warnings: list[str] = []
    if current_price is None or current_price <= 0:
        warnings.append("composite: current_price_missing")
        return None, None, None, None, "partial", warnings

    fair_values: dict[str, float] = {}
    if analyst_upside is not None:
        fair_values["analyst"] = current_price * (1.0 + analyst_upside)
    if dcf_fair_value is not None and dcf_fair_value > 0:
        fair_values["dcf"] = dcf_fair_value
    if ri_fair_value is not None and ri_fair_value > 0:
        fair_values["ri"] = ri_fair_value
    if relative_fair_value is not None and relative_fair_value > 0:
        fair_values["relative"] = relative_fair_value

    if not fair_values:
        warnings.append("composite: no_available_models")
        return None, None, None, None, "partial", warnings

    total_weight = sum(BASE_WEIGHTS[k] for k in fair_values.keys())
    composite = sum(fair_values[k] * (BASE_WEIGHTS[k] / total_weight) for k in fair_values.keys())
    upside = composite / current_price - 1.0

    values = list(fair_values.values())
    if len(values) == 1:
        confidence_low = values[0] * 0.95
        confidence_high = values[0] * 1.05
    else:
        confidence_low = min(values)
        confidence_high = max(values)

    status = "full" if len(fair_values) >= 3 else "partial"
    if status == "partial":
        warnings.append("composite: partial_model_coverage")

    return (
        float(composite),
        float(upside),
        float(confidence_low),
        float(confidence_high),
        status,
        warnings,
    )

