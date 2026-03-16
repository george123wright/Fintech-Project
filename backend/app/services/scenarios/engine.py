from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew, t as student_t
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    HoldingsPosition,
    HoldingsSnapshot,
    MacroFactorSnapshot,
    MacroSeriesObservation,
    SecurityPriceDaily,
    ScenarioRun,
    ScenarioRunDistributionBin,
    ScenarioRunNarrative,
    ScenarioRunPortfolio,
    ScenarioRunResult,
)
from app.schemas.scenarios import (
    RelationshipStatsOut,
    ScenarioContributionOut,
    ScenarioDistributionBinOut,
    ScenarioFactorMeta,
    ScenarioImpactOut,
    ScenarioMetadataResponse,
    ScenarioPathOut,
    ScenarioPathPointOut,
    ScenarioPreviewRequest,
    ScenarioResultResponse,
    ScenarioRunListItem,
    ScenarioRunListResponse,
    SimulationStatsOut,
)
from app.services.portfolio import get_portfolio_or_404, latest_snapshot
from app.services.pricing import get_symbols_price_frame
from app.services.providers import fetch_fred_series

MODEL_VERSION = "scenario_v1"
MIN_OBS = 24
MIN_OBS_WARN = 36
DEFAULT_LOOKBACK_YEARS = 10
MAX_SHOCK_Z = 3.0
PREVIEW_MAX_SIMS = 400
PREVIEW_MAX_PATHS = 12

FACTOR_SHOCK_PERSISTENCE: dict[str, float] = {
    "rates": 0.65,
    "oil": 0.45,
    "unemployment": 0.70,
    "government_spending": 0.80,
    "inflation": 0.75,
    "gdp": 0.75,
    "retail_spending": 0.60,
    "vix": 0.30,
}


@dataclass(frozen=True)
class FactorSpec:
    key: str
    label: str
    unit: str
    source: str
    source_series: str
    transform: str
    min_value: float
    max_value: float
    step: float
    default_value: float
    description: str


FACTOR_SPECS: dict[str, FactorSpec] = {
    "rates": FactorSpec(
        key="rates",
        label="Rates (10Y Treasury)",
        unit="bps",
        source="yahoo",
        source_series="^TNX",
        transform="diff_pp",
        min_value=-200.0,
        max_value=200.0,
        step=5.0,
        default_value=25.0,
        description="Shock to 10Y yield in basis points.",
    ),
    "oil": FactorSpec(
        key="oil",
        label="Oil (WTI)",
        unit="%",
        source="yahoo",
        source_series="CL=F",
        transform="log_pct",
        min_value=-30.0,
        max_value=30.0,
        step=1.0,
        default_value=5.0,
        description="Monthly oil return shock in percent.",
    ),
    "unemployment": FactorSpec(
        key="unemployment",
        label="Unemployment",
        unit="pp",
        source="fred",
        source_series="UNRATE",
        transform="diff_pp",
        min_value=-3.0,
        max_value=3.0,
        step=0.1,
        default_value=0.5,
        description="Shock to unemployment rate in percentage points.",
    ),
    "government_spending": FactorSpec(
        key="government_spending",
        label="Government Spending",
        unit="%",
        source="fred",
        source_series="W068RCQ027SBEA",
        transform="log_pct",
        min_value=-15.0,
        max_value=15.0,
        step=0.5,
        default_value=2.0,
        description="Growth shock to real government spending (log %).",
    ),
    "inflation": FactorSpec(
        key="inflation",
        label="Inflation (CPI)",
        unit="%",
        source="fred",
        source_series="CPIAUCSL",
        transform="log_pct",
        min_value=-5.0,
        max_value=5.0,
        step=0.1,
        default_value=0.4,
        description="Monthly inflation shock from CPI log growth.",
    ),
    "gdp": FactorSpec(
        key="gdp",
        label="GDP Growth",
        unit="%",
        source="fred",
        source_series="GDP",
        transform="log_pct",
        min_value=-10.0,
        max_value=10.0,
        step=0.25,
        default_value=1.0,
        description="Growth shock to GDP log growth.",
    ),
    "retail_spending": FactorSpec(
        key="retail_spending",
        label="Retail Spending",
        unit="%",
        source="fred",
        source_series="RSAFS",
        transform="log_pct",
        min_value=-10.0,
        max_value=10.0,
        step=0.25,
        default_value=1.0,
        description="Growth shock to retail sales log growth.",
    ),
    "vix": FactorSpec(
        key="vix",
        label="Market Volatility (VIX)",
        unit="%",
        source="fred",
        source_series="VIXCLS",
        transform="log_pct",
        min_value=-60.0,
        max_value=60.0,
        step=1.0,
        default_value=10.0,
        description="Shock to VIX log return as volatility proxy.",
    ),
}

QUARTERLY_SERIES = {"GDP", "W068RCQ027SBEA"}


def _safe_json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _as_month_end(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    clean = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    if clean.empty:
        return clean
    if not isinstance(clean.index, pd.DatetimeIndex):
        clean.index = pd.to_datetime(clean.index)
    if clean.index.tz is not None:
        clean.index = clean.index.tz_convert(None)
    return clean.resample("ME").last()


def _safe_log_diff_pct(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    clean = clean.where(clean > 0)
    return 100.0 * np.log(clean / clean.shift(1))


def _log_pct_to_simple_pct(value: float | np.ndarray) -> float | np.ndarray:
    return (np.exp(np.asarray(value, dtype=float) / 100.0) - 1.0) * 100.0


def _to_monthly_asset_returns(price_frame: pd.DataFrame) -> pd.DataFrame:
    if price_frame.empty:
        return pd.DataFrame()
    monthly = price_frame.sort_index().resample("ME").last()
    returns = 100.0 * np.log(monthly / monthly.shift(1))
    return returns.replace([np.inf, -np.inf], np.nan)


def _to_monthly_factor_series(spec: FactorSpec, raw: pd.Series) -> pd.Series:
    if raw.empty:
        return pd.Series(dtype=float)

    series = raw.sort_index()
    if spec.source == "fred" and spec.source_series in QUARTERLY_SERIES:
        monthly = series.resample("ME").ffill()
    else:
        monthly = _as_month_end(series)

    if spec.transform == "diff_pp":
        transformed = monthly.diff()
    elif spec.transform == "log_pct":
        transformed = _safe_log_diff_pct(monthly)
    else:
        transformed = monthly.copy()

    return transformed.replace([np.inf, -np.inf], np.nan)


def _shock_to_factor_units(spec: FactorSpec, shock_value: float, shock_unit: str) -> float:
    unit = shock_unit.strip().lower()
    if spec.unit == "bps":
        if unit in {"bps", "bp"}:
            return shock_value / 100.0
        if unit in {"pp", "%", "percent", "pct"}:
            return shock_value
        raise ValueError(f"Invalid shock unit '{shock_unit}' for factor {spec.key}")

    if spec.unit == "pp":
        if unit in {"pp", "%", "percent", "pct"}:
            return shock_value
        raise ValueError(f"Invalid shock unit '{shock_unit}' for factor {spec.key}")

    if spec.unit == "%":
        if unit in {"%", "percent", "pct"}:
            return shock_value
        raise ValueError(f"Invalid shock unit '{shock_unit}' for factor {spec.key}")

    return shock_value


def _upsert_macro_observations(
    db: Session,
    *,
    series_id: str,
    rows: list[tuple[date, float]],
    source: str,
) -> None:
    if not rows:
        return
    now = datetime.utcnow()
    for obs_date, value in rows:
        existing = db.scalar(
            select(MacroSeriesObservation)
            .where(MacroSeriesObservation.series_id == series_id)
            .where(MacroSeriesObservation.observation_date == obs_date)
            .limit(1)
        )
        if existing is None:
            db.add(
                MacroSeriesObservation(
                    series_id=series_id,
                    observation_date=obs_date,
                    value=value,
                    source=source,
                    fetched_at=now,
                )
            )
        else:
            existing.value = value
            existing.source = source
            existing.fetched_at = now


def _load_cached_macro_series(
    db: Session,
    *,
    series_id: str,
    start_date: date,
    end_date: date,
) -> pd.Series:
    rows = list(
        db.scalars(
            select(MacroSeriesObservation)
            .where(MacroSeriesObservation.series_id == series_id)
            .where(MacroSeriesObservation.observation_date >= start_date)
            .where(MacroSeriesObservation.observation_date <= end_date)
            .order_by(MacroSeriesObservation.observation_date.asc())
        )
    )
    if not rows:
        return pd.Series(dtype=float, name=series_id)
    idx = pd.to_datetime([r.observation_date for r in rows])
    vals = [float(r.value) for r in rows]
    return pd.Series(vals, index=idx, name=series_id)


def _load_cached_price_frame(
    db: Session,
    *,
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    clean_symbols = sorted({s.upper() for s in symbols if s.strip()})
    if not clean_symbols:
        return pd.DataFrame()

    rows = list(
        db.scalars(
            select(SecurityPriceDaily)
            .where(SecurityPriceDaily.symbol.in_(clean_symbols))
            .where(SecurityPriceDaily.date >= start_date)
            .where(SecurityPriceDaily.date <= end_date)
            .order_by(SecurityPriceDaily.date.asc())
        )
    )
    if not rows:
        return pd.DataFrame()

    grouped: dict[str, list[tuple[pd.Timestamp, float]]] = {symbol: [] for symbol in clean_symbols}
    for row in rows:
        grouped.setdefault(row.symbol.upper(), []).append(
            (pd.Timestamp(row.date), float(row.adj_close))
        )

    series_list: list[pd.Series] = []
    for symbol in clean_symbols:
        points = grouped.get(symbol, [])
        if not points:
            continue
        idx = pd.DatetimeIndex([item[0] for item in points])
        vals = [item[1] for item in points]
        series_list.append(pd.Series(vals, index=idx, name=symbol))

    if not series_list:
        return pd.DataFrame()
    return pd.concat(series_list, axis=1).sort_index().ffill().dropna(how="all")


def _fetch_raw_factor_series(
    db: Session,
    *,
    spec: FactorSpec,
    start_date: date,
    end_date: date,
    warnings: list[str],
    allow_remote_fetch: bool,
) -> pd.Series:
    if spec.source == "yahoo":
        frame = _load_cached_price_frame(
            db,
            symbols=[spec.source_series],
            start_date=start_date,
            end_date=end_date,
        )
        if (frame.empty or spec.source_series not in frame.columns) and allow_remote_fetch:
            try:
                frame = get_symbols_price_frame(db, [spec.source_series], start_date, end_date)
            except Exception as exc:
                warnings.append(f"E_FACTOR_FETCH_FAILED:{spec.key}:{exc.__class__.__name__}")
                return pd.Series(dtype=float, name=spec.source_series)
        if frame.empty or spec.source_series not in frame.columns:
            warnings.append(f"E_FACTOR_NO_DATA:{spec.key}")
            return pd.Series(dtype=float, name=spec.source_series)
        return pd.to_numeric(frame[spec.source_series], errors="coerce").dropna()

    if allow_remote_fetch:
        try:
            obs = fetch_fred_series(series_id=spec.source_series, start_date=start_date, end_date=end_date)
            rows = [(item.observation_date, item.value) for item in obs]
            _upsert_macro_observations(
                db,
                series_id=spec.source_series,
                rows=rows,
                source="fred",
            )
            db.flush()
        except Exception as exc:
            warnings.append(f"E_FACTOR_FETCH_FAILED:{spec.key}:{exc.__class__.__name__}")

    series = _load_cached_macro_series(
        db,
        series_id=spec.source_series,
        start_date=start_date,
        end_date=end_date,
    )
    if series.empty:
        warnings.append(f"E_FACTOR_NO_DATA:{spec.key}")
    return series


def _regression_stats(y: pd.Series, x: pd.Series) -> tuple[RelationshipStatsOut, pd.Series]:
    merged = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    n = len(merged)
    if n < MIN_OBS:
        return RelationshipStatsOut(n_obs=n, flags=["low_sample"]), pd.Series(dtype=float)

    y_np = merged["y"].to_numpy(dtype=float)
    x_np = merged["x"].to_numpy(dtype=float)
    X = np.column_stack([np.ones(n), x_np])

    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return RelationshipStatsOut(n_obs=n, flags=["singular_design"]), pd.Series(dtype=float)

    beta_vec = xtx_inv @ (X.T @ y_np)
    y_hat = X @ beta_vec
    residual = y_np - y_hat

    hat = np.sum(X * (X @ xtx_inv), axis=1)
    leverage_denom = np.clip(1.0 - hat, 1e-9, None)
    scaled = residual / leverage_denom

    meat = np.zeros((2, 2), dtype=float)
    for i in range(n):
        xi = X[i][:, None]
        meat += (scaled[i] ** 2) * (xi @ xi.T)
    cov_hc3 = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.clip(np.diag(cov_hc3), 0.0, None))

    alpha = float(beta_vec[0])
    beta = float(beta_vec[1])
    beta_se = float(se[1]) if np.isfinite(se[1]) else None
    beta_t = None
    beta_p = None
    if beta_se is not None and beta_se > 0:
        beta_t = beta / beta_se
        dof = max(n - 2, 1)
        beta_p = float(2.0 * (1.0 - student_t.cdf(abs(beta_t), dof)))

    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y_np - float(np.mean(y_np))) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else None
    adj_r2 = None
    if r2 is not None and n > 2:
        adj_r2 = float(1.0 - (1.0 - r2) * (n - 1) / max(n - 2, 1))

    corr = None
    covar = None
    if n > 1:
        corr_raw = np.corrcoef(y_np, x_np)[0, 1]
        cov_raw = np.cov(y_np, x_np, ddof=1)[0, 1]
        corr = float(corr_raw) if np.isfinite(corr_raw) else None
        covar = float(cov_raw) if np.isfinite(cov_raw) else None

    flags: list[str] = []
    if n < MIN_OBS_WARN:
        flags.append("low_sample")
    if beta_p is not None and beta_p > 0.10:
        flags.append("weak_fit")
    if r2 is not None and r2 < 0.03:
        flags.append("weak_fit")
    if beta_se is not None and abs(beta) > 0 and beta_se / abs(beta) > 1.5:
        flags.append("high_instability")

    residual_series = pd.Series(residual, index=merged.index)
    stats = RelationshipStatsOut(
        alpha=alpha,
        beta=beta,
        beta_std_error=beta_se,
        beta_t_stat=float(beta_t) if beta_t is not None and np.isfinite(beta_t) else None,
        beta_p_value=beta_p,
        r2=r2,
        adj_r2=adj_r2,
        n_obs=n,
        correlation=corr,
        covariance=covar,
        residual_mean=float(residual_series.mean()) if n else None,
        residual_std=float(residual_series.std(ddof=1)) if n > 1 else None,
        residual_skew=float(skew(residual_series, bias=False)) if n > 2 else None,
        residual_kurtosis=float(kurtosis(residual_series, fisher=False, bias=False)) if n > 3 else None,
        flags=sorted(set(flags)),
    )
    return stats, residual_series


def _regression_stats_with_controls(
    y: pd.Series,
    x_primary: pd.Series,
    controls: dict[str, pd.Series],
) -> tuple[RelationshipStatsOut, pd.Series]:
    control_items = [(name, series) for name, series in controls.items() if not series.dropna().empty]
    if not control_items:
        return _regression_stats(y, x_primary)

    data_parts: dict[str, pd.Series] = {"y": y, "x_primary": x_primary}
    for name, series in control_items:
        data_parts[name] = series
    merged = pd.concat(data_parts, axis=1).dropna()
    n = len(merged)
    p = 1 + 1 + len(control_items)  # intercept + primary + controls
    if n < max(MIN_OBS, p + 5):
        return _regression_stats(y, x_primary)

    y_np = merged["y"].to_numpy(dtype=float)
    x_cols = ["x_primary", *[name for name, _ in control_items]]
    x_np = merged[x_cols].to_numpy(dtype=float)
    X = np.column_stack([np.ones(n), x_np])

    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return _regression_stats(y, x_primary)

    beta_vec = xtx_inv @ (X.T @ y_np)
    y_hat = X @ beta_vec
    residual = y_np - y_hat

    hat = np.sum(X * (X @ xtx_inv), axis=1)
    leverage_denom = np.clip(1.0 - hat, 1e-9, None)
    scaled = residual / leverage_denom

    meat = np.zeros((X.shape[1], X.shape[1]), dtype=float)
    for i in range(n):
        xi = X[i][:, None]
        meat += (scaled[i] ** 2) * (xi @ xi.T)
    cov_hc3 = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.clip(np.diag(cov_hc3), 0.0, None))

    alpha = float(beta_vec[0])
    beta = float(beta_vec[1])
    beta_se = float(se[1]) if np.isfinite(se[1]) else None
    beta_t = None
    beta_p = None
    if beta_se is not None and beta_se > 0:
        beta_t = beta / beta_se
        dof = max(n - X.shape[1], 1)
        beta_p = float(2.0 * (1.0 - student_t.cdf(abs(beta_t), dof)))

    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y_np - float(np.mean(y_np))) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else None
    adj_r2 = None
    if r2 is not None and n > X.shape[1]:
        adj_r2 = float(1.0 - (1.0 - r2) * (n - 1) / max(n - X.shape[1], 1))

    corr = None
    covar = None
    if n > 1:
        x_primary_np = merged["x_primary"].to_numpy(dtype=float)
        corr_raw = np.corrcoef(y_np, x_primary_np)[0, 1]
        cov_raw = np.cov(y_np, x_primary_np, ddof=1)[0, 1]
        corr = float(corr_raw) if np.isfinite(corr_raw) else None
        covar = float(cov_raw) if np.isfinite(cov_raw) else None

    flags: list[str] = []
    if n < MIN_OBS_WARN:
        flags.append("low_sample")
    if beta_p is not None and beta_p > 0.10:
        flags.append("weak_fit")
    if r2 is not None and r2 < 0.03:
        flags.append("weak_fit")
    if beta_se is not None and abs(beta) > 0 and beta_se / abs(beta) > 1.5:
        flags.append("high_instability")

    residual_series = pd.Series(residual, index=merged.index)
    stats = RelationshipStatsOut(
        alpha=alpha,
        beta=beta,
        beta_std_error=beta_se,
        beta_t_stat=float(beta_t) if beta_t is not None and np.isfinite(beta_t) else None,
        beta_p_value=beta_p,
        r2=r2,
        adj_r2=adj_r2,
        n_obs=n,
        correlation=corr,
        covariance=covar,
        residual_mean=float(residual_series.mean()) if n else None,
        residual_std=float(residual_series.std(ddof=1)) if n > 1 else None,
        residual_skew=float(skew(residual_series, bias=False)) if n > 2 else None,
        residual_kurtosis=float(kurtosis(residual_series, fisher=False, bias=False)) if n > 3 else None,
        flags=sorted(set(flags)),
    )
    return stats, residual_series


def _shock_stats(x: pd.Series, shock: float) -> tuple[float | None, float | None]:
    clean = x.dropna()
    if clean.empty:
        return None, None
    sigma = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    mean = float(clean.mean())
    z_score = None
    if sigma > 0:
        z_score = float((shock - mean) / sigma)

    abs_values = np.abs(clean.to_numpy(dtype=float))
    if len(abs_values) == 0:
        return z_score, None
    percentile = float(np.mean(abs_values <= abs(shock)))
    return z_score, percentile


def _simulation_stats(draws: np.ndarray, confidence_level: float) -> SimulationStatsOut:
    if draws.size == 0:
        return SimulationStatsOut()

    low_q = (1.0 - confidence_level) / 2.0
    high_q = 1.0 - low_q
    q_low = float(np.quantile(draws, low_q))
    q_high = float(np.quantile(draws, high_q))
    q_5 = float(np.quantile(draws, 0.05))
    q_1 = float(np.quantile(draws, 0.01))
    tail = draws[draws <= q_5]
    tail_99 = draws[draws <= q_1]
    var_95 = max(0.0, float(-q_5))
    cvar = max(0.0, float(-tail.mean()) if tail.size else float(-q_5))
    var_99 = max(0.0, float(-q_1))
    cvar_99 = max(0.0, float(-tail_99.mean()) if tail_99.size else float(-q_1))

    return SimulationStatsOut(
        mean_pct=float(np.mean(draws)),
        median_pct=float(np.median(draws)),
        std_pct=float(np.std(draws, ddof=1)) if draws.size > 1 else 0.0,
        skew=float(skew(draws, bias=False)) if draws.size > 2 else 0.0,
        kurtosis=float(kurtosis(draws, fisher=False, bias=False)) if draws.size > 3 else 3.0,
        var_95_pct=var_95,
        cvar_95_pct=cvar,
        var_99_pct=var_99,
        cvar_99_pct=cvar_99,
        quantile_low_pct=q_low,
        quantile_high_pct=q_high,
    )


def _distribution_bins(
    draws: np.ndarray,
    *,
    series_key: str,
    bins: int = 30,
) -> list[ScenarioDistributionBinOut]:
    if draws.size == 0:
        return []
    counts, edges = np.histogram(draws, bins=bins)
    total = int(counts.sum())
    out: list[ScenarioDistributionBinOut] = []
    for idx in range(len(counts)):
        start = float(edges[idx])
        end = float(edges[idx + 1])
        count = int(counts[idx])
        density = float(count / total) if total > 0 else 0.0
        out.append(
            ScenarioDistributionBinOut(
                series_key=series_key,
                bin_index=idx,
                bin_start=start,
                bin_end=end,
                count=count,
                density=density,
            )
        )
    return out


def _build_sample_paths(
    *,
    series_key: str,
    cumulative_log_paths: np.ndarray,
    current_value: float | None,
    max_paths: int = 30,
) -> list[ScenarioPathOut]:
    if cumulative_log_paths.size == 0:
        return []
    n_sims, n_steps = cumulative_log_paths.shape
    if n_steps == 0:
        return []

    indices = np.linspace(0, max(n_sims - 1, 0), num=min(max_paths, n_sims), dtype=int)
    out: list[ScenarioPathOut] = []
    for idx in indices:
        points: list[ScenarioPathPointOut] = []
        for step in range(n_steps):
            log_pct = float(cumulative_log_paths[idx, step])
            simple_pct = float(_log_pct_to_simple_pct(log_pct))
            value = None
            if current_value is not None:
                value = float(current_value * (1.0 + simple_pct / 100.0))
            points.append(
                ScenarioPathPointOut(
                    step=step + 1,
                    label=f"M{step + 1}",
                    cumulative_return_pct=simple_pct,
                    value=value,
                )
            )
        out.append(ScenarioPathOut(series_key=series_key, path_id=f"{series_key}_{idx}", points=points))
    return out


def _build_factor_metadata() -> list[ScenarioFactorMeta]:
    out: list[ScenarioFactorMeta] = []
    for key in [
        "rates",
        "oil",
        "inflation",
        "gdp",
        "retail_spending",
        "unemployment",
        "government_spending",
        "vix",
    ]:
        spec = FACTOR_SPECS[key]
        out.append(
            ScenarioFactorMeta(
                key=spec.key,
                label=spec.label,
                unit=spec.unit,
                min_value=spec.min_value,
                max_value=spec.max_value,
                step=spec.step,
                default_value=spec.default_value,
                source=f"{spec.source}:{spec.source_series}",
                description=spec.description,
            )
        )
    return out


def scenario_metadata(portfolio_id: int) -> ScenarioMetadataResponse:
    return ScenarioMetadataResponse(
        portfolio_id=portfolio_id,
        factors=_build_factor_metadata(),
    )


def _latest_factor_snapshot(db: Session) -> MacroFactorSnapshot | None:
    return db.scalar(
        select(MacroFactorSnapshot)
        .order_by(desc(MacroFactorSnapshot.as_of_date), desc(MacroFactorSnapshot.id))
        .limit(1)
    )


def _upsert_factor_snapshot(
    db: Session,
    *,
    as_of_date: date,
    factor_panel: pd.DataFrame,
    warnings: list[str],
) -> None:
    payload = {
        "dates": [idx.date().isoformat() for idx in factor_panel.index],
        "factors": {
            col: [None if pd.isna(v) else float(v) for v in factor_panel[col].tolist()]
            for col in factor_panel.columns
        },
    }
    existing = db.scalar(
        select(MacroFactorSnapshot)
        .where(MacroFactorSnapshot.as_of_date == as_of_date)
        .limit(1)
    )
    if existing is None:
        db.add(
            MacroFactorSnapshot(
                as_of_date=as_of_date,
                factors_json=json.dumps(payload),
                warnings_json=json.dumps(sorted(set(warnings))),
            )
        )
    else:
        existing.factors_json = json.dumps(payload)
        existing.warnings_json = json.dumps(sorted(set(warnings)))


def _build_monthly_panel(
    db: Session,
    *,
    holdings: list[HoldingsPosition],
    benchmark_symbol: str,
    end_date: date,
    warnings: list[str],
    allow_remote_fetch: bool,
    persist_factor_snapshot: bool,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame]:
    symbols = [h.symbol.upper() for h in holdings]
    start_date = end_date - timedelta(days=365 * DEFAULT_LOOKBACK_YEARS)

    px = _load_cached_price_frame(
        db,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
    )
    missing_symbols = [s for s in symbols if s not in px.columns or px[s].dropna().empty]
    if missing_symbols and allow_remote_fetch:
        px = get_symbols_price_frame(db, symbols, start_date, end_date)
        missing_symbols = [s for s in symbols if s not in px.columns or px[s].dropna().empty]
    if missing_symbols:
        warnings.append(f"E_PRICE_CACHE_MISS:{','.join(sorted(set(missing_symbols)))}")
    if px.empty:
        raise ValueError("No holdings price data available for scenario model.")

    bench_px_frame = _load_cached_price_frame(
        db,
        symbols=[benchmark_symbol],
        start_date=start_date,
        end_date=end_date,
    )
    if (bench_px_frame.empty or benchmark_symbol not in bench_px_frame.columns) and allow_remote_fetch:
        bench_px_frame = get_symbols_price_frame(db, [benchmark_symbol], start_date, end_date)
    if bench_px_frame.empty:
        raise ValueError(f"No benchmark price data available for {benchmark_symbol}.")

    bench_col = benchmark_symbol if benchmark_symbol in bench_px_frame.columns else bench_px_frame.columns[0]
    bench_px = bench_px_frame[bench_col]

    holding_returns = _to_monthly_asset_returns(px)
    benchmark_returns = _to_monthly_asset_returns(bench_px.to_frame(name="benchmark"))["benchmark"]

    weights = np.array([float(h.weight) for h in holdings], dtype=float)
    if not np.isfinite(weights).all() or float(weights.sum()) <= 0:
        raise ValueError("Invalid holdings weights for scenario model.")
    weights = weights / float(weights.sum())

    common = holding_returns.index
    if common.empty:
        raise ValueError("No monthly holdings returns available for scenario model.")

    portfolio_returns = (holding_returns.fillna(0.0).to_numpy(dtype=float) @ weights)
    portfolio_series = pd.Series(portfolio_returns, index=holding_returns.index, name="portfolio")

    factor_columns: dict[str, pd.Series] = {}
    stale_cutoff = pd.Timestamp(end_date) - pd.Timedelta(days=45)
    for spec in FACTOR_SPECS.values():
        raw = _fetch_raw_factor_series(
            db,
            spec=spec,
            start_date=start_date,
            end_date=end_date,
            warnings=warnings,
            allow_remote_fetch=allow_remote_fetch,
        )
        if raw.empty:
            factor_columns[spec.key] = pd.Series(dtype=float)
            continue

        if raw.index.max() < stale_cutoff:
            warnings.append(f"E_FACTOR_STALE:{spec.key}")

        transformed = _to_monthly_factor_series(spec, raw)
        factor_columns[spec.key] = transformed

    factor_panel = pd.concat(factor_columns, axis=1).sort_index()
    factor_panel = factor_panel.replace([np.inf, -np.inf], np.nan)

    align_index = holding_returns.index.intersection(benchmark_returns.index).intersection(factor_panel.index)
    holding_returns = holding_returns.loc[align_index]
    portfolio_series = portfolio_series.loc[align_index]
    benchmark_returns = benchmark_returns.loc[align_index]
    factor_panel = factor_panel.loc[align_index]

    if len(align_index) < MIN_OBS:
        warnings.append("E_LOW_ALIGNED_OBS")

    if persist_factor_snapshot:
        _upsert_factor_snapshot(db, as_of_date=end_date, factor_panel=factor_panel, warnings=warnings)

    return holding_returns, portfolio_series, factor_panel, benchmark_returns, px


def _build_narrative(
    *,
    factor_label: str,
    shock_value: float,
    shock_unit: str,
    horizon_days: int,
    portfolio_impact: ScenarioImpactOut,
    top_pos: ScenarioContributionOut | None,
    top_neg: ScenarioContributionOut | None,
) -> list[str]:
    lines = [
        (
            f"Scenario uses a {factor_label} shock of {shock_value:g} {shock_unit} over {horizon_days} trading days "
            "with monthly factor-response calibration."
        )
    ]
    if portfolio_impact.shock_only_return_pct is not None:
        lines.append(
            "Deterministic shock-only portfolio impact: "
            f"{portfolio_impact.shock_only_return_pct:+.2f}% (before residual uncertainty)."
        )
    if top_pos is not None:
        lines.append(
            f"Largest positive contributor: {top_pos.symbol} ({(top_pos.contribution_pct or 0.0):+.2f}% return contribution)."
        )
    if top_neg is not None:
        lines.append(
            f"Largest negative contributor: {top_neg.symbol} ({(top_neg.contribution_pct or 0.0):+.2f}% return contribution)."
        )
    lines.append("Scenario outputs are analytics only and not investment advice.")
    return lines


def run_scenario_preview(
    db: Session,
    *,
    portfolio_id: int,
    payload: ScenarioPreviewRequest,
    persist: bool,
) -> ScenarioResultResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise ValueError("Portfolio not found")

    spec = FACTOR_SPECS.get(payload.factor_key)
    if spec is None:
        raise ValueError(f"Unknown factor '{payload.factor_key}'")

    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise ValueError("No holdings snapshot found")

    holdings = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )
    if not holdings:
        raise ValueError("No holdings in latest snapshot")

    warnings: list[str] = []
    effective_n_sims = int(payload.n_sims)
    if not persist and effective_n_sims > PREVIEW_MAX_SIMS:
        warnings.append(f"E_PREVIEW_SIMS_CAPPED:{PREVIEW_MAX_SIMS}")
        effective_n_sims = PREVIEW_MAX_SIMS

    end_date = date.today()
    holding_returns, portfolio_series, factor_panel, benchmark_returns, _latest_prices = _build_monthly_panel(
        db,
        holdings=holdings,
        benchmark_symbol=portfolio.benchmark_symbol,
        end_date=end_date,
        warnings=warnings,
        allow_remote_fetch=persist,
        persist_factor_snapshot=persist,
    )

    factor_series = factor_panel.get(spec.key, pd.Series(dtype=float))
    if factor_series.dropna().empty:
        raise ValueError(f"No transformed factor data available for '{spec.key}'")

    raw_shock = _shock_to_factor_units(spec, payload.shock_value, payload.shock_unit)
    factor_clean = factor_series.dropna()
    factor_mean = float(factor_clean.mean()) if len(factor_clean) else 0.0
    factor_std = float(factor_clean.std(ddof=1)) if len(factor_clean) > 1 else 0.0

    shock = raw_shock
    if factor_std > 0:
        lower = factor_mean - MAX_SHOCK_Z * factor_std
        upper = factor_mean + MAX_SHOCK_Z * factor_std
        clipped = float(np.clip(raw_shock, lower, upper))
        if abs(clipped - raw_shock) > 1e-12:
            warnings.append("E_SHOCK_CLIPPED")
            shock = clipped

    h_months = payload.horizon_days / 21.0
    horizon_steps = max(1, int(round(h_months)))
    step_scale = h_months / horizon_steps
    shock_persistence = FACTOR_SHOCK_PERSISTENCE.get(spec.key, 0.6)

    available_holdings = [h for h in holdings if h.symbol.upper() in holding_returns.columns]
    missing_symbols = [h.symbol.upper() for h in holdings if h.symbol.upper() not in holding_returns.columns]
    if missing_symbols:
        warnings.append(f"E_SYMBOL_PRICE_GAPS:{','.join(sorted(set(missing_symbols)))}")

    if not available_holdings:
        raise ValueError("No holdings with aligned price history for scenario model")

    symbols = [h.symbol.upper() for h in available_holdings]
    weights = np.array([float(h.weight) for h in available_holdings], dtype=float)
    weights = weights / float(weights.sum())
    holding_returns = holding_returns[symbols]
    current_values = {h.symbol.upper(): float(h.market_value) for h in available_holdings}
    portfolio_value = float(sum(current_values.values()))

    relationship_stats: dict[str, RelationshipStatsOut] = {}
    residual_map: dict[str, pd.Series] = {}
    expected_map_log: dict[str, float] = {}
    shock_map_log: dict[str, float] = {}
    beta_map: dict[str, float | None] = {}
    alpha_vec = np.zeros(len(symbols), dtype=float)
    beta_vec = np.zeros(len(symbols), dtype=float)

    control_series: dict[str, pd.Series] = {
        "market_ret": benchmark_returns
    }
    for control_key in factor_panel.columns:
        if control_key == spec.key:
            continue
        control = factor_panel[control_key]
        if control.dropna().empty:
            continue
        control_series[control_key] = control

    for symbol in symbols:
        y = holding_returns[symbol]
        stats, residual = _regression_stats_with_controls(y, factor_series, control_series)
        z_score, percentile = _shock_stats(factor_series, shock)
        stats.shock_z_score = z_score
        stats.shock_percentile = percentile

        relationship_stats[symbol] = stats
        residual_map[symbol] = residual
        beta_map[symbol] = stats.beta

        alpha = stats.alpha or 0.0
        beta = stats.beta or 0.0
        sym_idx = symbols.index(symbol)
        alpha_vec[sym_idx] = alpha
        beta_vec[sym_idx] = beta
        shock_accum = 0.0
        for step in range(horizon_steps):
            shock_accum += (shock * (shock_persistence**step)) * step_scale
        expected_map_log[symbol] = alpha * h_months + beta * shock_accum
        shock_map_log[symbol] = beta * shock_accum

    p_stats, _ = _regression_stats_with_controls(portfolio_series, factor_series, control_series)
    p_z, p_pct = _shock_stats(factor_series, shock)
    p_stats.shock_z_score = p_z
    p_stats.shock_percentile = p_pct
    relationship_stats["portfolio"] = p_stats

    expected_portfolio_log = float(sum(weights[i] * expected_map_log[s] for i, s in enumerate(symbols)))
    shock_portfolio_log = float(sum(weights[i] * shock_map_log[s] for i, s in enumerate(symbols)))

    residual_df = pd.concat({symbol: residual_map[symbol] for symbol in symbols}, axis=1).dropna(how="all")
    if residual_df.shape[0] < 3:
        warnings.append("E_LOW_RESIDUAL_OBS")
        residual_df = pd.DataFrame(0.0, index=factor_series.dropna().index, columns=symbols)

    resid_matrix = residual_df.to_numpy(dtype=float)
    if resid_matrix.ndim == 1:
        resid_matrix = resid_matrix.reshape(-1, 1)

    if resid_matrix.shape[0] > 1:
        sigma_eps = np.cov(resid_matrix, rowvar=False, ddof=1)
    else:
        sigma_eps = np.eye(len(symbols)) * 0.01

    if np.ndim(sigma_eps) == 0:
        sigma_eps = np.array([[float(sigma_eps)]], dtype=float)

    sigma_eps = np.array(sigma_eps, dtype=float)
    sigma_eps = np.nan_to_num(sigma_eps, nan=0.0, posinf=0.0, neginf=0.0)
    if sigma_eps.shape != (len(symbols), len(symbols)):
        sigma_eps = np.eye(len(symbols)) * float(np.nanmean(np.diag(sigma_eps)) if sigma_eps.size else 0.01)

    shrink = float(payload.shrinkage_lambda)
    sigma_hat = (1.0 - shrink) * sigma_eps + shrink * np.diag(np.diag(sigma_eps))

    diag = np.clip(np.diag(sigma_hat), 1e-8, None)
    np.fill_diagonal(sigma_hat, diag)

    cumulative_paths = np.zeros((effective_n_sims, horizon_steps, len(symbols)), dtype=float)
    running = np.zeros((effective_n_sims, len(symbols)), dtype=float)
    for step in range(horizon_steps):
        deterministic_step = (
            alpha_vec * step_scale + beta_vec * (shock * (shock_persistence**step)) * step_scale
        )
        try:
            eta_step = np.random.multivariate_normal(
                mean=np.zeros(len(symbols), dtype=float),
                cov=sigma_hat * max(step_scale, 1e-6),
                size=effective_n_sims,
            )
        except np.linalg.LinAlgError:
            warnings.append("E_COVARIANCE_ADJUSTED")
            sigma_hat = sigma_hat + np.eye(len(symbols)) * 1e-6
            eta_step = np.random.multivariate_normal(
                mean=np.zeros(len(symbols), dtype=float),
                cov=sigma_hat * max(step_scale, 1e-6),
                size=effective_n_sims,
            )
        running = running + deterministic_step[None, :] + eta_step
        cumulative_paths[:, step, :] = running

    simulated_returns_log = cumulative_paths[:, -1, :]
    portfolio_paths_log = np.tensordot(cumulative_paths, weights, axes=(2, 0))
    portfolio_draws_log = portfolio_paths_log[:, -1]

    selected_symbol = (payload.selected_symbol or symbols[0]).upper()
    if selected_symbol not in symbols:
        warnings.append(f"E_SELECTED_SYMBOL_NOT_IN_PORTFOLIO:{selected_symbol}")
        selected_symbol = symbols[0]

    selected_idx = symbols.index(selected_symbol)
    selected_paths_log = cumulative_paths[:, :, selected_idx]
    selected_draws_log = simulated_returns_log[:, selected_idx]

    portfolio_draws = np.asarray(_log_pct_to_simple_pct(portfolio_draws_log), dtype=float)
    selected_draws = np.asarray(_log_pct_to_simple_pct(selected_draws_log), dtype=float)

    conf_low = (1.0 - payload.confidence_level) / 2.0
    conf_high = 1.0 - conf_low

    def _impact_for(symbol: str, draws: np.ndarray) -> ScenarioImpactOut:
        current = portfolio_value if symbol == "portfolio" else current_values.get(symbol)
        expected_log = expected_portfolio_log if symbol == "portfolio" else expected_map_log[symbol]
        shock_log = shock_portfolio_log if symbol == "portfolio" else shock_map_log[symbol]
        expected_ret = float(_log_pct_to_simple_pct(expected_log))
        shock_ret = float(_log_pct_to_simple_pct(shock_log))
        expected_value = None
        shock_delta = None
        if current is not None:
            expected_value = float(current * (1.0 + expected_ret / 100.0))
            shock_delta = float(current * (shock_ret / 100.0))

        q_low = float(np.quantile(draws, conf_low)) if draws.size else None
        q_high = float(np.quantile(draws, conf_high)) if draws.size else None
        return ScenarioImpactOut(
            symbol=symbol,
            current_value=current,
            expected_return_pct=expected_ret,
            shock_only_return_pct=shock_ret,
            expected_value=expected_value,
            shock_only_value_delta=shock_delta,
            quantile_low_pct=q_low,
            quantile_high_pct=q_high,
        )

    portfolio_impact = _impact_for("portfolio", portfolio_draws)
    selected_impact = _impact_for(selected_symbol, selected_draws)

    contributions = [
        ScenarioContributionOut(
            symbol=symbol,
            weight=float(weights[idx]),
            beta=beta_map.get(symbol),
            contribution_pct=float(weights[idx] * float(_log_pct_to_simple_pct(shock_map_log[symbol]))),
        )
        for idx, symbol in enumerate(symbols)
    ]
    contributions.sort(key=lambda item: abs(item.contribution_pct or 0.0), reverse=True)

    top_pos = max(contributions, key=lambda item: item.contribution_pct or -1e9, default=None)
    top_neg = min(contributions, key=lambda item: item.contribution_pct or 1e9, default=None)

    simulation_stats = {
        "portfolio": _simulation_stats(portfolio_draws, payload.confidence_level),
        selected_symbol: _simulation_stats(selected_draws, payload.confidence_level),
    }

    distribution_bins = _distribution_bins(portfolio_draws, series_key="portfolio")
    simulation_paths = _build_sample_paths(
        series_key="portfolio",
        cumulative_log_paths=portfolio_paths_log,
        current_value=portfolio_value,
        max_paths=24 if persist else PREVIEW_MAX_PATHS,
    )
    simulation_paths.extend(
        _build_sample_paths(
            series_key=selected_symbol,
            cumulative_log_paths=selected_paths_log,
            current_value=current_values.get(selected_symbol),
            max_paths=24 if persist else PREVIEW_MAX_PATHS,
        )
    )
    narrative = _build_narrative(
        factor_label=spec.label,
        shock_value=payload.shock_value,
        shock_unit=payload.shock_unit,
        horizon_days=payload.horizon_days,
        portfolio_impact=portfolio_impact,
        top_pos=top_pos,
        top_neg=top_neg,
    )

    assumptions = {
        "factor_source": f"{spec.source}:{spec.source_series}",
        "transform": spec.transform,
        "horizon_months": h_months,
        "horizon_steps": horizon_steps,
        "min_obs_required": MIN_OBS,
        "aligned_obs": int(len(factor_series.dropna())),
        "lookback_years": DEFAULT_LOOKBACK_YEARS,
        "shrinkage_lambda": payload.shrinkage_lambda,
        "controls_used": list(control_series.keys()),
        "shock_persistence": shock_persistence,
        "raw_shock_factor_units": raw_shock,
        "effective_shock_factor_units": shock,
        "return_reporting": "simple_percent_from_log_model",
    }

    inputs = {
        "factor_key": payload.factor_key,
        "shock_value": payload.shock_value,
        "shock_unit": payload.shock_unit,
        "shock_in_factor_units": shock,
        "horizon_days": payload.horizon_days,
        "confidence_level": payload.confidence_level,
        "n_sims": effective_n_sims,
        "selected_symbol": selected_symbol,
        "include_baseline": payload.include_baseline,
    }

    response = ScenarioResultResponse(
        status="ok" if not warnings else "partial",
        warnings=sorted(set(warnings)),
        model_version=MODEL_VERSION,
        inputs=inputs,
        assumptions=assumptions,
        portfolio_impact=portfolio_impact,
        selected_stock_impact=selected_impact,
        contributions=contributions,
        distribution_bins=distribution_bins,
        simulation_paths=simulation_paths,
        relationship_stats={
            "portfolio": relationship_stats["portfolio"],
            selected_symbol: relationship_stats[selected_symbol],
        },
        simulation_stats=simulation_stats,
        narrative=narrative,
        run_id=None,
        created_at=None,
    )

    if persist:
        assumptions_with_paths = {
            **assumptions,
            "simulation_paths": [path.model_dump() for path in simulation_paths],
        }

        run = ScenarioRun(
            portfolio_id=portfolio_id,
            snapshot_id=snapshot.id,
            trigger_type="manual_run",
            status="completed" if response.status == "ok" else "completed_with_warnings",
            factor_key=payload.factor_key,
            shock_value=payload.shock_value,
            shock_unit=payload.shock_unit,
            horizon_days=payload.horizon_days,
            confidence_level=payload.confidence_level,
            n_sims=effective_n_sims,
            selected_symbol=selected_symbol,
            include_baseline=payload.include_baseline,
            shrinkage_lambda=payload.shrinkage_lambda,
            assumptions_json=json.dumps(assumptions_with_paths, separators=(",", ":"), sort_keys=True),
            warnings_json=json.dumps(sorted(set(warnings))),
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            model_version=MODEL_VERSION,
        )
        db.add(run)
        db.flush()

        db.add(
            ScenarioRunPortfolio(
                run_id=run.id,
                portfolio_id=portfolio_id,
                expected_return_pct=portfolio_impact.expected_return_pct,
                shock_only_return_pct=portfolio_impact.shock_only_return_pct,
                expected_value=portfolio_impact.expected_value,
                shock_only_value_delta=portfolio_impact.shock_only_value_delta,
                simulated_mean_pct=simulation_stats["portfolio"].mean_pct,
                simulated_median_pct=simulation_stats["portfolio"].median_pct,
                simulated_std_pct=simulation_stats["portfolio"].std_pct,
                quantile_low_pct=simulation_stats["portfolio"].quantile_low_pct,
                quantile_high_pct=simulation_stats["portfolio"].quantile_high_pct,
                relationship_json=json.dumps(relationship_stats["portfolio"].model_dump(), separators=(",", ":")),
                simulation_json=json.dumps(simulation_stats["portfolio"].model_dump(), separators=(",", ":")),
                warnings_json=json.dumps(sorted(set(warnings))),
            )
        )

        for symbol in symbols:
            symbol_draws_log = simulated_returns_log[:, symbols.index(symbol)]
            symbol_draws = np.asarray(_log_pct_to_simple_pct(symbol_draws_log), dtype=float)
            symbol_stats = _simulation_stats(symbol_draws, payload.confidence_level)
            impact = _impact_for(symbol, symbol_draws)
            db.add(
                ScenarioRunResult(
                    run_id=run.id,
                    symbol=symbol,
                    expected_return_pct=impact.expected_return_pct,
                    shock_only_return_pct=impact.shock_only_return_pct,
                    expected_value=impact.expected_value,
                    shock_only_value_delta=impact.shock_only_value_delta,
                    simulated_mean_pct=symbol_stats.mean_pct,
                    simulated_median_pct=symbol_stats.median_pct,
                    simulated_std_pct=symbol_stats.std_pct,
                    quantile_low_pct=symbol_stats.quantile_low_pct,
                    quantile_high_pct=symbol_stats.quantile_high_pct,
                    relationship_json=json.dumps(relationship_stats[symbol].model_dump(), separators=(",", ":")),
                    simulation_json=json.dumps(symbol_stats.model_dump(), separators=(",", ":")),
                    warnings_json=json.dumps(sorted(set(warnings))),
                )
            )

        for bin_row in distribution_bins:
            db.add(
                ScenarioRunDistributionBin(
                    run_id=run.id,
                    series_key=bin_row.series_key,
                    bin_index=bin_row.bin_index,
                    bin_start=bin_row.bin_start,
                    bin_end=bin_row.bin_end,
                    count=bin_row.count,
                    density=bin_row.density,
                )
            )

        for idx, line in enumerate(narrative):
            db.add(ScenarioRunNarrative(run_id=run.id, block_key=f"line_{idx+1}", content=line))

        db.flush()
        response.run_id = run.id
        response.created_at = run.finished_at

    return response


def list_scenario_runs(db: Session, *, portfolio_id: int, limit: int = 100) -> ScenarioRunListResponse:
    rows = list(
        db.scalars(
            select(ScenarioRun)
            .where(ScenarioRun.portfolio_id == portfolio_id)
            .order_by(desc(ScenarioRun.started_at), desc(ScenarioRun.id))
            .limit(limit)
        )
    )
    return ScenarioRunListResponse(
        portfolio_id=portfolio_id,
        runs=[
            ScenarioRunListItem(
                id=row.id,
                status=row.status,
                factor_key=row.factor_key,
                shock_value=row.shock_value,
                shock_unit=row.shock_unit,
                horizon_days=row.horizon_days,
                confidence_level=row.confidence_level,
                n_sims=row.n_sims,
                selected_symbol=row.selected_symbol,
                started_at=row.started_at,
                finished_at=row.finished_at,
                error=row.error,
            )
            for row in rows
        ],
    )


def get_scenario_run_detail(db: Session, *, portfolio_id: int, run_id: int) -> ScenarioResultResponse | None:
    run = db.scalar(
        select(ScenarioRun)
        .where(ScenarioRun.id == run_id)
        .where(ScenarioRun.portfolio_id == portfolio_id)
        .limit(1)
    )
    if run is None:
        return None

    portfolio_row = db.scalar(
        select(ScenarioRunPortfolio)
        .where(ScenarioRunPortfolio.run_id == run.id)
        .limit(1)
    )
    if portfolio_row is None:
        return None

    selected_symbol = run.selected_symbol or ""
    symbol_row = None
    if selected_symbol:
        symbol_row = db.scalar(
            select(ScenarioRunResult)
            .where(ScenarioRunResult.run_id == run.id)
            .where(ScenarioRunResult.symbol == selected_symbol)
            .limit(1)
        )

    bins = list(
        db.scalars(
            select(ScenarioRunDistributionBin)
            .where(ScenarioRunDistributionBin.run_id == run.id)
            .order_by(ScenarioRunDistributionBin.series_key.asc(), ScenarioRunDistributionBin.bin_index.asc())
        )
    )
    narratives = list(
        db.scalars(
            select(ScenarioRunNarrative)
            .where(ScenarioRunNarrative.run_id == run.id)
            .order_by(ScenarioRunNarrative.id.asc())
        )
    )

    symbol_results = list(
        db.scalars(
            select(ScenarioRunResult)
            .where(ScenarioRunResult.run_id == run.id)
            .order_by(ScenarioRunResult.symbol.asc())
        )
    )

    contributions = [
        ScenarioContributionOut(
            symbol=item.symbol,
            weight=0.0,
            beta=(_safe_json_loads(item.relationship_json, {}).get("beta") if item.relationship_json else None),
            contribution_pct=item.shock_only_return_pct,
        )
        for item in symbol_results
    ]

    relationship_stats: dict[str, RelationshipStatsOut] = {
        "portfolio": RelationshipStatsOut(**_safe_json_loads(portfolio_row.relationship_json, {})),
    }
    simulation_stats: dict[str, SimulationStatsOut] = {
        "portfolio": SimulationStatsOut(**_safe_json_loads(portfolio_row.simulation_json, {})),
    }

    selected_impact = None
    if symbol_row is not None:
        relationship_stats[selected_symbol] = RelationshipStatsOut(
            **_safe_json_loads(symbol_row.relationship_json, {})
        )
        simulation_stats[selected_symbol] = SimulationStatsOut(
            **_safe_json_loads(symbol_row.simulation_json, {})
        )
        selected_impact = ScenarioImpactOut(
            symbol=symbol_row.symbol,
            expected_return_pct=symbol_row.expected_return_pct,
            shock_only_return_pct=symbol_row.shock_only_return_pct,
            expected_value=symbol_row.expected_value,
            shock_only_value_delta=symbol_row.shock_only_value_delta,
            quantile_low_pct=symbol_row.quantile_low_pct,
            quantile_high_pct=symbol_row.quantile_high_pct,
        )

    raw_assumptions = _safe_json_loads(run.assumptions_json, {})
    simulation_paths = raw_assumptions.get("simulation_paths", []) if isinstance(raw_assumptions, dict) else []
    if isinstance(raw_assumptions, dict):
        raw_assumptions = {k: v for k, v in raw_assumptions.items() if k != "simulation_paths"}

    return ScenarioResultResponse(
        status=run.status,
        warnings=[str(w) for w in _safe_json_loads(run.warnings_json, [])],
        model_version=run.model_version,
        inputs={
            "factor_key": run.factor_key,
            "shock_value": run.shock_value,
            "shock_unit": run.shock_unit,
            "horizon_days": run.horizon_days,
            "confidence_level": run.confidence_level,
            "n_sims": run.n_sims,
            "selected_symbol": run.selected_symbol,
            "include_baseline": run.include_baseline,
        },
        assumptions=raw_assumptions if isinstance(raw_assumptions, dict) else {},
        portfolio_impact=ScenarioImpactOut(
            symbol="portfolio",
            expected_return_pct=portfolio_row.expected_return_pct,
            shock_only_return_pct=portfolio_row.shock_only_return_pct,
            expected_value=portfolio_row.expected_value,
            shock_only_value_delta=portfolio_row.shock_only_value_delta,
            quantile_low_pct=portfolio_row.quantile_low_pct,
            quantile_high_pct=portfolio_row.quantile_high_pct,
        ),
        selected_stock_impact=selected_impact,
        contributions=contributions,
        distribution_bins=[
            ScenarioDistributionBinOut(
                series_key=item.series_key,
                bin_index=item.bin_index,
                bin_start=item.bin_start,
                bin_end=item.bin_end,
                count=item.count,
                density=item.density,
            )
            for item in bins
        ],
        simulation_paths=[
            ScenarioPathOut(**item)
            for item in simulation_paths
            if isinstance(item, dict)
        ],
        relationship_stats=relationship_stats,
        simulation_stats=simulation_stats,
        narrative=[item.content for item in narratives],
        run_id=run.id,
        created_at=run.finished_at,
    )


def scenario_sensitivity(
    db: Session,
    *,
    portfolio_id: int,
    symbol: str,
    factor_key: str,
) -> dict[str, Any]:
    payload = ScenarioPreviewRequest(
        factor_key=factor_key,
        shock_value=FACTOR_SPECS[factor_key].default_value,
        shock_unit=FACTOR_SPECS[factor_key].unit,
        horizon_days=21,
        confidence_level=0.95,
        n_sims=PREVIEW_MAX_SIMS,
        selected_symbol=symbol.upper(),
        include_baseline=True,
        shrinkage_lambda=0.2,
    )
    out = run_scenario_preview(db, portfolio_id=portfolio_id, payload=payload, persist=False)
    return {
        "status": out.status,
        "warnings": out.warnings,
        "factor_key": factor_key,
        "portfolio": out.relationship_stats.get("portfolio", RelationshipStatsOut()).model_dump(),
        "symbol": out.relationship_stats.get(symbol.upper(), RelationshipStatsOut()).model_dump(),
        "portfolio_impact": out.portfolio_impact.model_dump(),
        "symbol_impact": (out.selected_stock_impact.model_dump() if out.selected_stock_impact else None),
    }


def refresh_macro_cache_for_scenarios(db: Session, *, portfolio_id: int) -> list[str]:
    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        return ["scenario_cache:no_snapshot"]

    holdings = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )
    if not holdings:
        return ["scenario_cache:no_holdings"]

    warnings: list[str] = []
    end_date = date.today()
    _build_monthly_panel(
        db,
        holdings=holdings,
        benchmark_symbol=snapshot.portfolio.benchmark_symbol,
        end_date=end_date,
        warnings=warnings,
        allow_remote_fetch=True,
        persist_factor_snapshot=True,
    )
    return warnings


def scenario_debug_latest_factor_snapshot(db: Session) -> dict[str, Any] | None:
    snap = _latest_factor_snapshot(db)
    if snap is None:
        return None
    return {
        "as_of_date": snap.as_of_date.isoformat(),
        "factors": _safe_json_loads(snap.factors_json, {}),
        "warnings": _safe_json_loads(snap.warnings_json, []),
    }
