from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HoldingsPosition, HoldingsSnapshot, PortfolioNarrativeSnapshot


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _chip(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value}


def build_narrative_payload(
    *,
    positions: list[HoldingsPosition],
    exposure_summary: dict[str, Any] | None,
    metrics: Any | None,
    valuation_summary: Any | None,
    latest_scenario: Any | None,
    previous_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    exposure_summary = exposure_summary or {}
    cards: list[dict[str, Any]] = []
    watchouts: list[dict[str, Any]] = []
    warnings: list[str] = list(exposure_summary.get("warnings", []))
    breakdowns = exposure_summary.get("breakdowns", {})
    concentration_signals = exposure_summary.get("concentration_signals", [])
    top_sector = (breakdowns.get("sector") or [{}])[0]
    top_currency = (breakdowns.get("currency") or [{}])[0]
    top_overlap = (exposure_summary.get("overlap_pairs") or [None])[0]
    top_holdings = exposure_summary.get("top_lookthrough_holdings") or []

    top3_weight = _safe_float(getattr(metrics, "top3_weight_share", None))
    if top3_weight is None:
        top3_weight = sum(float(position.weight) for position in sorted(positions, key=lambda row: float(row.weight), reverse=True)[:3])
    if top3_weight is not None:
        cards.append(
            {
                "id": "concentration",
                "title": "Portfolio concentration",
                "tone": "negative" if top3_weight >= 0.5 else "neutral",
                "summary": f"The top three positions still drive {top3_weight * 100:.1f}% of direct weight, so single-name moves can dominate results.",
                "evidence_chips": [_chip("Top 3", f"{top3_weight * 100:.1f}%"), _chip("Holdings", str(len(positions)))],
            }
        )

    if top_sector:
        lookthrough_weight_pct = _safe_float(top_sector.get("lookthrough_weight_pct")) or 0.0
        cards.append(
            {
                "id": "sector-crowding",
                "title": "Look-through sector tilt",
                "tone": "negative" if lookthrough_weight_pct >= 35 else "positive",
                "summary": f"{top_sector.get('label', 'Unknown')} is the largest look-through sector at {lookthrough_weight_pct:.1f}%, so sector shocks will likely transmit across multiple holdings.",
                "evidence_chips": [_chip("Top sector", str(top_sector.get("label", "Unknown"))), _chip("Look-through", f"{lookthrough_weight_pct:.1f}%")],
            }
        )

    if top_overlap:
        overlap_pct = (_safe_float(top_overlap.get("overlap_weight")) or 0.0) * 100.0
        cards.append(
            {
                "id": "overlap",
                "title": "False diversification check",
                "tone": "negative" if overlap_pct >= 8 else "neutral",
                "summary": f"{top_overlap.get('left_symbol')} and {top_overlap.get('right_symbol')} share {overlap_pct:.1f}% look-through exposure, so diversification is lower than line-item counts suggest.",
                "evidence_chips": [_chip("Pair", f"{top_overlap.get('left_symbol')}/{top_overlap.get('right_symbol')}"), _chip("Shared weight", f"{overlap_pct:.1f}%")],
            }
        )

    coverage_ratio = _safe_float(getattr(valuation_summary, "coverage_ratio", None))
    composite_upside = _safe_float(getattr(valuation_summary, "weighted_composite_upside", None))
    if coverage_ratio is not None:
        cards.append(
            {
                "id": "valuation",
                "title": "Valuation usability",
                "tone": "positive" if coverage_ratio >= 0.65 else "neutral",
                "summary": (
                    f"Valuation coverage spans {coverage_ratio * 100:.1f}% of portfolio weight"
                    + (f", with weighted composite upside of {composite_upside * 100:.1f}%." if composite_upside is not None else ".")
                ),
                "evidence_chips": [_chip("Coverage", f"{coverage_ratio * 100:.1f}%"), _chip("Composite", "N/A" if composite_upside is None else f"{composite_upside * 100:.1f}%")],
            }
        )
        if coverage_ratio < 0.5:
            watchouts.append({"level": "medium", "title": "Partial valuation coverage", "detail": "Large parts of the portfolio still rely on partial valuation evidence, so upside signals should be treated as directional."})

    if latest_scenario is not None:
        cards.append(
            {
                "id": "scenario",
                "title": "Latest macro stress anchor",
                "tone": "positive" if str(getattr(latest_scenario, "status", "")) == "completed" else "neutral",
                "summary": f"The last saved macro run stressed {getattr(latest_scenario, 'factor_key', 'scenario')} by {getattr(latest_scenario, 'shock_value', 0):+g} {getattr(latest_scenario, 'shock_unit', '')} over {getattr(latest_scenario, 'horizon_days', 0)} days.",
                "evidence_chips": [_chip("Status", str(getattr(latest_scenario, "status", "unknown"))), _chip("Horizon", f"{getattr(latest_scenario, 'horizon_days', 0)}d")],
            }
        )
    else:
        watchouts.append({"level": "medium", "title": "Scenario workflow not used", "detail": "No saved scenario run exists for the latest holdings snapshot, so the portfolio has not been stress-tested end to end."})

    if top_currency:
        currency_pct = _safe_float(top_currency.get("lookthrough_weight_pct")) or 0.0
        if currency_pct >= 75:
            watchouts.append({"level": "medium", "title": "Currency dependence", "detail": f"{top_currency.get('label', 'Unknown')} still represents {currency_pct:.1f}% of look-through exposure."})

    for signal in concentration_signals[:3]:
        watchouts.append(
            {
                "level": signal.get("severity", "info"),
                "title": str(signal.get("signal_key", "signal")).replace("_", " ").title(),
                "detail": str(signal.get("summary", "")),
            }
        )

    previous_top_sector = None
    previous_top3 = None
    if previous_payload:
        prev_sector = ((previous_payload.get("exposure_summary") or {}).get("breakdowns", {}).get("sector") or [{}])[0]
        previous_top_sector = _safe_float(prev_sector.get("lookthrough_weight"))
        previous_top3 = _safe_float((previous_payload.get("change_summary") or {}).get("prior_top3_weight"))
        if previous_top3 is None:
            previous_top3 = _safe_float(((previous_payload.get("cards") or [{}])[0].get("evidence_chips") or [{}, {}])[0].get("value", "").rstrip("%"))
            if previous_top3 is not None:
                previous_top3 = previous_top3 / 100.0

    current_sector_weight = _safe_float(top_sector.get("lookthrough_weight"))
    change_bits: list[str] = []
    if previous_top3 is not None and top3_weight is not None:
        delta = (top3_weight - previous_top3) * 100.0
        if abs(delta) >= 1.0:
            change_bits.append(f"top-3 concentration {'rose' if delta > 0 else 'fell'} by {abs(delta):.1f} pts")
    if previous_top_sector is not None and current_sector_weight is not None:
        delta_sector = (current_sector_weight - previous_top_sector) * 100.0
        if abs(delta_sector) >= 1.0:
            change_bits.append(f"lead sector exposure {'rose' if delta_sector > 0 else 'fell'} by {abs(delta_sector):.1f} pts")

    change_summary = {
        "headline": "No prior narrative snapshot available." if not change_bits else "; ".join(change_bits).capitalize() + ".",
        "prior_top3_weight": previous_top3,
    }

    return {
        "status": "ok" if cards else "no_data",
        "cards": cards[:5],
        "watchouts": watchouts[:5],
        "change_summary": change_summary,
        "evidence_chips": [_chip("Top look-through name", str(top_holdings[0]["symbol"]))] if top_holdings else [],
        "warnings": sorted(set(warnings)),
        "exposure_summary": exposure_summary,
    }


def persist_portfolio_narrative(
    db: Session,
    *,
    portfolio_id: int,
    snapshot: HoldingsSnapshot,
    payload: dict[str, Any],
) -> PortfolioNarrativeSnapshot:
    today = date.today()
    row = db.scalar(
        select(PortfolioNarrativeSnapshot)
        .where(PortfolioNarrativeSnapshot.portfolio_id == portfolio_id)
        .where(PortfolioNarrativeSnapshot.snapshot_id == snapshot.id)
        .where(PortfolioNarrativeSnapshot.as_of_date == today)
        .limit(1)
    )
    if row is None:
        row = PortfolioNarrativeSnapshot(portfolio_id=portfolio_id, snapshot_id=snapshot.id, as_of_date=today)
        db.add(row)
    row.summary_json = _json_dumps(payload)
    row.warnings_json = _json_dumps(sorted(set(payload.get("warnings", []))))
    db.flush()
    return row


def latest_narrative_snapshot(db: Session, portfolio_id: int, *, snapshot_id: int | None = None) -> PortfolioNarrativeSnapshot | None:
    query = select(PortfolioNarrativeSnapshot).where(PortfolioNarrativeSnapshot.portfolio_id == portfolio_id)
    if snapshot_id is not None:
        query = query.where(PortfolioNarrativeSnapshot.snapshot_id == snapshot_id)
    return db.scalar(query.order_by(PortfolioNarrativeSnapshot.as_of_date.desc(), PortfolioNarrativeSnapshot.id.desc()).limit(1))


def previous_narrative_payload(db: Session, portfolio_id: int, *, exclude_snapshot_id: int) -> dict[str, Any] | None:
    row = db.scalar(
        select(PortfolioNarrativeSnapshot)
        .where(PortfolioNarrativeSnapshot.portfolio_id == portfolio_id)
        .where(PortfolioNarrativeSnapshot.snapshot_id != exclude_snapshot_id)
        .order_by(PortfolioNarrativeSnapshot.as_of_date.desc(), PortfolioNarrativeSnapshot.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    return _json_loads(row.summary_json, {})


def narrative_payload(row: PortfolioNarrativeSnapshot | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = _json_loads(row.summary_json, {})
    payload.setdefault("warnings", _json_loads(row.warnings_json, []))
    return payload
