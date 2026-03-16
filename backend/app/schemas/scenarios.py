from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScenarioFactorMeta(BaseModel):
    key: str
    label: str
    unit: str
    min_value: float
    max_value: float
    step: float
    default_value: float
    source: str
    description: str


class ScenarioMetadataResponse(BaseModel):
    portfolio_id: int
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    factors: list[ScenarioFactorMeta] = Field(default_factory=list)
    default_confidence_level: float = 0.95
    default_n_sims: int = 1000
    max_n_sims: int = 5000
    horizons: list[int] = Field(default_factory=lambda: [1, 5, 21, 63, 126, 252])


class ScenarioPreviewRequest(BaseModel):
    factor_key: str
    shock_value: float
    shock_unit: str
    horizon_days: int = Field(default=21, ge=1, le=3650)
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.999)
    n_sims: int = Field(default=1000, ge=100, le=5000)
    selected_symbol: str | None = Field(default=None, max_length=24)
    include_baseline: bool = True
    shrinkage_lambda: float = Field(default=0.2, ge=0.0, le=1.0)


class ScenarioImpactOut(BaseModel):
    symbol: str
    current_value: float | None = None
    expected_return_pct: float | None = None
    shock_only_return_pct: float | None = None
    expected_value: float | None = None
    shock_only_value_delta: float | None = None
    quantile_low_pct: float | None = None
    quantile_high_pct: float | None = None


class ScenarioContributionOut(BaseModel):
    symbol: str
    weight: float
    beta: float | None = None
    contribution_pct: float | None = None


class ScenarioDistributionBinOut(BaseModel):
    series_key: str
    bin_index: int
    bin_start: float
    bin_end: float
    count: int
    density: float


class ScenarioPathPointOut(BaseModel):
    step: int
    label: str
    cumulative_return_pct: float
    value: float | None = None


class ScenarioPathOut(BaseModel):
    series_key: str
    path_id: str
    points: list[ScenarioPathPointOut] = Field(default_factory=list)


class RelationshipStatsOut(BaseModel):
    alpha: float | None = None
    beta: float | None = None
    beta_std_error: float | None = None
    beta_t_stat: float | None = None
    beta_p_value: float | None = None
    r2: float | None = None
    adj_r2: float | None = None
    n_obs: int = 0
    correlation: float | None = None
    covariance: float | None = None
    residual_mean: float | None = None
    residual_std: float | None = None
    residual_skew: float | None = None
    residual_kurtosis: float | None = None
    shock_z_score: float | None = None
    shock_percentile: float | None = None
    flags: list[str] = Field(default_factory=list)


class SimulationStatsOut(BaseModel):
    mean_pct: float | None = None
    median_pct: float | None = None
    std_pct: float | None = None
    skew: float | None = None
    kurtosis: float | None = None
    var_95_pct: float | None = None
    cvar_95_pct: float | None = None
    var_99_pct: float | None = None
    cvar_99_pct: float | None = None
    quantile_low_pct: float | None = None
    quantile_high_pct: float | None = None


class ScenarioResultResponse(BaseModel):
    status: str
    warnings: list[str] = Field(default_factory=list)
    model_version: str
    inputs: dict[str, Any]
    assumptions: dict[str, Any]
    portfolio_impact: ScenarioImpactOut
    selected_stock_impact: ScenarioImpactOut | None = None
    contributions: list[ScenarioContributionOut] = Field(default_factory=list)
    distribution_bins: list[ScenarioDistributionBinOut] = Field(default_factory=list)
    simulation_paths: list[ScenarioPathOut] = Field(default_factory=list)
    relationship_stats: dict[str, RelationshipStatsOut] = Field(default_factory=dict)
    simulation_stats: dict[str, SimulationStatsOut] = Field(default_factory=dict)
    narrative: list[str] = Field(default_factory=list)
    run_id: int | None = None
    created_at: datetime | None = None


class ScenarioRunListItem(BaseModel):
    id: int
    status: str
    factor_key: str
    shock_value: float
    shock_unit: str
    horizon_days: int
    confidence_level: float
    n_sims: int
    selected_symbol: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class ScenarioRunListResponse(BaseModel):
    portfolio_id: int
    runs: list[ScenarioRunListItem] = Field(default_factory=list)
