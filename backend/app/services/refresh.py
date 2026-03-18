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
    PortfolioExtendedMetricSnapshot,
    PortfolioMetricSnapshot,
    PortfolioValuationSnapshot,
    PositionRiskContribution,
    RefreshJob,
    ValuationRun,
)
from app.services.exposures import build_portfolio_exposure_snapshot
from app.services.metrics import compute_metrics
from app.services.metrics_extended import compute_extended_metrics
from app.services.narratives import (
    build_narrative_payload,
    persist_portfolio_narrative,
    previous_narrative_payload,
)
from app.services.portfolio import latest_scenario_run, latest_snapshot
from app.services.pricing import get_symbols_price_frame
from app.services.scenarios import refresh_macro_cache_for_scenarios
from app.services.valuation import run_portfolio_valuation


@dataclass
class RefreshOutcome:
    job: RefreshJob
    metric_snapshot: PortfolioMetricSnapshot | None
    valuation_snapshot: PortfolioValuationSnapshot | None
    extended_metric_snapshot: PortfolioExtendedMetricSnapshot | None


class RefreshBusyError(RuntimeError):
    pass


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _create_metric_snapshot(db: Session, *, snapshot_id: int, metrics) -> PortfolioMetricSnapshot:
    existing = db.scalar(
        select(PortfolioMetricSnapshot)
        .where(PortfolioMetricSnapshot.snapshot_id == snapshot_id)
        .where(PortfolioMetricSnapshot.as_of_date == date.today())
        .where(PortfolioMetricSnapshot.window == "1Y")
        .limit(1)
    )
    if existing is None:
        existing = PortfolioMetricSnapshot(snapshot_id=snapshot_id, as_of_date=date.today(), window="1Y", portfolio_value=0.0, ann_return=0.0, ann_vol=0.0, sharpe=0.0, sortino=0.0, max_drawdown=0.0, var_95=0.0, cvar_95=0.0, beta=0.0, top3_weight_share=0.0, hhi=0.0)
        db.add(existing)
        db.flush()

    existing.portfolio_value = metrics.portfolio_value
    existing.ann_return = metrics.ann_return
    existing.ann_vol = metrics.ann_vol
    existing.sharpe = metrics.sharpe
    existing.sortino = metrics.sortino
    existing.max_drawdown = metrics.max_drawdown
    existing.var_95 = metrics.var_95
    existing.cvar_95 = metrics.cvar_95
    existing.beta = metrics.beta
    existing.top3_weight_share = metrics.top3_weight_share
    existing.hhi = metrics.hhi

    db.execute(delete(PositionRiskContribution).where(PositionRiskContribution.snapshot_id == snapshot_id))
    for c in metrics.contributions:
        db.add(PositionRiskContribution(snapshot_id=snapshot_id, symbol=c.symbol, marginal_risk=c.marginal_risk, component_risk=c.component_risk, pct_total_risk=c.pct_total_risk))
    db.flush()
    return existing


def _create_extended_metric_snapshot(db: Session, *, snapshot_id: int, benchmark_symbol: str, metrics_payload: dict[str, object], warnings: list[str]) -> PortfolioExtendedMetricSnapshot:
    existing = db.scalar(
        select(PortfolioExtendedMetricSnapshot)
        .where(PortfolioExtendedMetricSnapshot.snapshot_id == snapshot_id)
        .where(PortfolioExtendedMetricSnapshot.as_of_date == date.today())
        .where(PortfolioExtendedMetricSnapshot.window == "5Y")
        .limit(1)
    )
    if existing is None:
        existing = PortfolioExtendedMetricSnapshot(snapshot_id=snapshot_id, as_of_date=date.today(), window="5Y", benchmark_symbol=benchmark_symbol.upper(), metrics_json="{}", warnings_json="[]")
        db.add(existing)
    existing.benchmark_symbol = benchmark_symbol.upper()
    existing.metrics_json = _json_dumps(metrics_payload)
    existing.warnings_json = _json_dumps(sorted(set(warnings)))
    db.flush()
    return existing


def _assert_refresh_not_busy(db: Session, portfolio_id: int) -> None:
    running_refresh = db.scalar(
        select(RefreshJob)
        .where(RefreshJob.portfolio_id == portfolio_id)
        .where(RefreshJob.status == "running")
        .limit(1)
    )
    if running_refresh is not None:
        raise RefreshBusyError("A refresh job is already running for this portfolio.")
    running_valuation = db.scalar(
        select(ValuationRun)
        .where(ValuationRun.portfolio_id == portfolio_id)
        .where(ValuationRun.status == "running")
        .limit(1)
    )
    if running_valuation is not None:
        raise RefreshBusyError("A valuation job is already running for this portfolio.")


def run_refresh_for_portfolio(db: Session, portfolio_id: int, trigger_type: str = "manual") -> RefreshOutcome:
    _assert_refresh_not_busy(db, portfolio_id)
    job = RefreshJob(portfolio_id=portfolio_id, trigger_type=trigger_type, status="running", started_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        snapshot = latest_snapshot(db, portfolio_id)
        if snapshot is None:
            raise ValueError("No holdings snapshot found for portfolio.")

        positions = list(db.scalars(select(HoldingsPosition).where(HoldingsPosition.snapshot_id == snapshot.id).order_by(HoldingsPosition.weight.desc())))
        if not positions:
            raise ValueError("Latest holdings snapshot has no positions.")

        symbols = [p.symbol.upper() for p in positions]
        end_date = date.today()
        extended_start_date = end_date - timedelta(days=365 * 6)
        one_year_start = end_date - timedelta(days=366)
        full_price_frame = get_symbols_price_frame(db, symbols, extended_start_date, end_date)
        benchmark_symbol = snapshot.portfolio.benchmark_symbol.upper()
        benchmark_df = get_symbols_price_frame(db, [benchmark_symbol], extended_start_date, end_date)
        if benchmark_df.empty:
            raise ValueError(f"No benchmark price history found for {benchmark_symbol}.")
        benchmark_prices = benchmark_df[benchmark_symbol] if benchmark_symbol in benchmark_df.columns else benchmark_df.iloc[:, 0]
        cutoff_ts = pd.Timestamp(one_year_start)
        price_frame = full_price_frame[full_price_frame.index >= cutoff_ts]
        benchmark_one_year = benchmark_prices[benchmark_prices.index >= cutoff_ts]

        metrics = compute_metrics(holdings=positions, price_frame=price_frame, benchmark_prices=benchmark_one_year, risk_free_rate=settings.risk_free_rate)
        metric_snapshot = _create_metric_snapshot(db, snapshot_id=snapshot.id, metrics=metrics)

        valuation_outcome = run_portfolio_valuation(db, portfolio_id=portfolio_id, snapshot_id=snapshot.id, trigger_type=trigger_type)
        valuation_snapshot = valuation_outcome.portfolio_snapshot

        extended_snapshot = None
        extended_warnings: list[str] = []
        exposure_warnings: list[str] = []
        scenario_warnings: list[str] = []
        narrative_warnings: list[str] = []

        try:
            extended = compute_extended_metrics(holdings=positions, price_frame=full_price_frame, benchmark_prices=benchmark_prices.copy(), risk_free_rate=settings.risk_free_rate, benchmark_symbol=benchmark_symbol, db=db, as_of_date=end_date)
            extended_snapshot = _create_extended_metric_snapshot(db, snapshot_id=snapshot.id, benchmark_symbol=benchmark_symbol, metrics_payload=extended.metrics, warnings=extended.warnings)
            extended_warnings.extend(extended.warnings)
        except Exception as ext_exc:  # pragma: no cover - defensive
            extended_warnings.append(f"extended_metrics_failed:{ext_exc.__class__.__name__}")

        exposure_summary = None
        try:
            exposure_result = build_portfolio_exposure_snapshot(db, portfolio_id=portfolio_id, snapshot=snapshot, positions=positions)
            exposure_summary = exposure_result.summary
            exposure_warnings.extend(exposure_result.warnings)
        except Exception as exposure_exc:  # pragma: no cover - defensive
            exposure_warnings.append(f"exposure_snapshot_failed:{exposure_exc.__class__.__name__}")

        try:
            previous_payload = previous_narrative_payload(db, portfolio_id, exclude_snapshot_id=snapshot.id)
            narrative_payload = build_narrative_payload(positions=positions, exposure_summary=exposure_summary, metrics=metric_snapshot, valuation_summary=valuation_snapshot, latest_scenario=latest_scenario_run(db, portfolio_id), previous_payload=previous_payload)
            persist_portfolio_narrative(db, portfolio_id=portfolio_id, snapshot=snapshot, payload=narrative_payload)
            narrative_warnings.extend(narrative_payload.get("warnings", []))
        except Exception as narrative_exc:  # pragma: no cover - defensive
            narrative_warnings.append(f"narrative_build_failed:{narrative_exc.__class__.__name__}")

        try:
            scenario_warnings.extend(refresh_macro_cache_for_scenarios(db, portfolio_id=portfolio_id))
        except Exception as scen_exc:
            scenario_warnings.append(f"scenario_cache_failed:{scen_exc.__class__.__name__}")

        all_warnings: list[str] = []
        if valuation_outcome.run.status != "completed":
            all_warnings.append(f"valuation_run_status={valuation_outcome.run.status}")
        all_warnings.extend(valuation_outcome.warnings)
        all_warnings.extend(extended_warnings)
        all_warnings.extend(exposure_warnings)
        all_warnings.extend(narrative_warnings)
        all_warnings.extend(scenario_warnings)

        job.status = "completed_with_warnings" if all_warnings else "completed"
        job.finished_at = datetime.utcnow()
        job.error = "; ".join(sorted(set(all_warnings))) if all_warnings else None

        db.commit()
        db.refresh(job)
        db.refresh(metric_snapshot)
        if valuation_snapshot is not None:
            db.refresh(valuation_snapshot)
        if extended_snapshot is not None:
            db.refresh(extended_snapshot)
        return RefreshOutcome(job=job, metric_snapshot=metric_snapshot, valuation_snapshot=valuation_snapshot, extended_metric_snapshot=extended_snapshot)
    except Exception as exc:
        db.rollback()
        job = db.get(RefreshJob, job.id) or job
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.error = str(exc)
        db.add(job)
        db.commit()
        db.refresh(job)
        raise


def run_nightly_refresh(db: Session) -> list[RefreshOutcome]:
    from app.models import Portfolio

    outcomes: list[RefreshOutcome] = []
    portfolios = list(db.scalars(select(Portfolio).order_by(Portfolio.id.asc())))
    for portfolio in portfolios:
        snapshot = latest_snapshot(db, portfolio.id)
        if snapshot is None:
            continue
        try:
            outcomes.append(run_refresh_for_portfolio(db, portfolio.id, trigger_type="nightly"))
        except RefreshBusyError:
            db.rollback()
            continue
    return outcomes
