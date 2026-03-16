from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    HoldingsSnapshot,
    Portfolio,
    PortfolioExtendedMetricSnapshot,
    PortfolioMetricSnapshot,
    PortfolioValuationSnapshot,
    RefreshJob,
    ScenarioRun,
    ValuationRun,
)


def list_portfolios(db: Session) -> list[Portfolio]:
    return list(db.scalars(select(Portfolio).order_by(Portfolio.created_at.asc())))


def create_portfolio(
    db: Session,
    *,
    name: str,
    base_currency: str,
    benchmark_symbol: str,
) -> Portfolio:
    portfolio = Portfolio(
        name=name,
        base_currency=base_currency.upper(),
        benchmark_symbol=benchmark_symbol.upper(),
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def ensure_default_portfolio(db: Session) -> Portfolio:
    existing = db.scalar(select(Portfolio).order_by(Portfolio.id.asc()).limit(1))
    if existing is not None:
        return existing

    portfolio = Portfolio(
        name="My Portfolio",
        base_currency=settings.default_base_ccy,
        benchmark_symbol=settings.default_benchmark,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def get_portfolio_or_404(db: Session, portfolio_id: int) -> Portfolio | None:
    return db.get(Portfolio, portfolio_id)


def latest_snapshot(db: Session, portfolio_id: int) -> HoldingsSnapshot | None:
    return db.scalar(
        select(HoldingsSnapshot)
        .where(HoldingsSnapshot.portfolio_id == portfolio_id)
        .order_by(HoldingsSnapshot.as_of_date.desc(), HoldingsSnapshot.created_at.desc())
        .limit(1)
    )


def latest_metrics_for_snapshot(db: Session, snapshot_id: int) -> PortfolioMetricSnapshot | None:
    return db.scalar(
        select(PortfolioMetricSnapshot)
        .where(PortfolioMetricSnapshot.snapshot_id == snapshot_id)
        .order_by(PortfolioMetricSnapshot.as_of_date.desc(), PortfolioMetricSnapshot.created_at.desc())
        .limit(1)
    )


def latest_extended_metrics_for_snapshot(
    db: Session,
    snapshot_id: int,
) -> PortfolioExtendedMetricSnapshot | None:
    return db.scalar(
        select(PortfolioExtendedMetricSnapshot)
        .where(PortfolioExtendedMetricSnapshot.snapshot_id == snapshot_id)
        .order_by(
            PortfolioExtendedMetricSnapshot.as_of_date.desc(),
            PortfolioExtendedMetricSnapshot.created_at.desc(),
        )
        .limit(1)
    )


def latest_refresh_job(db: Session, portfolio_id: int) -> RefreshJob | None:
    return db.scalar(
        select(RefreshJob)
        .where(RefreshJob.portfolio_id == portfolio_id)
        .order_by(desc(RefreshJob.started_at))
        .limit(1)
    )


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
        .order_by(
            PortfolioValuationSnapshot.as_of_date.desc(),
            PortfolioValuationSnapshot.id.desc(),
        )
        .limit(1)
    )


def latest_scenario_run(db: Session, portfolio_id: int) -> ScenarioRun | None:
    return db.scalar(
        select(ScenarioRun)
        .where(ScenarioRun.portfolio_id == portfolio_id)
        .order_by(desc(ScenarioRun.started_at), desc(ScenarioRun.id))
        .limit(1)
    )
