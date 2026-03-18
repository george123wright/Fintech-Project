from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScenarioTemplate:
    key: str
    display_name: str
    factor_key: str
    shock_value: float
    shock_unit: str
    horizon_days: int
    confidence_level: float
    n_sims: int
    narrative: str
    objective: str


TEMPLATES: list[ScenarioTemplate] = [
    ScenarioTemplate("fomc_plus_25", "FOMC: Rates +25 bps", "rates", 25.0, "bps", 21, 0.95, 1200, "Tests whether equity and duration holdings can absorb a standard hawkish Fed surprise.", "Policy tightening"),
    ScenarioTemplate("rates_plus_100", "Rates +100 bps", "rates", 100.0, "bps", 63, 0.95, 1200, "Stresses a sharper repricing in discount rates and long-duration assets.", "Rates shock"),
    ScenarioTemplate("inflation_surprise", "Inflation surprise", "inflation", 0.7, "%", 63, 0.95, 1200, "Checks whether inflation-sensitive sectors and duration exposure become dominant.", "Inflation shock"),
    ScenarioTemplate("growth_slowdown", "GDP slowdown", "gdp", -1.0, "%", 126, 0.95, 1200, "Frames a recession-lite slowdown using GDP growth as the macro driver.", "Growth risk"),
    ScenarioTemplate("retail_drawdown", "Retail spending drawdown", "retail_spending", -2.0, "%", 63, 0.95, 1200, "Useful when discretionary and consumer exposure looks crowded.", "Consumer demand"),
    ScenarioTemplate("oil_spike", "Oil spike", "oil", 12.0, "%", 21, 0.95, 1200, "Tests inflation pass-through and cyclicals sensitivity during a commodity spike.", "Commodity shock"),
    ScenarioTemplate("vix_spike", "VIX spike", "vix", 25.0, "%", 10, 0.99, 1600, "Examines near-term downside if volatility rapidly mean-reverts higher.", "Volatility shock"),
]


def scenario_templates_payload() -> list[dict[str, Any]]:
    return [template.__dict__.copy() for template in TEMPLATES]


def guided_macro_workflow_payload() -> dict[str, Any]:
    steps = [
        {"step_key": "diagnose", "title": "Diagnose current crowding", "detail": "Start with exposure concentration and overlap to see where false diversification is present."},
        {"step_key": "select", "title": "Select a macro lens", "detail": "Choose the preset whose economic question best matches the portfolio's current crowding."},
        {"step_key": "stress", "title": "Run baseline then shock", "detail": "Preview the scenario first, then save the run once the shocked path and tails make sense."},
        {"step_key": "explain", "title": "Explain what changed", "detail": "Compare scenario narratives, valuation coverage, and concentration watchouts to form the macro review."},
    ]
    return {"workflow_key": "guided_macro_v1", "title": "Guided Macro Workflow", "description": "A deterministic macro workflow that walks from exposure diagnosis to a saved stress test.", "steps": steps, "templates": scenario_templates_payload()}
