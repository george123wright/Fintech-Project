from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import (
    HoldingsPosition,
    HoldingsSnapshot,
    PortfolioMetricSnapshot,
    PortfolioValuationSnapshot,
    SecurityAnalystSnapshot,
    SecurityForwardEstimateSnapshot,
    SecurityFundamentalSnapshot,
    SecurityValuationResult,
    ValuationDcfDetail,
    ValuationDdmDetail,
    ValuationRiDetail,
    ValuationRun,
)
from app.services.providers import (
    fetch_financial_ratios,
    fetch_financial_statements,
    fetch_forward_estimates,
    fetch_market_rate_snapshot,
    fetch_security_snapshot,
)
from app.services.valuation.analyst import compute_analyst_upside
from app.services.valuation.dcf import compute_dcf_fair_value
from app.services.valuation.ddm import compute_ddm_fair_value
from app.services.valuation.relative import compute_relative_fair_value
from app.services.valuation.ri import compute_ri_fair_value


DEFAULT_VALUATION_ASSUMPTIONS: dict[str, Any] = {
    "dcf": {
        "terminal_growth": 0.025,
        "steady_state_growth": 0.025,
        "discount_rate": None,
        "explicit_years": 7,
        "rf": 0.02,
        "erp": 0.05,
        "anchor_mode": "revenue_only",
        "tv_method": "blended",
        "tv_blend_weight": 0.65,
        "reinvestment_blend_weight": 0.50,
        "fallback_rev_spread": 0.10,
        "fallback_eps_spread": 0.15,
        "terminal_clip_buffer": 0.02,
        "quality_penalty_enabled": True,
    },
    "ri": {
        "explicit_years": 7,
        "anchor_mode": "revenue_eps_consistency",
        "terminal_method": "blended",
        "terminal_blend_weight": 0.65,
        "steady_state_growth": 0.025,
        "long_run_roe": 0.12,
        "long_run_payout": 0.35,
        "payout_smoothing_weight": 0.60,
        "fade_years_post_horizon": 8,
        "fallback_rev_spread": 0.10,
        "fallback_eps_spread": 0.15,
        "terminal_clip_buffer": 0.02,
        "quality_penalty_enabled": True,
        "cost_of_equity": None,
    },
    "ddm": {
        "explicit_years": 7,
        "anchor_mode": "eps_payout_linked",
        "coverage_mode": "hybrid_eps_payout",
        "terminal_method": "two_stage_gordon",
        "steady_state_growth": 0.025,
        "long_run_payout": 0.35,
        "payout_smoothing_weight": 0.60,
        "initiation_payout_floor": 0.08,
        "payout_cap": 0.90,
        "fallback_eps_spread": 0.15,
        "fallback_payout_spread": 0.10,
        "terminal_clip_buffer": 0.02,
        "quality_penalty_enabled": True,
        "cost_of_equity": None,
    },
    "relative": {
        "peer_set": "sector",
        "multiples": ["forward_pe", "pb", "ev_ebitda"],
        "cap_upside": 0.6,
    },
}


@dataclass
class ValuationRunOutcome:
    run: ValuationRun
    portfolio_snapshot: PortfolioValuationSnapshot | None
    warnings: list[str]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    out = json.loads(json.dumps(base))
    if not override:
        return out
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def _inject_dynamic_market_rates(assumptions: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    warnings: list[str] = []
    dcf_cfg = assumptions.setdefault("dcf", {})

    default_rf = _as_float(dcf_cfg.get("rf"))
    if default_rf is None:
        default_rf = 0.02
    default_erp = _as_float(dcf_cfg.get("erp"))
    if default_erp is None:
        default_erp = 0.05

    diagnostics: dict[str, Any] = {
        "market_symbol": "^GSPC",
        "risk_free_symbol": "^TNX",
        "rf": default_rf,
        "erp": default_erp,
        "market_return_5y": None,
        "observations": 0,
        "source": "default",
    }

    try:
        snapshot = fetch_market_rate_snapshot(
            years=5,
            market_symbol="^GSPC",
            risk_free_symbol="^TNX",
        )
    except Exception as exc:
        warnings.append(f"market_rates:fetch_failed:{exc.__class__.__name__}")
        dcf_cfg["rf"] = float(default_rf)
        dcf_cfg["erp"] = float(default_erp)
        return warnings, diagnostics

    warnings.extend([f"market_rates:{warning}" for warning in snapshot.warnings])

    rf = snapshot.risk_free_rate if snapshot.risk_free_rate is not None else default_rf
    if snapshot.risk_free_rate is None:
        warnings.append("market_rates:risk_free_fallback")
    rf = float(max(0.0, min(0.2, rf)))

    erp = snapshot.erp_5y if snapshot.erp_5y is not None else default_erp
    if snapshot.erp_5y is None:
        warnings.append("market_rates:erp_fallback")
    # Keep ERP bounded for stability while allowing weak/negative periods.
    erp = float(max(-0.2, min(0.3, erp)))

    dcf_cfg["rf"] = rf
    dcf_cfg["erp"] = erp

    diagnostics.update(
        {
            "rf": rf,
            "erp": erp,
            "market_return_5y": snapshot.market_return_5y,
            "observations": snapshot.observations,
            "status": snapshot.status,
            "source": "yahoo_market_snapshot",
            "as_of_date": snapshot.as_of_date.isoformat(),
        }
    )
    return warnings, diagnostics


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number):  # NaN
        return None
    return number


def _normalize_metric_label(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _statement_row(rows: list[dict[str, Any]], aliases: list[str]) -> dict[str, Any] | None:
    lookup = {_normalize_metric_label(alias) for alias in aliases}
    for row in rows:
        metric = row.get("Metric")
        if not isinstance(metric, str):
            continue
        if _normalize_metric_label(metric) in lookup:
            return row
    return None


def _statement_columns(row: dict[str, Any] | None) -> list[str]:
    if row is None:
        return []
    cols = [key for key in row.keys() if key != "Metric"]

    def sort_key(col: str) -> tuple[int, str]:
        # ISO dates sort lexicographically; keep those first, descending.
        if len(col) == 10 and col[4] == "-" and col[7] == "-":
            return (0, col)
        return (1, col)

    return sorted(cols, key=sort_key, reverse=True)


def _statement_values(row: dict[str, Any] | None, *, max_points: int = 6) -> list[float]:
    if row is None:
        return []
    values: list[float] = []
    for col in _statement_columns(row):
        value = _as_float(row.get(col))
        if value is None:
            continue
        values.append(value)
        if len(values) >= max_points:
            break
    return values


def _statement_latest_prev(rows: list[dict[str, Any]], aliases: list[str]) -> tuple[float | None, float | None]:
    values = _statement_values(_statement_row(rows, aliases), max_points=2)
    latest = values[0] if len(values) > 0 else None
    prev = values[1] if len(values) > 1 else None
    return latest, prev


def _ratio_map(metrics_rows: list[Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in metrics_rows:
        key = getattr(row, "key", None)
        value = _as_float(getattr(row, "value", None))
        if isinstance(key, str) and value is not None:
            out[key] = value
    return out


def _build_statement_inputs(
    *,
    financials_payload: Any | None,
    current_price: float | None,
    growth_proxy: float | None,
) -> dict[str, Any]:
    income_rows = (
        financials_payload.income_statement_annual
        if financials_payload is not None and financials_payload.income_statement_annual
        else []
    )
    balance_rows = (
        financials_payload.balance_sheet_annual
        if financials_payload is not None and financials_payload.balance_sheet_annual
        else []
    )
    cashflow_rows = (
        financials_payload.cashflow_annual
        if financials_payload is not None and financials_payload.cashflow_annual
        else []
    )

    revenue_latest, revenue_prev = _statement_latest_prev(
        income_rows,
        ["Total Revenue", "Operating Revenue", "Revenue"],
    )
    operating_income_latest, _ = _statement_latest_prev(
        income_rows,
        ["Operating Income", "Total Operating Income As Reported", "EBIT"],
    )
    net_income_latest, _ = _statement_latest_prev(
        income_rows,
        [
            "Net Income",
            "Net Income Common Stockholders",
            "Net Income Including Noncontrolling Interests",
            "Net Income Continuous Operations",
        ],
    )
    tax_rate_eff, _ = _statement_latest_prev(income_rows, ["Tax Rate For Calcs"])
    if tax_rate_eff is not None and tax_rate_eff > 1:
        tax_rate_eff = tax_rate_eff / 100.0
    tax_provision_latest, _ = _statement_latest_prev(income_rows, ["Tax Provision"])
    pretax_income_latest, _ = _statement_latest_prev(income_rows, ["Pretax Income"])
    interest_expense_latest, _ = _statement_latest_prev(
        income_rows,
        ["Interest Expense", "Interest Expense Non Operating"],
    )
    diluted_eps_latest, _ = _statement_latest_prev(income_rows, ["Diluted EPS"])
    diluted_shares_latest, diluted_shares_prev = _statement_latest_prev(income_rows, ["Diluted Average Shares"])

    depreciation_latest, _ = _statement_latest_prev(
        cashflow_rows,
        [
            "Depreciation And Amortization",
            "Depreciation Amortization Depletion",
            "Depreciation",
            "Reconciled Depreciation",
        ],
    )
    capex_latest, _ = _statement_latest_prev(
        cashflow_rows,
        ["Capital Expenditure", "Purchase Of PPE", "Net PPE Purchase And Sale"],
    )
    dividends_paid_latest, dividends_paid_prev = _statement_latest_prev(
        cashflow_rows,
        ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    )

    current_assets_latest, _ = _statement_latest_prev(balance_rows, ["Current Assets", "Total Current Assets"])
    current_liabilities_latest, _ = _statement_latest_prev(
        balance_rows,
        ["Current Liabilities", "Total Current Liabilities"],
    )
    invested_capital_latest, _ = _statement_latest_prev(balance_rows, ["Invested Capital"])
    total_debt_latest, total_debt_prev = _statement_latest_prev(balance_rows, ["Total Debt"])
    cash_and_short_latest, _ = _statement_latest_prev(
        balance_rows,
        [
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Short Term Investments",
            "Cash And Cash Equivalents",
        ],
    )
    cash_latest, _ = _statement_latest_prev(balance_rows, ["Cash And Cash Equivalents"])
    avg_debt = None
    if total_debt_latest is not None and total_debt_prev is not None:
        avg_debt = (total_debt_latest + total_debt_prev) / 2.0
    elif total_debt_latest is not None:
        avg_debt = total_debt_latest

    revenue_row = _statement_row(income_rows, ["Total Revenue", "Operating Revenue", "Revenue"])
    operating_row = _statement_row(
        income_rows,
        ["Operating Income", "Total Operating Income As Reported", "EBIT"],
    )
    net_income_row = _statement_row(
        income_rows,
        [
            "Net Income",
            "Net Income Common Stockholders",
            "Net Income Including Noncontrolling Interests",
            "Net Income Continuous Operations",
        ],
    )
    ebit_margin_history: list[float] = []
    net_margin_history: list[float] = []
    for col in _statement_columns(revenue_row)[:5]:
        revenue = _as_float(revenue_row.get(col) if revenue_row else None)
        if revenue is None or abs(revenue) < 1e-12:
            continue
        operating_income = _as_float(operating_row.get(col) if operating_row else None)
        net_income = _as_float(net_income_row.get(col) if net_income_row else None)
        if operating_income is not None:
            ebit_margin_history.append(operating_income / revenue)
        if net_income is not None:
            net_margin_history.append(net_income / revenue)

    if growth_proxy is None and revenue_latest is not None and revenue_prev is not None and abs(revenue_prev) > 1e-12:
        growth_proxy = revenue_latest / revenue_prev - 1.0

    nopat_latest = None
    if operating_income_latest is not None:
        tax_used = tax_rate_eff if tax_rate_eff is not None else 0.21
        nopat_latest = operating_income_latest * (1.0 - tax_used)

    return {
        "current_price": current_price,
        "revenue_latest": revenue_latest,
        "revenue_prev": revenue_prev,
        "growth_proxy": growth_proxy,
        "ebit_margin_history": ebit_margin_history,
        "net_margin_history": net_margin_history,
        "tax_rate_eff": tax_rate_eff,
        "tax_provision_latest": tax_provision_latest,
        "pretax_income_latest": pretax_income_latest,
        "depreciation_latest": depreciation_latest,
        "capex_latest": capex_latest,
        "current_assets_latest": current_assets_latest,
        "current_liabilities_latest": current_liabilities_latest,
        "nopat_latest": nopat_latest,
        "invested_capital_latest": invested_capital_latest,
        "diluted_shares_latest": diluted_shares_latest,
        "diluted_shares_prev": diluted_shares_prev,
        "total_debt_latest": total_debt_latest,
        "total_debt_prev": total_debt_prev,
        "cash_and_short_latest": cash_and_short_latest,
        "cash_latest": cash_latest,
        "avg_debt": avg_debt,
        "interest_expense_latest": interest_expense_latest,
        "diluted_eps_latest": diluted_eps_latest,
        "net_income_latest": net_income_latest,
        "dividends_paid_latest": dividends_paid_latest,
        "dividends_paid_prev": dividends_paid_prev,
    }


def _upsert_forward_estimate_snapshot(
    db: Session,
    *,
    symbol: str,
    as_of_date: date,
    payload,
) -> SecurityForwardEstimateSnapshot:
    values = {
        "symbol": symbol,
        "as_of_date": as_of_date,
        "fy0_revenue_avg": payload.fy0_revenue_avg,
        "fy0_revenue_low": payload.fy0_revenue_low,
        "fy0_revenue_high": payload.fy0_revenue_high,
        "fy1_revenue_avg": payload.fy1_revenue_avg,
        "fy1_revenue_low": payload.fy1_revenue_low,
        "fy1_revenue_high": payload.fy1_revenue_high,
        "fy0_eps_avg": payload.fy0_eps_avg,
        "fy0_eps_low": payload.fy0_eps_low,
        "fy0_eps_high": payload.fy0_eps_high,
        "fy1_eps_avg": payload.fy1_eps_avg,
        "fy1_eps_low": payload.fy1_eps_low,
        "fy1_eps_high": payload.fy1_eps_high,
        "revenue_analyst_count_fy0": payload.revenue_analyst_count_fy0,
        "revenue_analyst_count_fy1": payload.revenue_analyst_count_fy1,
        "eps_analyst_count_fy0": payload.eps_analyst_count_fy0,
        "eps_analyst_count_fy1": payload.eps_analyst_count_fy1,
        "source": "yfinance",
        "fetched_at": datetime.utcnow(),
    }

    stmt = sqlite_insert(SecurityForwardEstimateSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SecurityForwardEstimateSnapshot.symbol,
            SecurityForwardEstimateSnapshot.as_of_date,
        ],
        set_={key: values[key] for key in values.keys() if key not in {"symbol", "as_of_date"}},
    )
    db.execute(stmt)

    row = db.scalar(
        select(SecurityForwardEstimateSnapshot)
        .where(SecurityForwardEstimateSnapshot.symbol == symbol)
        .where(SecurityForwardEstimateSnapshot.as_of_date == as_of_date)
        .limit(1)
    )
    if row is None:
        raise RuntimeError(f"Failed to upsert forward estimate snapshot for {symbol}")
    return row


def _latest_snapshot_or_raise(db: Session, portfolio_id: int, snapshot_id: int | None) -> HoldingsSnapshot:
    if snapshot_id is not None:
        snapshot = db.get(HoldingsSnapshot, snapshot_id)
    else:
        snapshot = db.scalar(
            select(HoldingsSnapshot)
            .where(HoldingsSnapshot.portfolio_id == portfolio_id)
            .order_by(HoldingsSnapshot.as_of_date.desc(), HoldingsSnapshot.created_at.desc())
            .limit(1)
        )
    if snapshot is None:
        raise ValueError("No holdings snapshot found for valuation run.")
    return snapshot


def _latest_metric_beta(db: Session, snapshot_id: int) -> float | None:
    metric = db.scalar(
        select(PortfolioMetricSnapshot)
        .where(PortfolioMetricSnapshot.snapshot_id == snapshot_id)
        .order_by(PortfolioMetricSnapshot.as_of_date.desc(), PortfolioMetricSnapshot.created_at.desc())
        .limit(1)
    )
    if metric is None:
        return None
    return float(metric.beta)


def _upsert_analyst_snapshot(
    db: Session,
    *,
    symbol: str,
    as_of_date: date,
    payload,
) -> SecurityAnalystSnapshot:
    values = {
        "symbol": symbol,
        "as_of_date": as_of_date,
        "current_price": payload.current_price,
        "target_mean": payload.target_mean,
        "target_high": payload.target_high,
        "target_low": payload.target_low,
        "analyst_count": payload.analyst_count,
        "recommendation_key": payload.recommendation_key,
        "recommendation_mean": payload.recommendation_mean,
        "source": "yfinance",
        "fetched_at": datetime.utcnow(),
    }

    stmt = sqlite_insert(SecurityAnalystSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SecurityAnalystSnapshot.symbol,
            SecurityAnalystSnapshot.as_of_date,
        ],
        set_={key: values[key] for key in values.keys() if key not in {"symbol", "as_of_date"}},
    )
    db.execute(stmt)

    row = db.scalar(
        select(SecurityAnalystSnapshot)
        .where(SecurityAnalystSnapshot.symbol == symbol)
        .where(SecurityAnalystSnapshot.as_of_date == as_of_date)
        .limit(1)
    )
    if row is None:
        raise RuntimeError(f"Failed to upsert analyst snapshot for {symbol}")
    return row


def _upsert_fundamental_snapshot(
    db: Session,
    *,
    symbol: str,
    as_of_date: date,
    payload,
) -> SecurityFundamentalSnapshot:
    values = {
        "symbol": symbol,
        "as_of_date": as_of_date,
        "market_cap": payload.market_cap,
        "shares_outstanding": payload.shares_outstanding,
        "free_cashflow": payload.free_cashflow,
        "trailing_eps": payload.trailing_eps,
        "forward_eps": payload.forward_eps,
        "book_value_per_share": payload.book_value_per_share,
        "roe": payload.roe,
        "pe": payload.pe,
        "forward_pe": payload.forward_pe,
        "pb": payload.pb,
        "ev_ebitda": payload.ev_ebitda,
        "sector": payload.sector,
        "industry": payload.industry,
        "source": "yfinance",
        "fetched_at": datetime.utcnow(),
    }

    stmt = sqlite_insert(SecurityFundamentalSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SecurityFundamentalSnapshot.symbol,
            SecurityFundamentalSnapshot.as_of_date,
        ],
        set_={key: values[key] for key in values.keys() if key not in {"symbol", "as_of_date"}},
    )
    db.execute(stmt)

    row = db.scalar(
        select(SecurityFundamentalSnapshot)
        .where(SecurityFundamentalSnapshot.symbol == symbol)
        .where(SecurityFundamentalSnapshot.as_of_date == as_of_date)
        .limit(1)
    )
    if row is None:
        raise RuntimeError(f"Failed to upsert fundamental snapshot for {symbol}")
    return row


def run_portfolio_valuation(
    db: Session,
    *,
    portfolio_id: int,
    snapshot_id: int | None = None,
    trigger_type: str = "manual",
    assumptions_override: dict[str, Any] | None = None,
) -> ValuationRunOutcome:
    snapshot = _latest_snapshot_or_raise(db, portfolio_id, snapshot_id)
    assumptions = _deep_merge(DEFAULT_VALUATION_ASSUMPTIONS, assumptions_override)
    today = date.today()

    run = ValuationRun(
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        trigger_type=trigger_type,
        status="running",
        assumptions_json=_json_dumps(assumptions),
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()
    # Persist the run marker early, then release the write lock before
    # provider/network work begins.
    db.commit()
    db.refresh(run)

    warnings_global: list[str] = []
    positions = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )

    if not positions:
        run.status = "failed"
        run.error = "Snapshot has no holdings positions."
        run.finished_at = datetime.utcnow()
        db.flush()
        return ValuationRunOutcome(run=run, portfolio_snapshot=None, warnings=[])

    rate_warnings, rate_diagnostics = _inject_dynamic_market_rates(assumptions)
    warnings_global.extend(rate_warnings)
    assumptions.setdefault("meta", {})["market_rate_snapshot"] = rate_diagnostics
    run.assumptions_json = _json_dumps(assumptions)
    db.flush()
    db.commit()
    db.refresh(run)

    portfolio_beta = _latest_metric_beta(db, snapshot.id)

    weighted_analyst_upside = 0.0
    weighted_dcf_upside = 0.0
    weighted_ri_upside = 0.0
    weighted_ddm_upside = 0.0
    weighted_relative_upside = 0.0
    weighted_composite_upside = None
    coverage_ratio = 0.0
    overvalued_weight = 0.0
    undervalued_weight = 0.0
    covered_weight = 0.0
    result_rows: list[SecurityValuationResult] = []

    for position in positions:
        symbol = position.symbol.upper()
        row_warnings: list[str] = []
        try:
            yahoo_snapshot = fetch_security_snapshot(symbol, today)
        except Exception as exc:
            row_warnings.append(f"provider: yfinance_failed:{exc.__class__.__name__}")
            yahoo_snapshot = None

        if yahoo_snapshot is not None:
            analyst_snapshot = _upsert_analyst_snapshot(
                db,
                symbol=symbol,
                as_of_date=today,
                payload=yahoo_snapshot,
            )
            fundamental_snapshot = _upsert_fundamental_snapshot(
                db,
                symbol=symbol,
                as_of_date=today,
                payload=yahoo_snapshot,
            )
            current_price = yahoo_snapshot.current_price
            target_mean = yahoo_snapshot.target_mean
            growth_proxy = yahoo_snapshot.growth_proxy
            sector = yahoo_snapshot.sector
        else:
            analyst_snapshot = db.scalar(
                select(SecurityAnalystSnapshot)
                .where(SecurityAnalystSnapshot.symbol == symbol)
                .order_by(desc(SecurityAnalystSnapshot.as_of_date), desc(SecurityAnalystSnapshot.fetched_at))
                .limit(1)
            )
            fundamental_snapshot = db.scalar(
                select(SecurityFundamentalSnapshot)
                .where(SecurityFundamentalSnapshot.symbol == symbol)
                .order_by(desc(SecurityFundamentalSnapshot.as_of_date), desc(SecurityFundamentalSnapshot.fetched_at))
                .limit(1)
            )
            if analyst_snapshot is None and fundamental_snapshot is None:
                row_warnings.append("provider: no_cached_snapshot")

            current_price = analyst_snapshot.current_price if analyst_snapshot is not None else None
            target_mean = analyst_snapshot.target_mean if analyst_snapshot is not None else None
            growth_proxy = None
            sector = fundamental_snapshot.sector if fundamental_snapshot is not None else None

        analyst_upside, _analyst_status, analyst_warn = compute_analyst_upside(
            current_price=current_price,
            target_mean=target_mean,
        )
        row_warnings.extend(analyst_warn)

        forward_snapshot = None
        try:
            forward_payload = fetch_forward_estimates(symbol=symbol)
            row_warnings.extend([f"forward:{warn}" for warn in forward_payload.warnings])
            forward_snapshot = _upsert_forward_estimate_snapshot(
                db,
                symbol=symbol,
                as_of_date=today,
                payload=forward_payload,
            )
        except Exception as exc:
            row_warnings.append(f"forward:fetch_failed:{exc.__class__.__name__}")
            forward_snapshot = db.scalar(
                select(SecurityForwardEstimateSnapshot)
                .where(SecurityForwardEstimateSnapshot.symbol == symbol)
                .order_by(
                    desc(SecurityForwardEstimateSnapshot.as_of_date),
                    desc(SecurityForwardEstimateSnapshot.fetched_at),
                )
                .limit(1)
            )

        if forward_snapshot is None:
            row_warnings.append("dcf:missing_forward_estimates")

        try:
            financials_payload = fetch_financial_statements(symbol=symbol, max_rows=260)
            row_warnings.extend([f"statements:{warn}" for warn in financials_payload.warnings])
        except Exception as exc:
            financials_payload = None
            row_warnings.append(f"statements:fetch_failed:{exc.__class__.__name__}")

        try:
            ratios_payload = fetch_financial_ratios(symbol=symbol)
            row_warnings.extend([f"ratios:{warn}" for warn in ratios_payload.warnings])
        except Exception as exc:
            ratios_payload = None
            row_warnings.append(f"ratios:fetch_failed:{exc.__class__.__name__}")

        statement_inputs = _build_statement_inputs(
            financials_payload=financials_payload,
            current_price=current_price,
            growth_proxy=growth_proxy,
        )

        ratio_inputs = _ratio_map(ratios_payload.annual if ratios_payload is not None else [])
        if "nwc_to_revenue" not in ratio_inputs:
            current_assets = _as_float(statement_inputs.get("current_assets_latest"))
            current_liabilities = _as_float(statement_inputs.get("current_liabilities_latest"))
            revenue_latest = _as_float(statement_inputs.get("revenue_latest"))
            if (
                current_assets is not None
                and current_liabilities is not None
                and revenue_latest is not None
                and abs(revenue_latest) > 1e-12
            ):
                ratio_inputs["nwc_to_revenue"] = (current_assets - current_liabilities) / revenue_latest
        if "da_to_revenue" not in ratio_inputs:
            depreciation_latest = _as_float(statement_inputs.get("depreciation_latest"))
            revenue_latest = _as_float(statement_inputs.get("revenue_latest"))
            if depreciation_latest is not None and revenue_latest is not None and abs(revenue_latest) > 1e-12:
                ratio_inputs["da_to_revenue"] = depreciation_latest / revenue_latest
        if "capex_to_revenue" not in ratio_inputs:
            capex_latest = _as_float(statement_inputs.get("capex_latest"))
            revenue_latest = _as_float(statement_inputs.get("revenue_latest"))
            if capex_latest is not None and revenue_latest is not None and abs(revenue_latest) > 1e-12:
                ratio_inputs["capex_to_revenue"] = abs(capex_latest) / revenue_latest

        forward_estimates = {
            "fy0_revenue_avg": (forward_snapshot.fy0_revenue_avg if forward_snapshot is not None else None),
            "fy0_revenue_low": (forward_snapshot.fy0_revenue_low if forward_snapshot is not None else None),
            "fy0_revenue_high": (forward_snapshot.fy0_revenue_high if forward_snapshot is not None else None),
            "fy1_revenue_avg": (forward_snapshot.fy1_revenue_avg if forward_snapshot is not None else None),
            "fy1_revenue_low": (forward_snapshot.fy1_revenue_low if forward_snapshot is not None else None),
            "fy1_revenue_high": (forward_snapshot.fy1_revenue_high if forward_snapshot is not None else None),
            "fy0_eps_avg": (forward_snapshot.fy0_eps_avg if forward_snapshot is not None else None),
            "fy0_eps_low": (forward_snapshot.fy0_eps_low if forward_snapshot is not None else None),
            "fy0_eps_high": (forward_snapshot.fy0_eps_high if forward_snapshot is not None else None),
            "fy1_eps_avg": (forward_snapshot.fy1_eps_avg if forward_snapshot is not None else None),
            "fy1_eps_low": (forward_snapshot.fy1_eps_low if forward_snapshot is not None else None),
            "fy1_eps_high": (forward_snapshot.fy1_eps_high if forward_snapshot is not None else None),
        }

        dcf_fair, dcf_low, dcf_high, dcf_upside, dcf_warn, dcf_detail = compute_dcf_fair_value(
            symbol=symbol,
            current_price=current_price,
            market_cap=(fundamental_snapshot.market_cap if fundamental_snapshot is not None else None),
            shares_outstanding=(fundamental_snapshot.shares_outstanding if fundamental_snapshot is not None else None),
            beta=portfolio_beta,
            sector=sector,
            assumptions=assumptions,
            forward_estimates=forward_estimates,
            statement_inputs=statement_inputs,
            ratio_inputs=ratio_inputs,
        )
        row_warnings.extend(dcf_warn)

        ri_fair, ri_low, ri_high, ri_upside, ri_warn, ri_detail = compute_ri_fair_value(
            symbol=symbol,
            current_price=current_price,
            book_value_per_share=(
                fundamental_snapshot.book_value_per_share if fundamental_snapshot is not None else None
            ),
            roe=(fundamental_snapshot.roe if fundamental_snapshot is not None else None),
            beta=portfolio_beta,
            assumptions=assumptions,
            forward_estimates=forward_estimates,
            statement_inputs=statement_inputs,
            ratio_inputs=ratio_inputs,
            shares_outstanding=(
                fundamental_snapshot.shares_outstanding if fundamental_snapshot is not None else None
            ),
        )
        row_warnings.extend(ri_warn)

        ddm_fair, ddm_low, ddm_high, ddm_upside, ddm_warn, ddm_detail = compute_ddm_fair_value(
            symbol=symbol,
            current_price=current_price,
            beta=portfolio_beta,
            assumptions=assumptions,
            forward_estimates=forward_estimates,
            statement_inputs=statement_inputs,
            ratio_inputs=ratio_inputs,
            shares_outstanding=(
                fundamental_snapshot.shares_outstanding if fundamental_snapshot is not None else None
            ),
        )
        row_warnings.extend(ddm_warn)

        relative_fair, relative_upside, rel_warn, rel_used = compute_relative_fair_value(
            current_price=current_price,
            sector=sector,
            metrics={
                "forward_pe": (fundamental_snapshot.forward_pe if fundamental_snapshot is not None else None),
                "pb": (fundamental_snapshot.pb if fundamental_snapshot is not None else None),
                "ev_ebitda": (fundamental_snapshot.ev_ebitda if fundamental_snapshot is not None else None),
            },
            assumptions=assumptions,
        )
        row_warnings.extend(rel_warn)

        if dcf_upside is None and dcf_fair is not None and current_price and current_price > 0:
            dcf_upside = dcf_fair / current_price - 1.0
        if ri_upside is None and ri_fair is not None and current_price and current_price > 0:
            ri_upside = ri_fair / current_price - 1.0
        if ddm_upside is None and ddm_fair is not None and current_price and current_price > 0:
            ddm_upside = ddm_fair / current_price - 1.0
        if relative_upside is None and relative_fair is not None and current_price and current_price > 0:
            relative_upside = relative_fair / current_price - 1.0

        term_upsides = [x for x in [analyst_upside, dcf_upside, ri_upside, ddm_upside, relative_upside] if x is not None]
        fair_values = [x for x in [dcf_fair, ri_fair, ddm_fair, relative_fair] if x is not None]
        if term_upsides:
            term_avg_upside = float(sum(term_upsides) / len(term_upsides))
        else:
            term_avg_upside = None

        if fair_values:
            conf_low = float(min(fair_values))
            conf_high = float(max(fair_values))
        else:
            range_candidates = [value for value in [dcf_low, ri_low, ddm_low] if value is not None]
            range_high_candidates = [value for value in [dcf_high, ri_high, ddm_high] if value is not None]
            conf_low = min(range_candidates) if range_candidates else None
            conf_high = max(range_high_candidates) if range_high_candidates else None

        if len(term_upsides) >= 3:
            model_status = "full"
        elif len(term_upsides) >= 1:
            model_status = "partial"
        else:
            model_status = "no_data"
            row_warnings.append("valuation: no_term_outputs")

        if analyst_upside is not None:
            weighted_analyst_upside += float(position.weight) * analyst_upside
        if dcf_upside is not None:
            weighted_dcf_upside += float(position.weight) * dcf_upside
        if ri_upside is not None:
            weighted_ri_upside += float(position.weight) * ri_upside
        if ddm_upside is not None:
            weighted_ddm_upside += float(position.weight) * ddm_upside
        if relative_upside is not None:
            weighted_relative_upside += float(position.weight) * relative_upside

        if term_avg_upside is not None:
            covered_weight += float(position.weight)
            if term_avg_upside < 0:
                overvalued_weight += float(position.weight)
            elif term_avg_upside > 0:
                undervalued_weight += float(position.weight)

        dcf_model_version = None
        dcf_quality_score = None
        dcf_anchor_summary: dict[str, Any] = {}
        dcf_tv_summary: dict[str, Any] = {}
        dcf_assumptions_used: dict[str, Any] = {}
        if isinstance(dcf_detail, dict):
            dcf_model_version = dcf_detail.get("model_version")
            dcf_quality_score = dcf_detail.get("quality_score")
            dcf_anchor_summary = dcf_detail.get("anchor_diagnostics_summary") or {}
            dcf_tv_summary = dcf_detail.get("tv_breakdown_summary") or {}
            dcf_assumptions_used = dcf_detail.get("assumptions_used") or {}
            scenario_results = dcf_detail.get("scenario_results")
            if isinstance(scenario_results, dict):
                for scenario_key in ("base", "bull", "bear"):
                    scenario_payload = scenario_results.get(scenario_key)
                    if not isinstance(scenario_payload, dict):
                        continue
                    detail_row = ValuationDcfDetail(
                        run_id=run.id,
                        symbol=symbol,
                        as_of_date=today,
                        scenario_key=scenario_key,
                        assumptions_json=_json_dumps(dcf_assumptions_used),
                        forecast_json=_json_dumps(scenario_payload.get("forecast", [])),
                        diagnostics_json=_json_dumps(
                            {
                                "fair_value": scenario_payload.get("fair_value"),
                                "upside": scenario_payload.get("upside"),
                                "ev": scenario_payload.get("ev"),
                                "wacc": scenario_payload.get("wacc"),
                                "terminal_growth": scenario_payload.get("terminal_growth"),
                                "tv_gordon": scenario_payload.get("tv_gordon"),
                                "tv_multiple": scenario_payload.get("tv_multiple"),
                                "tv_blended": scenario_payload.get("tv_blended"),
                                "tv_pv_share": scenario_payload.get("tv_pv_share"),
                                "anchor_diagnostics": scenario_payload.get("anchor_diagnostics", {}),
                            }
                        ),
                        warnings_json=_json_dumps(scenario_payload.get("warnings", [])),
                    )
                    db.add(detail_row)

        ri_model_version = None
        ri_quality_score = None
        ri_anchor_summary: dict[str, Any] = {}
        ri_terminal_summary: dict[str, Any] = {}
        ri_assumptions_used: dict[str, Any] = {}
        if isinstance(ri_detail, dict):
            ri_model_version = ri_detail.get("model_version")
            ri_quality_score = ri_detail.get("quality_score")
            ri_anchor_summary = ri_detail.get("anchor_diagnostics_summary") or {}
            ri_terminal_summary = ri_detail.get("terminal_summary") or {}
            ri_assumptions_used = ri_detail.get("assumptions_used") or {}
            scenario_results = ri_detail.get("scenario_results")
            if isinstance(scenario_results, dict):
                for scenario_key in ("base", "bull", "bear"):
                    scenario_payload = scenario_results.get(scenario_key)
                    if not isinstance(scenario_payload, dict):
                        continue
                    detail_row = ValuationRiDetail(
                        run_id=run.id,
                        symbol=symbol,
                        as_of_date=today,
                        scenario_key=scenario_key,
                        assumptions_json=_json_dumps(ri_assumptions_used),
                        forecast_json=_json_dumps(scenario_payload.get("forecast", [])),
                        diagnostics_json=_json_dumps(
                            {
                                "fair_value": scenario_payload.get("fair_value"),
                                "upside": scenario_payload.get("upside"),
                                "equity_value": scenario_payload.get("equity_value"),
                                "pv_residual_stream": scenario_payload.get("pv_residual_stream"),
                                "cost_of_equity": scenario_payload.get("cost_of_equity"),
                                "terminal_growth": scenario_payload.get("terminal_growth"),
                                "tv_gordon": scenario_payload.get("tv_gordon"),
                                "tv_fade": scenario_payload.get("tv_fade"),
                                "tv_blended": scenario_payload.get("tv_blended"),
                                "tv_pv_share": scenario_payload.get("tv_pv_share"),
                                "anchor_diagnostics": scenario_payload.get("anchor_diagnostics", {}),
                            }
                        ),
                        warnings_json=_json_dumps(scenario_payload.get("warnings", [])),
                    )
                    db.add(detail_row)

        ddm_model_version = None
        ddm_quality_score = None
        ddm_anchor_summary: dict[str, Any] = {}
        ddm_terminal_summary: dict[str, Any] = {}
        ddm_assumptions_used: dict[str, Any] = {}
        ddm_coverage_mode = None
        if isinstance(ddm_detail, dict):
            ddm_model_version = ddm_detail.get("model_version")
            ddm_quality_score = ddm_detail.get("quality_score")
            ddm_anchor_summary = ddm_detail.get("anchor_diagnostics_summary") or {}
            ddm_terminal_summary = ddm_detail.get("terminal_summary") or {}
            ddm_assumptions_used = ddm_detail.get("assumptions_used") or {}
            ddm_coverage_mode = ddm_detail.get("coverage_mode")
            scenario_results = ddm_detail.get("scenario_results")
            if isinstance(scenario_results, dict):
                for scenario_key in ("base", "bull", "bear"):
                    scenario_payload = scenario_results.get(scenario_key)
                    if not isinstance(scenario_payload, dict):
                        continue
                    detail_row = ValuationDdmDetail(
                        run_id=run.id,
                        symbol=symbol,
                        as_of_date=today,
                        scenario_key=scenario_key,
                        assumptions_json=_json_dumps(ddm_assumptions_used),
                        forecast_json=_json_dumps(scenario_payload.get("forecast", [])),
                        diagnostics_json=_json_dumps(
                            {
                                "fair_value": scenario_payload.get("fair_value"),
                                "upside": scenario_payload.get("upside"),
                                "pv_stage1": scenario_payload.get("pv_stage1"),
                                "terminal_value": scenario_payload.get("terminal_value"),
                                "terminal_pv": scenario_payload.get("terminal_pv"),
                                "cost_of_equity": scenario_payload.get("cost_of_equity"),
                                "terminal_growth": scenario_payload.get("terminal_growth"),
                                "tv_pv_share": scenario_payload.get("tv_pv_share"),
                                "anchor_diagnostics": scenario_payload.get("anchor_diagnostics", {}),
                            }
                        ),
                        warnings_json=_json_dumps(scenario_payload.get("warnings", [])),
                    )
                    db.add(detail_row)

        result = SecurityValuationResult(
            run_id=run.id,
            symbol=symbol,
            as_of_date=today,
            model_status=model_status,
            analyst_upside=analyst_upside,
            dcf_fair_value=dcf_fair,
            ri_fair_value=ri_fair,
            relative_fair_value=relative_fair,
            composite_fair_value=None,
            composite_upside=None,
            confidence_low=conf_low,
            confidence_high=conf_high,
            inputs_json=_json_dumps(
                {
                    "weight": position.weight,
                    "current_price": current_price,
                    "target_mean": target_mean,
                    "term_upsides": {
                        "analyst": analyst_upside,
                        "dcf": dcf_upside,
                        "ri": ri_upside,
                        "ddm": ddm_upside,
                        "relative": relative_upside,
                    },
                    "growth_proxy": growth_proxy,
                    "sector": sector,
                    "dcf_model_version": dcf_model_version,
                    "dcf_quality_score": dcf_quality_score,
                    "dcf_anchor_diagnostics_summary": dcf_anchor_summary,
                    "dcf_tv_breakdown_summary": dcf_tv_summary,
                    "ri_model_version": ri_model_version,
                    "ri_quality_score": ri_quality_score,
                    "ri_anchor_diagnostics_summary": ri_anchor_summary,
                    "ri_terminal_summary": ri_terminal_summary,
                    "ddm_fair_value": ddm_fair,
                    "ddm_model_version": ddm_model_version,
                    "ddm_quality_score": ddm_quality_score,
                    "ddm_anchor_diagnostics_summary": ddm_anchor_summary,
                    "ddm_terminal_summary": ddm_terminal_summary,
                    "ddm_coverage_mode": ddm_coverage_mode,
                    "metrics": {
                        "forward_pe": (
                            fundamental_snapshot.forward_pe if fundamental_snapshot is not None else None
                        ),
                        "pb": (fundamental_snapshot.pb if fundamental_snapshot is not None else None),
                        "ev_ebitda": (
                            fundamental_snapshot.ev_ebitda if fundamental_snapshot is not None else None
                        ),
                    },
                    "relative_ratios": rel_used,
                    "dcf_assumptions_used": dcf_assumptions_used,
                    "ri_assumptions_used": ri_assumptions_used,
                    "ddm_assumptions_used": ddm_assumptions_used,
                    "assumptions": assumptions,
                }
            ),
            warnings_json=_json_dumps(sorted(set(row_warnings))),
        )
        db.add(result)
        result_rows.append(result)
        # Release SQLite write lock between symbols so concurrent endpoints can proceed.
        db.flush()
        db.commit()

    coverage_ratio = covered_weight
    weighted_analyst_out: float | None = weighted_analyst_upside
    weighted_dcf_out: float | None = weighted_dcf_upside
    weighted_ri_out: float | None = weighted_ri_upside
    weighted_ddm_out: float | None = weighted_ddm_upside
    weighted_relative_out: float | None = weighted_relative_upside
    if coverage_ratio <= 0:
        weighted_analyst_out = None
        weighted_dcf_out = None
        weighted_ri_out = None
        weighted_ddm_out = None
        weighted_relative_out = None

    summary = {
        "covered_symbols": sum(1 for row in result_rows if row.model_status in {"partial", "full"}),
        "total_symbols": len(result_rows),
        "covered_weight": covered_weight,
        "weighted_analyst_upside": weighted_analyst_out,
        "weighted_dcf_upside": weighted_dcf_out,
        "weighted_ri_upside": weighted_ri_out,
        "weighted_ddm_upside": weighted_ddm_out,
        "weighted_relative_upside": weighted_relative_out,
        "disclaimer": "Valuation outputs are guidance-only and should not be treated as investment advice.",
    }

    portfolio_snapshot = PortfolioValuationSnapshot(
        run_id=run.id,
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        as_of_date=today,
        weighted_analyst_upside=weighted_analyst_out,
        weighted_composite_upside=weighted_composite_upside,
        coverage_ratio=coverage_ratio,
        overvalued_weight=overvalued_weight,
        undervalued_weight=undervalued_weight,
        summary_json=_json_dumps(summary),
    )
    db.add(portfolio_snapshot)

    run.status = "completed"
    run.error = None
    run.finished_at = datetime.utcnow()
    db.flush()

    if covered_weight <= 0:
        warnings_global.append("valuation: no_term_coverage")
    return ValuationRunOutcome(run=run, portfolio_snapshot=portfolio_snapshot, warnings=warnings_global)


def latest_valuation_run(db: Session, portfolio_id: int) -> ValuationRun | None:
    return db.scalar(
        select(ValuationRun)
        .where(ValuationRun.portfolio_id == portfolio_id)
        .order_by(desc(ValuationRun.started_at))
        .limit(1)
    )


def latest_portfolio_valuation_snapshot(db: Session, portfolio_id: int) -> PortfolioValuationSnapshot | None:
    return db.scalar(
        select(PortfolioValuationSnapshot)
        .where(PortfolioValuationSnapshot.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioValuationSnapshot.as_of_date), desc(PortfolioValuationSnapshot.id))
        .limit(1)
    )


def latest_security_valuation_result(
    db: Session,
    *,
    portfolio_id: int,
    symbol: str,
) -> SecurityValuationResult | None:
    return db.scalar(
        select(SecurityValuationResult)
        .join(ValuationRun, SecurityValuationResult.run_id == ValuationRun.id)
        .where(ValuationRun.portfolio_id == portfolio_id)
        .where(SecurityValuationResult.symbol == symbol.upper())
        .order_by(desc(SecurityValuationResult.as_of_date), desc(SecurityValuationResult.id))
        .limit(1)
    )


def latest_analyst_snapshot(db: Session, symbol: str) -> SecurityAnalystSnapshot | None:
    return db.scalar(
        select(SecurityAnalystSnapshot)
        .where(SecurityAnalystSnapshot.symbol == symbol.upper())
        .order_by(desc(SecurityAnalystSnapshot.as_of_date), desc(SecurityAnalystSnapshot.fetched_at))
        .limit(1)
    )


def parse_security_valuation_result(row: SecurityValuationResult) -> dict[str, Any]:
    inputs = _json_loads(row.inputs_json, {})
    term_upsides = {}
    if isinstance(inputs, dict):
        raw = inputs.get("term_upsides")
        if isinstance(raw, dict):
            term_upsides = raw
    return {
        "symbol": row.symbol,
        "as_of_date": row.as_of_date,
        "model_status": row.model_status,
        "analyst_upside": row.analyst_upside,
        "dcf_fair_value": row.dcf_fair_value,
        "dcf_upside": term_upsides.get("dcf"),
        "ri_fair_value": row.ri_fair_value,
        "ri_upside": term_upsides.get("ri"),
        "ddm_fair_value": inputs.get("ddm_fair_value") if isinstance(inputs, dict) else None,
        "ddm_upside": term_upsides.get("ddm"),
        "relative_fair_value": row.relative_fair_value,
        "relative_upside": term_upsides.get("relative"),
        "composite_fair_value": row.composite_fair_value,
        "composite_upside": row.composite_upside,
        "confidence_low": row.confidence_low,
        "confidence_high": row.confidence_high,
        "inputs": inputs,
        "warnings": _json_loads(row.warnings_json, []),
    }


def parse_portfolio_valuation_summary(row: PortfolioValuationSnapshot) -> dict[str, Any]:
    summary = _json_loads(row.summary_json, {})
    return {
        "portfolio_id": row.portfolio_id,
        "snapshot_id": row.snapshot_id,
        "as_of_date": row.as_of_date,
        "weighted_analyst_upside": row.weighted_analyst_upside,
        "weighted_dcf_upside": summary.get("weighted_dcf_upside"),
        "weighted_ri_upside": summary.get("weighted_ri_upside"),
        "weighted_ddm_upside": summary.get("weighted_ddm_upside"),
        "weighted_relative_upside": summary.get("weighted_relative_upside"),
        "weighted_composite_upside": row.weighted_composite_upside,
        "coverage_ratio": row.coverage_ratio,
        "overvalued_weight": row.overvalued_weight,
        "undervalued_weight": row.undervalued_weight,
        "summary": summary,
    }
