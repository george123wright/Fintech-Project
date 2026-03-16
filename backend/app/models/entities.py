from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    benchmark_symbol: Mapped[str] = mapped_column(String(16), nullable=False, default="SPY")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    uploads: Mapped[list[PortfolioUpload]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    snapshots: Mapped[list[HoldingsSnapshot]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    refresh_jobs: Mapped[list[RefreshJob]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    valuation_runs: Mapped[list[ValuationRun]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    valuation_snapshots: Mapped[list[PortfolioValuationSnapshot]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )
    scenario_runs: Mapped[list[ScenarioRun]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )
    scenario_portfolio_results: Mapped[list[ScenarioRunPortfolio]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )


class PortfolioUpload(Base):
    __tablename__ = "portfolio_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")

    portfolio: Mapped[Portfolio] = relationship(back_populates="uploads")
    snapshots: Mapped[list[HoldingsSnapshot]] = relationship(back_populates="upload")


class HoldingsSnapshot(Base):
    __tablename__ = "holdings_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("portfolio_uploads.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="snapshots")
    upload: Mapped[PortfolioUpload | None] = relationship(back_populates="snapshots")
    positions: Mapped[list[HoldingsPosition]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
    metric_snapshots: Mapped[list[PortfolioMetricSnapshot]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
    extended_metric_snapshots: Mapped[list[PortfolioExtendedMetricSnapshot]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )
    risk_contributions: Mapped[list[PositionRiskContribution]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
    valuation_runs: Mapped[list[ValuationRun]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
    valuation_snapshots: Mapped[list[PortfolioValuationSnapshot]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )
    scenario_runs: Mapped[list[ScenarioRun]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class HoldingsPosition(Base):
    __tablename__ = "holdings_positions"
    __table_args__ = (UniqueConstraint("snapshot_id", "symbol", name="uq_snapshot_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    units: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_value: Mapped[float] = mapped_column(Float, nullable=False)
    cost_basis: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    snapshot: Mapped[HoldingsSnapshot] = relationship(back_populates="positions")


class SecurityPriceDaily(Base):
    __tablename__ = "security_prices_daily"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    adj_close: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class PortfolioMetricSnapshot(Base):
    __tablename__ = "portfolio_metric_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_id", "as_of_date", "window", name="uq_metric_snapshot_window"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    window: Mapped[str] = mapped_column(String(16), nullable=False, default="1Y")
    portfolio_value: Mapped[float] = mapped_column(Float, nullable=False)
    ann_return: Mapped[float] = mapped_column(Float, nullable=False)
    ann_vol: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe: Mapped[float] = mapped_column(Float, nullable=False)
    sortino: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    var_95: Mapped[float] = mapped_column(Float, nullable=False)
    cvar_95: Mapped[float] = mapped_column(Float, nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)
    top3_weight_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hhi: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    snapshot: Mapped[HoldingsSnapshot] = relationship(back_populates="metric_snapshots")


class PortfolioExtendedMetricSnapshot(Base):
    __tablename__ = "portfolio_extended_metric_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "as_of_date", "window", name="uq_ext_metric_snapshot_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window: Mapped[str] = mapped_column(String(16), nullable=False, default="5Y")
    benchmark_symbol: Mapped[str] = mapped_column(String(16), nullable=False, default="SPY")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    snapshot: Mapped[HoldingsSnapshot] = relationship(back_populates="extended_metric_snapshots")


class PositionRiskContribution(Base):
    __tablename__ = "position_risk_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False)
    marginal_risk: Mapped[float] = mapped_column(Float, nullable=False)
    component_risk: Mapped[float] = mapped_column(Float, nullable=False)
    pct_total_risk: Mapped[float] = mapped_column(Float, nullable=False)

    snapshot: Mapped[HoldingsSnapshot] = relationship(back_populates="risk_contributions")


class RefreshJob(Base):
    __tablename__ = "refresh_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    portfolio: Mapped[Portfolio] = relationship(back_populates="refresh_jobs")


class SecurityAnalystSnapshot(Base):
    __tablename__ = "security_analyst_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "as_of_date", name="uq_security_analyst_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyst_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommendation_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class SecurityFundamentalSnapshot(Base):
    __tablename__ = "security_fundamental_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "as_of_date", name="uq_security_fund_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cashflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    book_value_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class SecurityForwardEstimateSnapshot(Base):
    __tablename__ = "security_forward_estimate_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "as_of_date", name="uq_security_forward_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fy0_revenue_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy0_revenue_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy0_revenue_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy1_revenue_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy1_revenue_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy1_revenue_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy0_eps_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy0_eps_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy0_eps_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy1_eps_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy1_eps_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    fy1_eps_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_analyst_count_fy0: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue_analyst_count_fy1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eps_analyst_count_fy0: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eps_analyst_count_fy1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ValuationRun(Base):
    __tablename__ = "valuation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    portfolio: Mapped[Portfolio] = relationship(back_populates="valuation_runs")
    snapshot: Mapped[HoldingsSnapshot] = relationship(back_populates="valuation_runs")
    security_results: Mapped[list[SecurityValuationResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    portfolio_snapshots: Mapped[list[PortfolioValuationSnapshot]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    dcf_details: Mapped[list[ValuationDcfDetail]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    ri_details: Mapped[list[ValuationRiDetail]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    ddm_details: Mapped[list[ValuationDdmDetail]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class SecurityValuationResult(Base):
    __tablename__ = "security_valuation_results"
    __table_args__ = (UniqueConstraint("run_id", "symbol", name="uq_security_valuation_run_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("valuation_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model_status: Mapped[str] = mapped_column(String(32), nullable=False, default="partial")
    analyst_upside: Mapped[float | None] = mapped_column(Float, nullable=True)
    dcf_fair_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    ri_fair_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_fair_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_fair_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_upside: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    inputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ValuationRun] = relationship(back_populates="security_results")


class PortfolioValuationSnapshot(Base):
    __tablename__ = "portfolio_valuation_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "portfolio_id", "snapshot_id", name="uq_portfolio_valuation_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("valuation_runs.id"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    weighted_analyst_upside: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_composite_upside: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overvalued_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    undervalued_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    run: Mapped[ValuationRun] = relationship(back_populates="portfolio_snapshots")
    portfolio: Mapped[Portfolio] = relationship(back_populates="valuation_snapshots")
    snapshot: Mapped[HoldingsSnapshot] = relationship(back_populates="valuation_snapshots")


class ValuationDcfDetail(Base):
    __tablename__ = "valuation_dcf_details"
    __table_args__ = (UniqueConstraint("run_id", "symbol", "scenario_key", name="uq_valuation_dcf_run_symbol_scenario"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("valuation_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scenario_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="base")
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    forecast_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    diagnostics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ValuationRun] = relationship(back_populates="dcf_details")


class ValuationRiDetail(Base):
    __tablename__ = "valuation_ri_details"
    __table_args__ = (UniqueConstraint("run_id", "symbol", "scenario_key", name="uq_valuation_ri_run_symbol_scenario"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("valuation_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scenario_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="base")
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    forecast_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    diagnostics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ValuationRun] = relationship(back_populates="ri_details")


class ValuationDdmDetail(Base):
    __tablename__ = "valuation_ddm_details"
    __table_args__ = (UniqueConstraint("run_id", "symbol", "scenario_key", name="uq_valuation_ddm_run_symbol_scenario"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("valuation_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scenario_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="base")
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    forecast_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    diagnostics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ValuationRun] = relationship(back_populates="ddm_details")


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("holdings_snapshots.id"), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    factor_key: Mapped[str] = mapped_column(String(48), nullable=False)
    shock_value: Mapped[float] = mapped_column(Float, nullable=False)
    shock_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    n_sims: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    selected_symbol: Mapped[str | None] = mapped_column(String(24), nullable=True)
    include_baseline: Mapped[bool] = mapped_column(nullable=False, default=True)
    shrinkage_lambda: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="scenario_v1")

    portfolio: Mapped[Portfolio] = relationship(back_populates="scenario_runs")
    snapshot: Mapped[HoldingsSnapshot | None] = relationship(back_populates="scenario_runs")
    symbol_results: Mapped[list[ScenarioRunResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    portfolio_result: Mapped[ScenarioRunPortfolio | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )
    distribution_bins: Mapped[list[ScenarioRunDistributionBin]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    narratives: Mapped[list[ScenarioRunNarrative]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ScenarioRunResult(Base):
    __tablename__ = "scenario_run_results"
    __table_args__ = (UniqueConstraint("run_id", "symbol", name="uq_scenario_run_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scenario_runs.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    expected_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    shock_only_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    shock_only_value_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_mean_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_median_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_std_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantile_low_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantile_high_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    relationship_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    simulation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ScenarioRun] = relationship(back_populates="symbol_results")


class ScenarioRunPortfolio(Base):
    __tablename__ = "scenario_run_portfolio"
    __table_args__ = (UniqueConstraint("run_id", name="uq_scenario_run_portfolio"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scenario_runs.id"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    expected_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    shock_only_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    shock_only_value_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_mean_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_median_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_std_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantile_low_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantile_high_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    relationship_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    simulation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ScenarioRun] = relationship(back_populates="portfolio_result")
    portfolio: Mapped[Portfolio] = relationship(back_populates="scenario_portfolio_results")


class ScenarioRunDistributionBin(Base):
    __tablename__ = "scenario_run_distribution_bins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scenario_runs.id"), nullable=False, index=True)
    series_key: Mapped[str] = mapped_column(String(32), nullable=False, default="portfolio")
    bin_index: Mapped[int] = mapped_column(Integer, nullable=False)
    bin_start: Mapped[float] = mapped_column(Float, nullable=False)
    bin_end: Mapped[float] = mapped_column(Float, nullable=False)
    density: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    run: Mapped[ScenarioRun] = relationship(back_populates="distribution_bins")


class ScenarioRunNarrative(Base):
    __tablename__ = "scenario_run_narratives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scenario_runs.id"), nullable=False, index=True)
    block_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[ScenarioRun] = relationship(back_populates="narratives")


class MacroSeriesObservation(Base):
    __tablename__ = "macro_series_observations"
    __table_args__ = (UniqueConstraint("series_id", "observation_date", name="uq_macro_series_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="fred")


class MacroFactorSnapshot(Base):
    __tablename__ = "macro_factor_snapshots"
    __table_args__ = (UniqueConstraint("as_of_date", name="uq_macro_factor_asof"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
