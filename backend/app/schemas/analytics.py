from __future__ import annotations

from datetime import date, datetime
from typing import Any

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
