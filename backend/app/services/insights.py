from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import HoldingsPosition, SecurityFundamentalSnapshot


@dataclass
class EnrichedHolding:
    symbol: str
    name: str | None
    weight: float
    market_value: float
    currency: str
    asset_type: str | None
    sector: str | None
    industry: str | None


def _clean_label(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    return raw if raw else fallback


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return float(number)


def _bucketize(weights: dict[str, float], *, limit: int = 6) -> list[dict[str, Any]]:
    ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return []

    head = ranked[:limit]
    tail = ranked[limit:]
    if tail:
        other_weight = sum(weight for _, weight in tail)
        head.append(("Other", other_weight))

    return [
        {
            "label": label,
            "weight": float(weight),
            "weight_pct": float(weight * 100.0),
        }
        for label, weight in head
    ]


def load_latest_fundamentals(db: Session, symbols: list[str]) -> dict[str, SecurityFundamentalSnapshot]:
    out: dict[str, SecurityFundamentalSnapshot] = {}
    for symbol in sorted({sym.strip().upper() for sym in symbols if sym and sym.strip()}):
        snapshot = db.scalar(
            select(SecurityFundamentalSnapshot)
            .where(SecurityFundamentalSnapshot.symbol == symbol)
            .order_by(desc(SecurityFundamentalSnapshot.as_of_date), desc(SecurityFundamentalSnapshot.fetched_at))
            .limit(1)
        )
        if snapshot is not None:
            out[symbol] = snapshot
    return out


def enrich_holdings(
    positions: list[HoldingsPosition],
    fundamentals_by_symbol: dict[str, SecurityFundamentalSnapshot] | None = None,
) -> list[EnrichedHolding]:
    fundamentals_by_symbol = fundamentals_by_symbol or {}
    enriched: list[EnrichedHolding] = []
    for position in positions:
        symbol = str(position.symbol).upper()
        snap = fundamentals_by_symbol.get(symbol)
        enriched.append(
            EnrichedHolding(
                symbol=symbol,
                name=position.name,
                weight=float(position.weight),
                market_value=float(position.market_value),
                currency=_clean_label(position.currency, "Unknown"),
                asset_type=_clean_label(position.asset_type, "Unclassified"),
                sector=_clean_label(getattr(snap, "sector", None), "Unknown sector"),
                industry=_clean_label(getattr(snap, "industry", None), "Unknown industry"),
            )
        )
    return enriched


def build_portfolio_exposure_summary(
    positions: list[HoldingsPosition],
    *,
    fundamentals_by_symbol: dict[str, SecurityFundamentalSnapshot] | None = None,
    metrics: Any | None = None,
) -> dict[str, Any]:
    enriched = enrich_holdings(positions, fundamentals_by_symbol)
    if not enriched:
        return {
            "asset_type": [],
            "currency": [],
            "sector": [],
            "top_holdings": [],
            "concentration_flags": [],
            "coverage": {"sector_weight_covered": 0.0, "sector_weight_covered_pct": 0.0, "holding_count": 0},
        }

    asset_type_weights: dict[str, float] = {}
    currency_weights: dict[str, float] = {}
    sector_weights: dict[str, float] = {}
    sector_covered_weight = 0.0

    for holding in enriched:
        asset_type_weights[holding.asset_type] = asset_type_weights.get(holding.asset_type, 0.0) + holding.weight
        currency_weights[holding.currency] = currency_weights.get(holding.currency, 0.0) + holding.weight
        sector_weights[holding.sector] = sector_weights.get(holding.sector, 0.0) + holding.weight
        if holding.sector != "Unknown sector":
            sector_covered_weight += holding.weight

    sorted_holdings = sorted(enriched, key=lambda item: (-item.weight, item.symbol))
    top_holdings = [
        {
            "symbol": item.symbol,
            "name": item.name,
            "weight": item.weight,
            "weight_pct": item.weight * 100.0,
            "market_value": item.market_value,
            "sector": item.sector,
            "currency": item.currency,
            "asset_type": item.asset_type,
        }
        for item in sorted_holdings[:5]
    ]

    hhi = _as_float(getattr(metrics, "hhi", None))
    if hhi is None:
        hhi = sum(item.weight**2 for item in enriched)
    top3_weight = _as_float(getattr(metrics, "top3_weight_share", None))
    if top3_weight is None:
        top3_weight = sum(item.weight for item in sorted_holdings[:3])

    sorted_sectors = sorted(sector_weights.items(), key=lambda item: (-item[1], item[0]))
    sorted_currencies = sorted(currency_weights.items(), key=lambda item: (-item[1], item[0]))
    top_sector_label, top_sector_weight = sorted_sectors[0]
    top_ccy_label, top_ccy_weight = sorted_currencies[0]

    concentration_flags: list[dict[str, Any]] = []
    if top3_weight >= 0.5:
        concentration_flags.append(
            {
                "level": "high",
                "title": "Top holdings concentration",
                "detail": f"Top three positions account for {top3_weight * 100:.1f}% of portfolio weight.",
            }
        )
    elif top3_weight >= 0.35:
        concentration_flags.append(
            {
                "level": "medium",
                "title": "Top holdings concentration",
                "detail": f"Top three positions account for {top3_weight * 100:.1f}% of portfolio weight.",
            }
        )

    if top_sector_weight >= 0.35:
        concentration_flags.append(
            {
                "level": "high" if top_sector_weight >= 0.45 else "medium",
                "title": "Sector crowding",
                "detail": f"{top_sector_label} represents {top_sector_weight * 100:.1f}% of the portfolio.",
            }
        )

    if top_ccy_weight >= 0.75:
        concentration_flags.append(
            {
                "level": "medium" if top_ccy_weight < 0.9 else "high",
                "title": "Currency dependence",
                "detail": f"{top_ccy_label} accounts for {top_ccy_weight * 100:.1f}% of portfolio weight.",
            }
        )

    if hhi >= 0.18:
        concentration_flags.append(
            {
                "level": "medium" if hhi < 0.25 else "high",
                "title": "Portfolio concentration score",
                "detail": f"HHI concentration score is {hhi:.3f}; higher values imply less diversification.",
            }
        )

    return {
        "asset_type": _bucketize(asset_type_weights),
        "currency": _bucketize(currency_weights),
        "sector": _bucketize(sector_weights),
        "top_holdings": top_holdings,
        "concentration_flags": concentration_flags,
        "coverage": {
            "sector_weight_covered": float(sector_covered_weight),
            "sector_weight_covered_pct": float(sector_covered_weight * 100.0),
            "holding_count": len(enriched),
        },
    }


def _evidence_chip(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value}


def build_portfolio_narrative(
    *,
    positions: list[HoldingsPosition],
    exposure_summary: dict[str, Any],
    metrics: Any | None = None,
    valuation_summary: Any | None = None,
    latest_scenario: Any | None = None,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    warnings: list[str] = []
    top_flags = exposure_summary.get("concentration_flags", [])
    sectors = exposure_summary.get("sector", [])
    currencies = exposure_summary.get("currency", [])

    top3_weight = _as_float(getattr(metrics, "top3_weight_share", None))
    if top3_weight is None and positions:
        top3_weight = sum(
            float(position.weight)
            for position in sorted(positions, key=lambda row: float(row.weight), reverse=True)[:3]
        )
    if top3_weight is not None:
        tone = "negative" if top3_weight >= 0.5 else "neutral"
        cards.append(
            {
                "id": "concentration",
                "title": "Concentration check",
                "tone": tone,
                "summary": (
                    f"The top three holdings make up {top3_weight * 100:.1f}% of total portfolio weight, "
                    "so single-name moves can still dominate overall results."
                ),
                "evidence_chips": [
                    _evidence_chip("Top 3 weight", f"{top3_weight * 100:.1f}%"),
                    _evidence_chip("Holdings", str(len(positions))),
                ],
            }
        )

    if sectors:
        lead = sectors[0]
        cards.append(
            {
                "id": "sector",
                "title": "Sector tilt",
                "tone": "negative" if float(lead["weight"]) >= 0.35 else "positive",
                "summary": (
                    f"{lead['label']} is the largest sector exposure at {lead['weight_pct']:.1f}% of weight, "
                    "which is likely to shape both returns and downside behaviour."
                ),
                "evidence_chips": [
                    _evidence_chip("Top sector", str(lead["label"])),
                    _evidence_chip("Weight", f"{float(lead['weight_pct']):.1f}%"),
                ],
            }
        )

    if currencies:
        lead_ccy = currencies[0]
        cards.append(
            {
                "id": "currency",
                "title": "Currency exposure",
                "tone": "neutral",
                "summary": (
                    f"The portfolio is primarily denominated in {lead_ccy['label']} ({lead_ccy['weight_pct']:.1f}% "
                    "of weight), so FX moves versus the base currency may still matter materially."
                ),
                "evidence_chips": [
                    _evidence_chip("Top currency", str(lead_ccy["label"])),
                    _evidence_chip("Weight", f"{float(lead_ccy['weight_pct']):.1f}%"),
                ],
            }
        )

    coverage_ratio = _as_float(getattr(valuation_summary, "coverage_ratio", None))
    composite_upside = _as_float(getattr(valuation_summary, "weighted_composite_upside", None))
    if coverage_ratio is not None:
        summary = f"Valuation coverage currently spans {coverage_ratio * 100:.1f}% of portfolio weight"
        if composite_upside is not None:
            summary += f", with weighted composite upside of {composite_upside * 100:.1f}%"
        summary += "."
        cards.append(
            {
                "id": "valuation",
                "title": "Valuation coverage",
                "tone": "positive" if coverage_ratio >= 0.6 else "neutral",
                "summary": summary,
                "evidence_chips": [
                    _evidence_chip("Coverage", f"{coverage_ratio * 100:.1f}%"),
                    _evidence_chip(
                        "Composite upside",
                        "N/A" if composite_upside is None else f"{composite_upside * 100:.1f}%",
                    ),
                ],
            }
        )
        if coverage_ratio < 0.5:
            warnings.append("valuation_coverage_low")

    if latest_scenario is not None:
        cards.append(
            {
                "id": "scenario",
                "title": "Latest stress run",
                "tone": "positive" if str(getattr(latest_scenario, "status", "")) == "completed" else "neutral",
                "summary": (
                    f"Latest saved scenario: {getattr(latest_scenario, 'factor_key', 'scenario')} "
                    f"{getattr(latest_scenario, 'shock_value', 0):+g} {getattr(latest_scenario, 'shock_unit', '')} "
                    f"over {getattr(latest_scenario, 'horizon_days', 0)} days."
                ),
                "evidence_chips": [
                    _evidence_chip("Status", str(getattr(latest_scenario, "status", "unknown"))),
                    _evidence_chip("Horizon", f"{getattr(latest_scenario, 'horizon_days', 0)}d"),
                ],
            }
        )
    else:
        cards.append(
            {
                "id": "scenario",
                "title": "Scenario readiness",
                "tone": "neutral",
                "summary": (
                    "No saved scenario run is available yet, so macro stress testing has not been anchored to this "
                    "latest portfolio snapshot."
                ),
                "evidence_chips": [_evidence_chip("Saved run", "None")],
            }
        )
        warnings.append("scenario_not_run")

    if top_flags:
        warnings.extend(flag["title"].lower().replace(" ", "_") for flag in top_flags)

    return {
        "status": "ok" if cards else "no_data",
        "cards": cards[:5],
        "warnings": sorted(set(warnings)),
    }
