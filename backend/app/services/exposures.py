from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models import (
    EtfConstituentSnapshot,
    HoldingsPosition,
    HoldingsSnapshot,
    PortfolioConcentrationSignal,
    PortfolioExposureBreakdown,
    PortfolioExposureSnapshot,
    PortfolioOverlapPair,
    SecurityFundamentalSnapshot,
    SecurityMasterSnapshot,
)

METHODOLOGY_VERSION = "exposure_v1"
ETF_HINTS = {"ETF", "FUND", "INDEX", "TRUST"}
LOOKTHROUGH_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "SPY": [
        {"symbol": "MSFT", "name": "Microsoft", "weight": 0.07, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AAPL", "name": "Apple", "weight": 0.065, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.06, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AMZN", "name": "Amazon", "weight": 0.035, "sector": "Consumer Discretionary", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "META", "name": "Meta", "weight": 0.025, "sector": "Communication Services", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
    ],
    "QQQ": [
        {"symbol": "MSFT", "name": "Microsoft", "weight": 0.09, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AAPL", "name": "Apple", "weight": 0.085, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.08, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AMZN", "name": "Amazon", "weight": 0.055, "sector": "Consumer Discretionary", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "META", "name": "Meta", "weight": 0.04, "sector": "Communication Services", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
    ],
    "VTI": [
        {"symbol": "MSFT", "name": "Microsoft", "weight": 0.06, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AAPL", "name": "Apple", "weight": 0.055, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.05, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AMZN", "name": "Amazon", "weight": 0.03, "sector": "Consumer Discretionary", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "GOOGL", "name": "Alphabet", "weight": 0.02, "sector": "Communication Services", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
    ],
    "SMH": [
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.21, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "TSM", "name": "TSMC", "weight": 0.13, "sector": "Technology", "country": "Taiwan", "currency": "TWD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AVGO", "name": "Broadcom", "weight": 0.10, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AMD", "name": "AMD", "weight": 0.07, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Large Cap"},
        {"symbol": "QCOM", "name": "Qualcomm", "weight": 0.05, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Large Cap"},
    ],
    "SOXX": [
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.10, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AVGO", "name": "Broadcom", "weight": 0.09, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Mega Cap"},
        {"symbol": "AMD", "name": "AMD", "weight": 0.08, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Large Cap"},
        {"symbol": "QCOM", "name": "Qualcomm", "weight": 0.07, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Large Cap"},
        {"symbol": "TXN", "name": "Texas Instruments", "weight": 0.06, "sector": "Technology", "country": "United States", "currency": "USD", "market_cap_bucket": "Large Cap"},
    ],
}


@dataclass
class ExposureBuildResult:
    snapshot: PortfolioExposureSnapshot
    warnings: list[str]
    summary: dict[str, Any]


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


def _clean_label(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    return raw if raw else fallback


def _infer_market_cap_bucket(market_cap: float | None) -> str:
    if market_cap is None:
        return "Unknown"
    if market_cap >= 200_000_000_000:
        return "Mega Cap"
    if market_cap >= 10_000_000_000:
        return "Large Cap"
    if market_cap >= 2_000_000_000:
        return "Mid Cap"
    if market_cap >= 300_000_000:
        return "Small Cap"
    return "Micro Cap"


def _is_etf_like(position: HoldingsPosition) -> bool:
    asset_type = (position.asset_type or "").upper()
    name = (position.name or "").upper()
    return any(hint in asset_type for hint in ETF_HINTS) or any(hint in name for hint in ETF_HINTS)


def _load_latest_fundamentals(db: Session, symbols: list[str]) -> dict[str, SecurityFundamentalSnapshot]:
    out: dict[str, SecurityFundamentalSnapshot] = {}
    for symbol in sorted({symbol.upper() for symbol in symbols if symbol}):
        snap = db.scalar(
            select(SecurityFundamentalSnapshot)
            .where(SecurityFundamentalSnapshot.symbol == symbol)
            .order_by(desc(SecurityFundamentalSnapshot.as_of_date), desc(SecurityFundamentalSnapshot.fetched_at))
            .limit(1)
        )
        if snap is not None:
            out[symbol] = snap
    return out


def _upsert_security_master(
    db: Session,
    *,
    symbol: str,
    as_of_date: date,
    position: HoldingsPosition,
    fundamental: SecurityFundamentalSnapshot | None,
) -> SecurityMasterSnapshot:
    row = db.scalar(
        select(SecurityMasterSnapshot)
        .where(SecurityMasterSnapshot.symbol == symbol)
        .where(SecurityMasterSnapshot.as_of_date == as_of_date)
        .limit(1)
    )
    if row is None:
        row = SecurityMasterSnapshot(symbol=symbol, as_of_date=as_of_date)
        db.add(row)
    row.name = position.name
    row.asset_type = position.asset_type
    row.sector = getattr(fundamental, "sector", None)
    row.industry = getattr(fundamental, "industry", None)
    row.country = "United States" if (position.currency or "USD").upper() == "USD" else None
    row.currency = position.currency
    row.market_cap_bucket = _infer_market_cap_bucket(getattr(fundamental, "market_cap", None))
    row.beta = getattr(fundamental, "beta", None) if hasattr(fundamental, "beta") else None
    row.provider_metadata_json = _json_dumps({"has_fundamental_snapshot": fundamental is not None})
    db.flush()
    return row


def _normalize_constituents(symbol: str, position: HoldingsPosition, master: SecurityMasterSnapshot) -> list[dict[str, Any]]:
    registered = LOOKTHROUGH_REGISTRY.get(symbol)
    if registered:
        total = sum(float(item.get("weight", 0.0)) for item in registered)
        if total > 0:
            return [{**item, "weight": float(item.get("weight", 0.0)) / total} for item in registered]
        return registered
    return [
        {
            "symbol": symbol,
            "name": position.name or symbol,
            "weight": 1.0,
            "sector": master.sector or "Unknown sector",
            "country": master.country or ("United States" if (position.currency or "USD").upper() == "USD" else "Unknown country"),
            "currency": position.currency or "USD",
            "market_cap_bucket": master.market_cap_bucket or "Unknown",
        }
    ]


def _bucketize(weights: dict[str, float], direct: dict[str, float], *, limit: int = 6) -> list[dict[str, Any]]:
    ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    head = ranked[:limit]
    tail = ranked[limit:]
    if tail:
        head.append(("Other", sum(weight for _, weight in tail)))
    buckets: list[dict[str, Any]] = []
    for label, lookthrough_weight in head:
        direct_weight = direct.get(label, 0.0)
        buckets.append(
            {
                "label": label,
                "direct_weight": float(direct_weight),
                "lookthrough_weight": float(lookthrough_weight),
                "direct_weight_pct": float(direct_weight * 100.0),
                "lookthrough_weight_pct": float(lookthrough_weight * 100.0),
            }
        )
    return buckets


def build_portfolio_exposure_snapshot(
    db: Session,
    *,
    portfolio_id: int,
    snapshot: HoldingsSnapshot,
    positions: list[HoldingsPosition],
) -> ExposureBuildResult:
    warnings: list[str] = []
    fundamentals = _load_latest_fundamentals(db, [position.symbol for position in positions])
    today = date.today()

    existing = db.scalar(
        select(PortfolioExposureSnapshot)
        .where(PortfolioExposureSnapshot.portfolio_id == portfolio_id)
        .where(PortfolioExposureSnapshot.snapshot_id == snapshot.id)
        .where(PortfolioExposureSnapshot.as_of_date == today)
        .limit(1)
    )
    exposure_snapshot = existing or PortfolioExposureSnapshot(
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        as_of_date=today,
        methodology_version=METHODOLOGY_VERSION,
    )
    if existing is None:
        db.add(exposure_snapshot)
        db.flush()

    db.execute(delete(PortfolioExposureBreakdown).where(PortfolioExposureBreakdown.exposure_snapshot_id == exposure_snapshot.id))
    db.execute(delete(PortfolioOverlapPair).where(PortfolioOverlapPair.exposure_snapshot_id == exposure_snapshot.id))
    db.execute(delete(PortfolioConcentrationSignal).where(PortfolioConcentrationSignal.exposure_snapshot_id == exposure_snapshot.id))

    lookthrough_direct: dict[str, dict[str, float]] = {
        "asset_type": {},
        "currency": {},
        "sector": {},
        "country": {},
        "market_cap_bucket": {},
    }
    lookthrough_total: dict[str, dict[str, float]] = {
        "asset_type": {},
        "currency": {},
        "sector": {},
        "country": {},
        "market_cap_bucket": {},
    }
    security_exposures: dict[str, float] = {}
    position_constituents: dict[str, dict[str, float]] = {}
    coverage = {"constituent_positions": 0, "lookthrough_positions": 0, "covered_weight": 0.0}

    for position in positions:
        symbol = position.symbol.upper()
        master = _upsert_security_master(
            db,
            symbol=symbol,
            as_of_date=today,
            position=position,
            fundamental=fundamentals.get(symbol),
        )
        direct_labels = {
            "asset_type": _clean_label(position.asset_type, "Unclassified"),
            "currency": _clean_label(position.currency, "Unknown"),
            "sector": _clean_label(master.sector, "Unknown sector"),
            "country": _clean_label(master.country, "Unknown country"),
            "market_cap_bucket": _clean_label(master.market_cap_bucket, "Unknown"),
        }
        for dimension, label in direct_labels.items():
            lookthrough_direct[dimension][label] = lookthrough_direct[dimension].get(label, 0.0) + float(position.weight)

        constituents = _normalize_constituents(symbol, position, master) if _is_etf_like(position) else [
            {
                "symbol": symbol,
                "name": position.name or symbol,
                "weight": 1.0,
                "sector": master.sector or "Unknown sector",
                "country": master.country or "Unknown country",
                "currency": position.currency or "USD",
                "market_cap_bucket": master.market_cap_bucket or "Unknown",
            }
        ]
        if _is_etf_like(position) and symbol not in LOOKTHROUGH_REGISTRY:
            warnings.append(f"lookthrough_registry_missing:{symbol}")
        if _is_etf_like(position):
            coverage["constituent_positions"] += 1
        if constituents:
            coverage["lookthrough_positions"] += 1
            coverage["covered_weight"] += float(position.weight)

        db.execute(delete(EtfConstituentSnapshot).where(EtfConstituentSnapshot.parent_symbol == symbol).where(EtfConstituentSnapshot.as_of_date == today))
        constituent_map: dict[str, float] = {}
        for constituent in constituents:
            weight = float(constituent.get("weight", 0.0))
            if weight <= 0:
                continue
            db.add(
                EtfConstituentSnapshot(
                    parent_symbol=symbol,
                    constituent_symbol=str(constituent.get("symbol", symbol)).upper(),
                    constituent_name=str(constituent.get("name") or constituent.get("symbol") or symbol),
                    weight=weight,
                    sector=_clean_label(constituent.get("sector"), "Unknown sector"),
                    country=_clean_label(constituent.get("country"), "Unknown country"),
                    currency=_clean_label(constituent.get("currency"), position.currency or "USD"),
                    market_cap_bucket=_clean_label(constituent.get("market_cap_bucket"), "Unknown"),
                    as_of_date=today,
                    source="registry",
                )
            )
            effective_weight = float(position.weight) * weight
            constituent_symbol = str(constituent.get("symbol", symbol)).upper()
            constituent_map[constituent_symbol] = constituent_map.get(constituent_symbol, 0.0) + effective_weight
            security_exposures[constituent_symbol] = security_exposures.get(constituent_symbol, 0.0) + effective_weight
            for dimension in lookthrough_total:
                label = _clean_label(constituent.get(dimension), direct_labels[dimension])
                lookthrough_total[dimension][label] = lookthrough_total[dimension].get(label, 0.0) + effective_weight
        position_constituents[symbol] = constituent_map

    for dimension, total_weights in lookthrough_total.items():
        for bucket, lookthrough_weight in total_weights.items():
            db.add(
                PortfolioExposureBreakdown(
                    exposure_snapshot_id=exposure_snapshot.id,
                    dimension=dimension,
                    bucket=bucket,
                    direct_weight=lookthrough_direct[dimension].get(bucket, 0.0),
                    lookthrough_weight=lookthrough_weight,
                )
            )

    symbols = sorted(position_constituents)
    overlaps: list[dict[str, Any]] = []
    for idx, left in enumerate(symbols):
        for right in symbols[idx + 1 :]:
            shared = set(position_constituents[left]).intersection(position_constituents[right])
            overlap_weight = sum(min(position_constituents[left][sym], position_constituents[right][sym]) for sym in shared)
            if overlap_weight <= 0:
                continue
            pair_base = float(next((p.weight for p in positions if p.symbol.upper() == left), 0.0)) + float(next((p.weight for p in positions if p.symbol.upper() == right), 0.0))
            overlap_pct_of_pair = overlap_weight / pair_base if pair_base > 0 else 0.0
            overlap_type = "lookthrough" if (left in LOOKTHROUGH_REGISTRY or right in LOOKTHROUGH_REGISTRY) else "direct"
            overlaps.append(
                {
                    "left_symbol": left,
                    "right_symbol": right,
                    "overlap_weight": float(overlap_weight),
                    "overlap_pct_of_pair": float(overlap_pct_of_pair),
                    "overlap_type": overlap_type,
                }
            )
            db.add(
                PortfolioOverlapPair(
                    exposure_snapshot_id=exposure_snapshot.id,
                    left_symbol=left,
                    right_symbol=right,
                    overlap_weight=float(overlap_weight),
                    overlap_pct_of_pair=float(overlap_pct_of_pair),
                    overlap_type=overlap_type,
                )
            )

    ranked_security = sorted(security_exposures.items(), key=lambda item: (-item[1], item[0]))
    top3 = sum(weight for _, weight in ranked_security[:3])
    top_sector_label, top_sector_weight = max(lookthrough_total["sector"].items(), key=lambda item: item[1], default=("Unknown sector", 0.0))
    top_country_label, top_country_weight = max(lookthrough_total["country"].items(), key=lambda item: item[1], default=("Unknown country", 0.0))
    top_currency_label, top_currency_weight = max(lookthrough_total["currency"].items(), key=lambda item: item[1], default=("Unknown", 0.0))
    top_overlap = max(overlaps, key=lambda item: item["overlap_weight"], default=None)

    signal_payloads: list[dict[str, Any]] = []

    def _add_signal(key: str, value: float, severity: str, summary: str) -> None:
        payload = {"signal_key": key, "signal_value": float(value), "severity": severity, "summary": summary}
        signal_payloads.append(payload)
        db.add(
            PortfolioConcentrationSignal(
                exposure_snapshot_id=exposure_snapshot.id,
                signal_key=key,
                signal_value=float(value),
                severity=severity,
                summary=summary,
            )
        )

    if top3 >= 0.45:
        _add_signal("top3_lookthrough_weight", top3, "high" if top3 >= 0.6 else "medium", f"Top three look-through names account for {top3 * 100:.1f}% of exposure.")
    if top_sector_weight >= 0.32:
        _add_signal("sector_crowding", top_sector_weight, "high" if top_sector_weight >= 0.45 else "medium", f"{top_sector_label} drives {top_sector_weight * 100:.1f}% of look-through exposure.")
    if top_country_weight >= 0.65:
        _add_signal("country_dominance", top_country_weight, "high" if top_country_weight >= 0.85 else "medium", f"{top_country_label} accounts for {top_country_weight * 100:.1f}% of look-through exposure.")
    if top_currency_weight >= 0.75:
        _add_signal("currency_dominance", top_currency_weight, "high" if top_currency_weight >= 0.9 else "medium", f"{top_currency_label} represents {top_currency_weight * 100:.1f}% of currency exposure.")
    if top_overlap is not None and top_overlap["overlap_weight"] >= 0.05:
        _add_signal("fund_overlap", top_overlap["overlap_weight"], "medium" if top_overlap["overlap_weight"] < 0.12 else "high", f"{top_overlap['left_symbol']} and {top_overlap['right_symbol']} share {top_overlap['overlap_weight'] * 100:.1f}% look-through exposure.")

    summary = {
        "methodology_version": METHODOLOGY_VERSION,
        "coverage": {
            "holding_count": len(positions),
            "lookthrough_positions": coverage["lookthrough_positions"],
            "constituent_positions": coverage["constituent_positions"],
            "covered_weight": float(coverage["covered_weight"]),
            "covered_weight_pct": float(coverage["covered_weight"] * 100.0),
        },
        "breakdowns": {
            dimension: _bucketize(lookthrough_total[dimension], lookthrough_direct[dimension])
            for dimension in lookthrough_total
        },
        "top_lookthrough_holdings": [
            {"symbol": symbol, "weight": float(weight), "weight_pct": float(weight * 100.0)}
            for symbol, weight in ranked_security[:8]
        ],
        "overlap_pairs": sorted(overlaps, key=lambda item: (-item["overlap_weight"], item["left_symbol"], item["right_symbol"]))[:8],
        "concentration_signals": sorted(signal_payloads, key=lambda item: (-item["signal_value"], item["signal_key"])),
    }

    exposure_snapshot.summary_json = _json_dumps(summary)
    exposure_snapshot.warnings_json = _json_dumps(sorted(set(warnings)))
    db.flush()
    return ExposureBuildResult(snapshot=exposure_snapshot, warnings=sorted(set(warnings)), summary=summary)


def latest_exposure_snapshot(db: Session, portfolio_id: int, snapshot_id: int | None = None) -> PortfolioExposureSnapshot | None:
    query = select(PortfolioExposureSnapshot).where(PortfolioExposureSnapshot.portfolio_id == portfolio_id)
    if snapshot_id is not None:
        query = query.where(PortfolioExposureSnapshot.snapshot_id == snapshot_id)
    return db.scalar(query.order_by(PortfolioExposureSnapshot.as_of_date.desc(), PortfolioExposureSnapshot.id.desc()).limit(1))


def exposure_snapshot_payload(exposure_snapshot: PortfolioExposureSnapshot | None) -> dict[str, Any] | None:
    if exposure_snapshot is None:
        return None
    payload = _json_loads(exposure_snapshot.summary_json, {})
    payload.setdefault("warnings", _json_loads(exposure_snapshot.warnings_json, []))
    payload.setdefault("snapshot_id", exposure_snapshot.snapshot_id)
    payload.setdefault("as_of_date", str(exposure_snapshot.as_of_date))
    payload.setdefault("methodology_version", exposure_snapshot.methodology_version)
    return payload
