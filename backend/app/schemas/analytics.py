from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskMetricOut(BaseModel):
    as_of_date: date
    window: str
    portfolio_value: float
    ann_return: float
    ann_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    beta: float
    top3_weight_share: float
    hhi: float

    model_config = {"from_attributes": True}


class RiskContributionOut(BaseModel):
    symbol: str
    marginal_risk: float
    component_risk: float
    pct_total_risk: float

    model_config = {"from_attributes": True}


class RiskAnalyticsResponse(BaseModel):
    portfolio_id: int
    snapshot_id: int
    metrics: RiskMetricOut
    contributions: list[RiskContributionOut]


class ExtendedMetricSnapshotOut(BaseModel):
    as_of_date: date
    window: str
    benchmark_symbol: str
    metrics: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class ExtendedAnalyticsResponse(BaseModel):
    portfolio_id: int
    snapshot_id: int
    extended: ExtendedMetricSnapshotOut


class RefreshJobOut(BaseModel):
    id: int
    trigger_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None

    model_config = {"from_attributes": True}


class RefreshResponse(BaseModel):
    job: RefreshJobOut
    metrics: RiskMetricOut | None


class PricePoint(BaseModel):
    date: date
    close: float


class SymbolPriceSeries(BaseModel):
    symbol: str
    points: list[PricePoint]


class PricesResponse(BaseModel):
    portfolio_id: int
    range: str
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    missing_symbols: list[str] = Field(default_factory=list)
    series: list[SymbolPriceSeries]


class MarketEventOut(BaseModel):
    id: str
    date: datetime
    event_type: str
    title: str
    summary: str
    detail: str | None = None
    link_target: str


class CorporateActionRowOut(BaseModel):
    date: datetime
    action_type: str
    value: float
    description: str


class InsiderTransactionRowOut(BaseModel):
    date: datetime | None = None
    insider: str | None = None
    position: str | None = None
    transaction: str | None = None
    shares: float | None = None
    value: float | None = None
    ownership: str | None = None
    text: str | None = None


class AnalystRevisionRowOut(BaseModel):
    date: datetime
    firm: str | None = None
    action: str | None = None
    to_grade: str | None = None
    from_grade: str | None = None
    current_price_target: float | None = None
    prior_price_target: float | None = None
    price_target_action: str | None = None


class SecurityEventsResponse(BaseModel):
    symbol: str
    range: str
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    events: list[MarketEventOut] = Field(default_factory=list)
    corporate_actions: list[CorporateActionRowOut] = Field(default_factory=list)
    insider_transactions: list[InsiderTransactionRowOut] = Field(default_factory=list)
    analyst_revisions: list[AnalystRevisionRowOut] = Field(default_factory=list)


class NewsArticleOut(BaseModel):
    id: str
    title: str
    summary: str | None = None
    pub_date: datetime | None = None
    provider: str | None = None
    url: str | None = None
    thumbnail_url: str | None = None
    content_type: str | None = None
    symbols: list[str] = Field(default_factory=list)


class SecurityNewsResponse(BaseModel):
    symbol: str
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    articles: list[NewsArticleOut] = Field(default_factory=list)


class PortfolioNewsResponse(BaseModel):
    portfolio_id: int
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    count: int = 0
    articles: list[NewsArticleOut] = Field(default_factory=list)


class ExposureBucketOut(BaseModel):
    label: str
    direct_weight: float = 0.0
    lookthrough_weight: float = 0.0
    direct_weight_pct: float = 0.0
    lookthrough_weight_pct: float = 0.0


class ExposureHoldingOut(BaseModel):
    symbol: str
    name: str | None = None
    weight: float
    weight_pct: float
    market_value: float | None = None
    sector: str | None = None
    currency: str | None = None
    asset_type: str | None = None


class ConcentrationFlagOut(BaseModel):
    level: str
    title: str
    detail: str


class ExposureCoverageOut(BaseModel):
    holding_count: int
    lookthrough_positions: int = 0
    constituent_positions: int = 0
    covered_weight: float = 0.0
    covered_weight_pct: float = 0.0


class OverlapPairOut(BaseModel):
    left_symbol: str
    right_symbol: str
    overlap_weight: float
    overlap_pct_of_pair: float
    overlap_type: str


class ConcentrationSignalOut(BaseModel):
    signal_key: str
    signal_value: float
    severity: str
    summary: str


class ExposureSummaryOut(BaseModel):
    methodology_version: str = "exposure_v1"
    coverage: ExposureCoverageOut
    breakdowns: dict[str, list[ExposureBucketOut]] = Field(default_factory=dict)
    top_lookthrough_holdings: list[ExposureHoldingOut] = Field(default_factory=list)
    overlap_pairs: list[OverlapPairOut] = Field(default_factory=list)
    concentration_signals: list[ConcentrationSignalOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    snapshot_id: int | None = None
    as_of_date: str | None = None


class EvidenceChipOut(BaseModel):
    label: str
    value: str


class NarrativeCardOut(BaseModel):
    id: str
    title: str
    tone: str
    summary: str
    evidence_chips: list[EvidenceChipOut] = Field(default_factory=list)


class WatchoutOut(BaseModel):
    level: str
    title: str
    detail: str


class ChangeSummaryOut(BaseModel):
    headline: str
    prior_top3_weight: float | None = None


class PortfolioNarrativeOut(BaseModel):
    status: str = "ok"
    cards: list[NarrativeCardOut] = Field(default_factory=list)
    watchouts: list[WatchoutOut] = Field(default_factory=list)
    change_summary: ChangeSummaryOut | None = None
    evidence_chips: list[EvidenceChipOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


IndustryAnalyticsWindow = Literal["1M", "3M", "6M", "1Y", "5Y"]
IndustryAnalyticsInterval = Literal["daily", "weekly", "monthly"]
IndustryAnalyticsSortBy = Literal["return", "vol", "sharpe", "alphabetical"]
IndustryAnalyticsSortOrder = Literal["asc", "desc"]


class IndustryAnalyticsParams(BaseModel):
    window: IndustryAnalyticsWindow = "1Y"
    interval: IndustryAnalyticsInterval = "daily"
    benchmark: str | None = None
    sort_by: IndustryAnalyticsSortBy = "return"
    sort_order: IndustryAnalyticsSortOrder = "desc"


class IndustryMetricRowOut(BaseModel):
    industry: str
    weight: float = 0.0
    window_return: float | None = None
    annualized_return: float | None = None
    volatility_periodic: float | None = None
    volatility_annualized: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    var_95: float | None = None
    cvar_95: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    upside_capture: float | None = None
    downside_capture: float | None = None
    beta: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    max_drawdown: float | None = None
    hit_rate: float | None = None


class IndustryMatrixOut(BaseModel):
    labels: list[str] = Field(default_factory=list)
    values: list[list[float | None]] = Field(default_factory=list)
    sort_context: dict[str, Any] = Field(default_factory=dict)


class IndustryOverviewResponse(BaseModel):
    portfolio_id: int
    snapshot_id: int
    as_of_date: date
    window: IndustryAnalyticsWindow
    interval: IndustryAnalyticsInterval
    benchmark: str
    sort_by: IndustryAnalyticsSortBy
    sort_order: IndustryAnalyticsSortOrder
    rows: list[IndustryMetricRowOut] = Field(default_factory=list)
    covariance_matrix: IndustryMatrixOut
    correlation_matrix: IndustryMatrixOut
