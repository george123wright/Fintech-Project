from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.analytics import RefreshJobOut, RiskMetricOut
from app.schemas.scenarios import ScenarioRunListItem
from app.schemas.valuation import PortfolioValuationOverviewResponse


class PortfolioCreate(BaseModel):
    name: str = Field(default="My Portfolio", min_length=1, max_length=128)
    base_currency: str = Field(default="USD", min_length=3, max_length=8)
    benchmark_symbol: str = Field(default="SPY", min_length=1, max_length=16)


class PortfolioRead(BaseModel):
    id: int
    name: str
    base_currency: str
    benchmark_symbol: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ManualHoldingInput(BaseModel):
    ticker: str = Field(min_length=1, max_length=24)
    units: float | None = None
    market_value: float | None = None
    cost_basis: float | None = None
    currency: str = Field(default="USD", min_length=3, max_length=8)
    name: str | None = None
    asset_type: str | None = None


class ManualHoldingsRequest(BaseModel):
    holdings: list[ManualHoldingInput] = Field(default_factory=list)


class UploadValidationReport(BaseModel):
    upload_id: int
    status: str
    accepted_rows: int
    rejected_rows: int
    unknown_tickers: list[str]
    missing_fields: list[str]
    errors: list[str] = Field(default_factory=list)
    snapshot_id: int | None = None
    as_of_date: date | None = None


class HoldingPositionOut(BaseModel):
    symbol: str
    name: str | None
    asset_type: str | None
    units: float | None
    market_value: float
    cost_basis: float | None
    currency: str
    weight: float

    model_config = {"from_attributes": True}


class HoldingsLatestResponse(BaseModel):
    portfolio_id: int
    snapshot_id: int
    as_of_date: date
    positions: list[HoldingPositionOut]


class OverviewResponse(BaseModel):
    portfolio: PortfolioRead
    snapshot_id: int | None
    as_of_date: date | None
    holdings_count: int
    top_holdings: list[HoldingPositionOut]
    allocation: dict[str, float]
    metrics: RiskMetricOut | None
    last_refresh: RefreshJobOut | None
    valuation_summary: PortfolioValuationOverviewResponse | None = None
    latest_scenario_run: ScenarioRunListItem | None = None
