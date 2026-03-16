from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    HoldingsPosition,
    HoldingsSnapshot,
    PortfolioExtendedMetricSnapshot,
    PortfolioValuationSnapshot,
    PortfolioMetricSnapshot,
    PositionRiskContribution,
    RefreshJob,
)
from app.services.metrics import compute_metrics
from app.services.metrics_extended import compute_extended_metrics
from app.services.portfolio import latest_snapshot
from app.services.pricing import get_symbols_price_frame
from app.services.scenarios import refresh_macro_cache_for_scenarios
from app.services.valuation import run_portfolio_valuation


@dataclass
class RefreshOutcome:
    job: RefreshJob
    metric_snapshot: PortfolioMetricSnapshot | None
    valuation_snapshot: PortfolioValuationSnapshot | None
    extended_metric_snapshot: PortfolioExtendedMetricSnapshot | None


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _create_metric_snapshot(
    db: Session,
    *,
    snapshot_id: int,
    metrics,
) -> PortfolioMetricSnapshot:
    existing = db.scalar(
        select(PortfolioMetricSnapshot)
        .where(PortfolioMetricSnapshot.snapshot_id == snapshot_id)
        .where(PortfolioMetricSnapshot.as_of_date == date.today())
        .where(PortfolioMetricSnapshot.window == "1Y")
        .limit(1)
    )

    if existing is None:
        metric_row = PortfolioMetricSnapshot(
            snapshot_id=snapshot_id,
            as_of_date=date.today(),
            window="1Y",
            portfolio_value=metrics.portfolio_value,
            ann_return=metrics.ann_return,
            ann_vol=metrics.ann_vol,
            sharpe=metrics.sharpe,
            sortino=metrics.sortino,
            max_drawdown=metrics.max_drawdown,
            var_95=metrics.var_95,
            cvar_95=metrics.cvar_95,
            beta=metrics.beta,
            top3_weight_share=metrics.top3_weight_share,
            hhi=metrics.hhi,
        )
        db.add(metric_row)
        db.flush()
    else:
        metric_row = existing
        metric_row.portfolio_value = metrics.portfolio_value
        metric_row.ann_return = metrics.ann_return
        metric_row.ann_vol = metrics.ann_vol
        metric_row.sharpe = metrics.sharpe
        metric_row.sortino = metrics.sortino
        metric_row.max_drawdown = metrics.max_drawdown
        metric_row.var_95 = metrics.var_95
        metric_row.cvar_95 = metrics.cvar_95
        metric_row.beta = metrics.beta
        metric_row.top3_weight_share = metrics.top3_weight_share
        metric_row.hhi = metrics.hhi

    db.execute(delete(PositionRiskContribution).where(PositionRiskContribution.snapshot_id == snapshot_id))

    for c in metrics.contributions:
        db.add(
            PositionRiskContribution(
                snapshot_id=snapshot_id,
                symbol=c.symbol,
                marginal_risk=c.marginal_risk,
                component_risk=c.component_risk,
                pct_total_risk=c.pct_total_risk,
            )
        )

    db.flush()
    return metric_row


def _create_extended_metric_snapshot(
    db: Session,
    *,
    snapshot_id: int,
    benchmark_symbol: str,
    metrics_payload: dict[str, object],
    warnings: list[str],
) -> PortfolioExtendedMetricSnapshot:
    existing = db.scalar(
        select(PortfolioExtendedMetricSnapshot)
        .where(PortfolioExtendedMetricSnapshot.snapshot_id == snapshot_id)
        .where(PortfolioExtendedMetricSnapshot.as_of_date == date.today())
        .where(PortfolioExtendedMetricSnapshot.window == "5Y")
        .limit(1)
    )
    if existing is None:
        row = PortfolioExtendedMetricSnapshot(
            snapshot_id=snapshot_id,
            as_of_date=date.today(),
            window="5Y",
            benchmark_symbol=benchmark_symbol.upper(),
            metrics_json=_json_dumps(metrics_payload),
            warnings_json=_json_dumps(sorted(set(warnings))),
        )
        db.add(row)
        db.flush()
        return row

    existing.benchmark_symbol = benchmark_symbol.upper()
    existing.metrics_json = _json_dumps(metrics_payload)
    existing.warnings_json = _json_dumps(sorted(set(warnings)))
    db.flush()
    return existing


def run_refresh_for_portfolio(db: Session, portfolio_id: int, trigger_type: str = "manual") -> RefreshOutcome:
    job = RefreshJob(
        portfolio_id=portfolio_id,
        trigger_type=trigger_type,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        snapshot = latest_snapshot(db, portfolio_id)
        if snapshot is None:
            raise ValueError("No holdings snapshot found for portfolio.")

        positions = list(
            db.scalars(
                select(HoldingsPosition)
                .where(HoldingsPosition.snapshot_id == snapshot.id)
                .order_by(HoldingsPosition.weight.desc())
            )
        )
        if not positions:
            raise ValueError("Latest holdings snapshot has no positions.")

        symbols = [p.symbol.upper() for p in positions]

        end_date = date.today()
        extended_start_date = end_date - timedelta(days=365 * 6)
        one_year_start = end_date - timedelta(days=366)

        full_price_frame = get_symbols_price_frame(db, symbols, extended_start_date, end_date)
        price_frame = full_price_frame.copy()

        benchmark_symbol = snapshot.portfolio.benchmark_symbol.upper()
        benchmark_df = get_symbols_price_frame(db, [benchmark_symbol], extended_start_date, end_date)
        if benchmark_df.empty:
            raise ValueError(f"No benchmark price history found for {benchmark_symbol}.")
        benchmark_prices = (
            benchmark_df[benchmark_symbol]
            if benchmark_symbol in benchmark_df.columns
            else benchmark_df.iloc[:, 0]
        )
        full_benchmark_prices = benchmark_prices.copy()

        cutoff_ts = pd.Timestamp(one_year_start)
        price_frame = price_frame[price_frame.index >= cutoff_ts]
        benchmark_prices = benchmark_prices[benchmark_prices.index >= cutoff_ts]

        metrics = compute_metrics(
            holdings=positions,
            price_frame=price_frame,
            benchmark_prices=benchmark_prices,
            risk_free_rate=settings.risk_free_rate,
        )

        metric_snapshot = _create_metric_snapshot(db, snapshot_id=snapshot.id, metrics=metrics)
        valuation_outcome = run_portfolio_valuation(
            db,
            portfolio_id=portfolio_id,
            snapshot_id=snapshot.id,
            trigger_type=trigger_type,
        )
        valuation_snapshot = valuation_outcome.portfolio_snapshot

        extended_snapshot: PortfolioExtendedMetricSnapshot | None = None
        extended_warnings: list[str] = []
        scenario_warnings: list[str] = []
        try:
            extended = compute_extended_metrics(
                holdings=positions,
                price_frame=full_price_frame,
                benchmark_prices=full_benchmark_prices,
                risk_free_rate=settings.risk_free_rate,
                benchmark_symbol=benchmark_symbol,
                db=db,
                as_of_date=end_date,
            )
            extended_snapshot = _create_extended_metric_snapshot(
                db,
                snapshot_id=snapshot.id,
                benchmark_symbol=benchmark_symbol,
                metrics_payload=extended.metrics,
                warnings=extended.warnings,
            )
            extended_warnings.extend(extended.warnings)
        except Exception as ext_exc:
            extended_warnings.append(f"extended_metrics_failed:{ext_exc.__class__.__name__}")

        try:
            scenario_warnings.extend(refresh_macro_cache_for_scenarios(db, portfolio_id=portfolio_id))
        except Exception as scen_exc:
            scenario_warnings.append(f"scenario_cache_failed:{scen_exc.__class__.__name__}")

        job.status = "completed"
        job.finished_at = datetime.utcnow()
        job.error = None
        all_warnings: list[str] = []
        if valuation_outcome.run.status != "completed":
            job.status = "completed_with_warnings"
            all_warnings.append(f"valuation_run_status={valuation_outcome.run.status}")
        if valuation_outcome.warnings:
            all_warnings.extend(valuation_outcome.warnings)
        if extended_warnings:
            all_warnings.extend(extended_warnings)
        if scenario_warnings:
            all_warnings.extend(scenario_warnings)
        if all_warnings:
            job.status = "completed_with_warnings"
            job.error = "; ".join(sorted(set(all_warnings)))

        db.commit()
        db.refresh(job)
        db.refresh(metric_snapshot)
        if valuation_snapshot is not None:
            db.refresh(valuation_snapshot)
        if extended_snapshot is not None:
            db.refresh(extended_snapshot)
        return RefreshOutcome(
            job=job,
            metric_snapshot=metric_snapshot,
            valuation_snapshot=valuation_snapshot,
            extended_metric_snapshot=extended_snapshot,
        )
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return RefreshOutcome(
            job=job,
            metric_snapshot=None,
            valuation_snapshot=None,
            extended_metric_snapshot=None,
        )


def run_nightly_refresh(db: Session) -> list[RefreshOutcome]:
    portfolio_ids = list(db.scalars(select(HoldingsSnapshot.portfolio_id).distinct()))
    outcomes: list[RefreshOutcome] = []
    for portfolio_id in portfolio_ids:
        outcomes.append(run_refresh_for_portfolio(db, portfolio_id, trigger_type="nightly"))
    return outcomes
