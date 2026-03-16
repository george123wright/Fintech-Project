from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class DcfAssumptionsIn(BaseModel):
    terminal_growth: float = Field(default=0.025, ge=-0.02, le=0.08)
    discount_rate: float | None = Field(default=None, ge=0.01, le=0.4)
    explicit_years: int = Field(default=7, ge=5, le=10)
    rf: float = Field(default=0.02, ge=0.0, le=0.2)
    erp: float = Field(default=0.05, ge=0.0, le=0.25)
    anchor_mode: str = Field(default="revenue_only")
    tv_method: str = Field(default="blended")
    tv_blend_weight: float = Field(default=0.65, ge=0.0, le=1.0)
    steady_state_growth: float = Field(default=0.025, ge=-0.02, le=0.08)
    reinvestment_blend_weight: float = Field(default=0.50, ge=0.0, le=1.0)
    fallback_rev_spread: float = Field(default=0.10, ge=0.01, le=1.0)
    fallback_eps_spread: float = Field(default=0.15, ge=0.01, le=1.0)
    terminal_clip_buffer: float = Field(default=0.02, ge=0.0, le=0.1)
    quality_penalty_enabled: bool = Field(default=True)


class RiAssumptionsIn(BaseModel):
    explicit_years: int = Field(default=7, ge=5, le=10)
    anchor_mode: str = Field(default="revenue_eps_consistency")
    terminal_method: str = Field(default="blended")
    terminal_blend_weight: float = Field(default=0.65, ge=0.0, le=1.0)
    steady_state_growth: float = Field(default=0.025, ge=-0.02, le=0.08)
    long_run_roe: float = Field(default=0.12, ge=0.0, le=0.6)
    long_run_payout: float = Field(default=0.35, ge=0.0, le=0.95)
    payout_smoothing_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    fade_years_post_horizon: int = Field(default=8, ge=3, le=15)
    fallback_rev_spread: float = Field(default=0.10, ge=0.01, le=1.0)
    fallback_eps_spread: float = Field(default=0.15, ge=0.01, le=1.0)
    terminal_clip_buffer: float = Field(default=0.02, ge=0.0, le=0.1)
    quality_penalty_enabled: bool = Field(default=True)
    cost_of_equity: float | None = Field(default=None, ge=0.01, le=0.4)


class DdmAssumptionsIn(BaseModel):
    explicit_years: int = Field(default=7, ge=5, le=10)
    anchor_mode: str = Field(default="eps_payout_linked")
    coverage_mode: str = Field(default="hybrid_eps_payout")
    terminal_method: str = Field(default="two_stage_gordon")
    steady_state_growth: float = Field(default=0.025, ge=-0.02, le=0.08)
    long_run_payout: float = Field(default=0.35, ge=0.0, le=0.95)
    payout_smoothing_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    initiation_payout_floor: float = Field(default=0.08, ge=0.0, le=0.5)
    payout_cap: float = Field(default=0.90, ge=0.3, le=1.2)
    fallback_eps_spread: float = Field(default=0.15, ge=0.01, le=1.0)
    fallback_payout_spread: float = Field(default=0.10, ge=0.0, le=0.5)
    terminal_clip_buffer: float = Field(default=0.02, ge=0.0, le=0.1)
    quality_penalty_enabled: bool = Field(default=True)
    cost_of_equity: float | None = Field(default=None, ge=0.01, le=0.4)


class RelativeAssumptionsIn(BaseModel):
    peer_set: str = Field(default="sector")
    multiples: list[str] = Field(default_factory=lambda: ["forward_pe", "pb", "ev_ebitda"])
    cap_upside: float = Field(default=0.6, ge=0.0, le=2.0)


class ValuationAssumptionsIn(BaseModel):
    dcf: DcfAssumptionsIn = Field(default_factory=DcfAssumptionsIn)
    ri: RiAssumptionsIn = Field(default_factory=RiAssumptionsIn)
    ddm: DdmAssumptionsIn = Field(default_factory=DdmAssumptionsIn)
    relative: RelativeAssumptionsIn = Field(default_factory=RelativeAssumptionsIn)


class ValuationRunOut(BaseModel):
    id: int
    portfolio_id: int
    snapshot_id: int
    trigger_type: str
    status: str
    assumptions_json: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None

    model_config = {"from_attributes": True}


class AnalystLatestResponse(BaseModel):
    symbol: str
    as_of_date: date | None
    current_price: float | None
    target_mean: float | None
    target_high: float | None
    target_low: float | None
    analyst_count: int | None
    recommendation_key: str | None
    recommendation_mean: float | None
    analyst_upside: float | None
    status: str
    warnings: list[str] = Field(default_factory=list)


class AnalystPriceTargetSnapshot(BaseModel):
    as_of_date: date | None = None
    current: float | None = None
    high: float | None = None
    low: float | None = None
    mean: float | None = None
    median: float | None = None


class AnalystCoverageDetail(BaseModel):
    analyst_count: int | None = None
    recommendation_key: str | None = None
    recommendation_mean: float | None = None


class AnalystTargetScenario(BaseModel):
    label: str
    target: float | None = None
    return_pct: float | None = None


class RecommendationBucket(BaseModel):
    label: str
    count: int


class ShareholderBreakdownItem(BaseModel):
    label: str
    value: float | None = None
    display_value: str | None = None


class InstitutionalHolderOut(BaseModel):
    date_reported: date | None = None
    holder: str
    pct_held: float | None = None
    shares: float | None = None
    value: float | None = None
    pct_change: float | None = None


class SecurityOverviewResponse(BaseModel):
    symbol: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    name: str | None = None
    description: str | None = None
    industry: str | None = None
    sector: str | None = None
    country: str | None = None
    full_address: str | None = None
    website: str | None = None
    market_cap: float | None = None
    current_price: float | None = None
    daily_return: float | None = None
    ytd_return: float | None = None
    one_year_return: float | None = None
    beta: float | None = None
    pe: float | None = None
    dividend_yield: float | None = None
    shareholder_breakdown: list[ShareholderBreakdownItem] = Field(default_factory=list)
    institutional_holders: list[InstitutionalHolderOut] = Field(default_factory=list)


class SecurityFinancialStatementsResponse(BaseModel):
    symbol: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    income_statement_annual: list[dict[str, Any]] = Field(default_factory=list)
    income_statement_quarterly: list[dict[str, Any]] = Field(default_factory=list)
    balance_sheet_annual: list[dict[str, Any]] = Field(default_factory=list)
    balance_sheet_quarterly: list[dict[str, Any]] = Field(default_factory=list)
    cashflow_annual: list[dict[str, Any]] = Field(default_factory=list)
    cashflow_quarterly: list[dict[str, Any]] = Field(default_factory=list)


class FinancialRatioMetricOut(BaseModel):
    key: str
    label: str
    category: str
    unit: str
    value: float | None = None
    source: str
    description: str


class SecurityFinancialRatiosResponse(BaseModel):
    symbol: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    annual: list[FinancialRatioMetricOut] = Field(default_factory=list)
    quarterly: list[FinancialRatioMetricOut] = Field(default_factory=list)


class AnalystDetailResponse(BaseModel):
    symbol: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    snapshot: AnalystPriceTargetSnapshot
    coverage: AnalystCoverageDetail
    target_scenarios: list[AnalystTargetScenario] = Field(default_factory=list)
    current_recommendations: list[RecommendationBucket] = Field(default_factory=list)
    recommendations_history: list[dict[str, Any]] = Field(default_factory=list)
    recommendations_table: list[dict[str, Any]] = Field(default_factory=list)
    eps_trend: list[dict[str, Any]] = Field(default_factory=list)
    eps_revisions: list[dict[str, Any]] = Field(default_factory=list)
    earnings_estimate: list[dict[str, Any]] = Field(default_factory=list)
    revenue_estimate: list[dict[str, Any]] = Field(default_factory=list)
    growth_estimates: list[dict[str, Any]] = Field(default_factory=list)


class SecurityValuationOut(BaseModel):
    symbol: str
    as_of_date: date
    model_status: str
    analyst_upside: float | None
    dcf_fair_value: float | None
    dcf_upside: float | None = None
    ri_fair_value: float | None
    ri_upside: float | None = None
    ddm_fair_value: float | None = None
    ddm_upside: float | None = None
    relative_fair_value: float | None
    relative_upside: float | None = None
    composite_fair_value: float | None
    composite_upside: float | None
    confidence_low: float | None
    confidence_high: float | None
    inputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class DcfDetailScenarioOut(BaseModel):
    scenario_key: str
    assumptions: dict[str, Any] = Field(default_factory=dict)
    forecast: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SecurityDcfDetailResponse(BaseModel):
    portfolio_id: int
    symbol: str
    as_of_date: date | None
    status: str
    model_version: str | None = None
    quality_score: float | None = None
    anchor_mode: str | None = None
    anchor_diagnostics_summary: dict[str, Any] = Field(default_factory=dict)
    tv_breakdown_summary: dict[str, Any] = Field(default_factory=dict)
    assumptions_used: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[DcfDetailScenarioOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RiDetailScenarioOut(BaseModel):
    scenario_key: str
    assumptions: dict[str, Any] = Field(default_factory=dict)
    forecast: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SecurityRiDetailResponse(BaseModel):
    portfolio_id: int
    symbol: str
    as_of_date: date | None
    status: str
    model_version: str | None = None
    quality_score: float | None = None
    anchor_mode: str | None = None
    anchor_diagnostics_summary: dict[str, Any] = Field(default_factory=dict)
    terminal_summary: dict[str, Any] = Field(default_factory=dict)
    assumptions_used: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[RiDetailScenarioOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DdmDetailScenarioOut(BaseModel):
    scenario_key: str
    assumptions: dict[str, Any] = Field(default_factory=dict)
    forecast: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SecurityDdmDetailResponse(BaseModel):
    portfolio_id: int
    symbol: str
    as_of_date: date | None
    status: str
    model_version: str | None = None
    quality_score: float | None = None
    anchor_mode: str | None = None
    coverage_mode: str | None = None
    anchor_diagnostics_summary: dict[str, Any] = Field(default_factory=dict)
    terminal_summary: dict[str, Any] = Field(default_factory=dict)
    assumptions_used: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[DdmDetailScenarioOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PortfolioValuationOverviewResponse(BaseModel):
    portfolio_id: int
    snapshot_id: int | None
    as_of_date: date | None
    status: str
    weighted_analyst_upside: float | None
    weighted_dcf_upside: float | None = None
    weighted_ri_upside: float | None = None
    weighted_ddm_upside: float | None = None
    weighted_relative_upside: float | None = None
    weighted_composite_upside: float | None
    coverage_ratio: float
    overvalued_weight: float
    undervalued_weight: float
    summary: dict[str, Any] = Field(default_factory=dict)
    run: ValuationRunOut | None = None
    results: list[SecurityValuationOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValuationRecomputeResponse(BaseModel):
    run: ValuationRunOut
    overview: PortfolioValuationOverviewResponse | None = None
